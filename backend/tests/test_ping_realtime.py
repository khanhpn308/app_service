import asyncio
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

from app.api import websocket_routes
from app.api.ping_routes import router as ping_router
from app.api.websocket_routes import router as websocket_router
from app.core import deps
from app.core.deps import get_current_user, get_db
from app.core.realtime_hub import RealtimeHub
from app.core.security import create_access_token
from app.models.base import Base
from app.models.device import Device
from app.models.ping import PingPayload
from app.models.user import User


class FakeSocket:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.fail_send = fail_send
        self.accepted_subprotocol = None
        self.sent: list[dict] = []
        self.closed = False

    async def accept(self, *, subprotocol=None) -> None:
        self.accepted_subprotocol = subprotocol

    async def send_json(self, message: dict) -> None:
        if self.fail_send:
            raise RuntimeError("stale socket")
        self.sent.append(dict(message))

    async def close(self) -> None:
        self.closed = True


def test_hub_isolates_ping_events_and_removes_failed_admin_socket() -> None:
    async def scenario() -> None:
        hub = RealtimeHub()
        global_socket = FakeSocket()
        admin_socket = FakeSocket()
        stale_socket = FakeSocket(fail_send=True)
        await hub.connect_global(global_socket)
        await hub.connect_ping_admin(admin_socket)
        await hub.connect_ping_admin(stale_socket)

        sent = await hub.publish_ping_stats("101", reason="received")

        assert sent == 1
        assert admin_socket.sent == [
            {
                "type": "ping_stats_updated",
                "device_id": "101",
                "reason": "received",
            }
        ]
        assert global_socket.sent == []
        assert stale_socket not in hub._ping_admin_clients

    asyncio.run(scenario())


def test_hub_stop_closes_and_clears_ping_admin_group() -> None:
    async def scenario() -> None:
        hub = RealtimeHub()
        admin_socket = FakeSocket()
        await hub.connect_ping_admin(admin_socket)

        await hub.stop()

        assert admin_socket.closed is True
        assert hub._ping_admin_clients == set()

    asyncio.run(scenario())


def test_threadsafe_ping_publish_reaches_admin_group() -> None:
    async def scenario() -> None:
        hub = RealtimeHub()
        admin_socket = FakeSocket()
        await hub.start()
        await hub.connect_ping_admin(admin_socket)

        await asyncio.to_thread(
            hub.publish_ping_stats_from_thread,
            "101",
            reason="cleared",
        )
        for _ in range(20):
            if admin_socket.sent:
                break
            await asyncio.sleep(0)

        assert admin_socket.sent == [
            {
                "type": "ping_stats_updated",
                "device_id": "101",
                "reason": "cleared",
            }
        ]
        await hub.stop()

    asyncio.run(scenario())


def _add_user(db: Session, username: str, role: str, sequence: int) -> User:
    user = User(
        username=username,
        password="not-used",
        fullname=f"User {username}",
        cccd=f"{sequence:012d}",
        creat_at=date.today(),
        expired_at=date.today() + timedelta(days=30),
        status="active",
        role=role,
        can_config_anchor="no",
    )
    db.add(user)
    db.flush()
    return user


def test_ping_admin_websocket_requires_admin_jwt_subprotocol(monkeypatch) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        admin = _add_user(db, "ping-admin", "admin", 1)
        member = _add_user(db, "ping-member", "user", 2)
        db.commit()
        admin_token = create_access_token(
            subject=admin.username,
            user_id=admin.user_id,
            role=admin.role,
        )
        member_token = create_access_token(
            subject=member.username,
            user_id=member.user_id,
            role=member.role,
        )

    monkeypatch.setattr(deps, "SessionLocal", factory)
    app = FastAPI()
    hub = RealtimeHub()
    app.state.realtime_hub = hub
    app.include_router(websocket_router, prefix="/api")
    app.include_router(websocket_router)

    with TestClient(app) as client:
        for path in ("/api/ws/pings", "/ws/pings"):
            with client.websocket_connect(
                path,
                subprotocols=["iot-jwt", admin_token],
            ) as websocket:
                assert websocket.accepted_subprotocol == "iot-jwt"

        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                "/api/ws/pings",
                subprotocols=["iot-jwt", member_token],
            ) as websocket:
                websocket.receive_text()

    assert error.value.code == 1008
    assert hub._ping_admin_clients == set()


def test_ping_commit_echoes_before_redacted_received_event(monkeypatch) -> None:
    actions: list[tuple] = []

    class EventHub:
        async def publish_ping_stats(self, device_id: str, *, reason: str) -> int:
            actions.append(("event", device_id, reason))
            return 1

    class FrameSocket:
        app = SimpleNamespace(state=SimpleNamespace(realtime_hub=EventHub()))

        async def send_text(self, raw: str) -> None:
            actions.append(("echo", raw))

        async def send_json(self, message: dict) -> None:
            actions.append(("error", message))

    monkeypatch.setattr(websocket_routes, "persist_ping", lambda factory, ping: None)
    raw = (
        '{"device_id":"101","sensor_type":"ping","order":1,"size":8,'
        '"payload":"BCDEFGHI","location":"","timestamp":12345}'
    )

    handled = asyncio.run(
        websocket_routes._handle_ping_payload(
            FrameSocket(),
            {
                "device_id": "101",
                "sensor_type": "ping",
                "order": 1,
                "size": 8,
                "payload": "BCDEFGHI",
                "location": "",
                "timestamp": 12345,
            },
            raw,
        )
    )

    assert handled is True
    assert actions == [
        ("echo", raw),
        ("event", "101", "received"),
    ]
    assert "BCDEFGHI" not in str(actions[1])


def test_delete_commit_publishes_redacted_cleared_event() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    db.add(
        Device(
            device_id=101,
            devicename="ESP32 Node 101",
            status="active",
            user_device_asignment_id=0,
        )
    )
    db.add(
        PingPayload(
            device_id=101,
            cycle_id=1,
            order=1,
            node_timestamp_ms=12345,
        )
    )
    db.commit()

    events: list[dict] = []

    class EventHub:
        def publish_ping_stats_from_thread(
            self, device_id: str, *, reason: str
        ) -> None:
            events.append(
                {
                    "type": "ping_stats_updated",
                    "device_id": device_id,
                    "reason": reason,
                }
            )

    app = FastAPI()
    app.state.realtime_hub = EventHub()
    app.include_router(ping_router, prefix="/api")

    def override_db():
        try:
            yield db
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="admin")

    with TestClient(app) as client:
        response = client.delete("/api/pings/101")

    assert response.status_code == 200
    assert events == [
        {
            "type": "ping_stats_updated",
            "device_id": "101",
            "reason": "cleared",
        }
    ]
    assert "payload" not in events[0]
    db.close()
