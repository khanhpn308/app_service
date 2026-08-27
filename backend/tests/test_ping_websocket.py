import json
import threading
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import websocket_routes
from app.models.base import Base
from app.models.device import Device
from app.models.ping import MissingPingPayload, PingPayload
from app.services.ping_service import PingPersistenceError


class FakeRealtimeHub:
    def __init__(self) -> None:
        self.handler_thread_id: int | None = None
        self.disconnected: list[str] = []
        self.ping_events: list[dict] = []

    async def connect_esp32(self, websocket, device_id: str, *, subprotocol=None):
        self.handler_thread_id = threading.get_ident()
        await websocket.accept(subprotocol=subprotocol)

    async def disconnect_esp32(self, websocket, device_id: str):
        self.disconnected.append(device_id)

    async def publish_ping_stats(self, device_id: str, *, reason: str) -> int:
        self.ping_events.append(
            {
                "type": "ping_stats_updated",
                "device_id": device_id,
                "reason": reason,
            }
        )
        return 1


@pytest.fixture
def ws_app(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add(
            Device(
                device_id=101,
                devicename="ESP32 Node 101",
                status="active",
                user_device_asignment_id=0,
            )
        )
        db.commit()

    hub = FakeRealtimeHub()
    side_effects = {"ingest": [], "ack": [], "presence": []}

    async def authenticate(websocket, device_id: str):
        return SimpleNamespace(device_id=int(device_id), device_type="gateway")

    class Presence:
        def touch(self, device_id: int) -> None:
            side_effects["presence"].append(device_id)

    def ingest(app, payload) -> None:
        side_effects["ingest"].append(dict(payload))

    def handle_ack(db, payload, **kwargs) -> bool:
        side_effects["ack"].append(dict(payload))
        return False

    monkeypatch.setattr(websocket_routes, "authenticate_ws_device", authenticate)
    monkeypatch.setattr(websocket_routes, "ws_device_auth_subprotocol", lambda ws: None)
    monkeypatch.setattr(websocket_routes, "SessionLocal", factory)
    monkeypatch.setattr(websocket_routes, "ingest_sensor_payload", ingest)
    monkeypatch.setattr(websocket_routes, "handle_gateway_uplink", handle_ack)

    app = FastAPI()
    app.state.realtime_hub = hub
    app.state.gateway_presence = Presence()
    app.include_router(websocket_routes.router, prefix="/api")
    return app, factory, hub, side_effects


def _raw_ping(order: int = 1) -> str:
    return (
        '{ "location" : "", "payload" : "BCDEFGHI", "size" : 8, '
        f'"order" : {order}, "sensor_type" : "ping", "device_id" : "101", '
        '"timestamp" : 12345 }'
    )


def _ping_payload(**overrides) -> dict:
    payload = {
        "device_id": "101",
        "sensor_type": "ping",
        "order": 1,
        "size": 8,
        "payload": "BCDEFGHI",
        "location": "",
        "timestamp": 12345,
    }
    payload.update(overrides)
    return payload


def test_text_ping_commits_then_echoes_exact_raw_text_without_telemetry(
    ws_app, monkeypatch
) -> None:
    app, factory, hub, side_effects = ws_app
    worker_thread_ids: list[int] = []
    real_persist_ping = websocket_routes.persist_ping

    def record_thread(session_factory, ping):
        worker_thread_ids.append(threading.get_ident())
        return real_persist_ping(session_factory, ping)

    monkeypatch.setattr(websocket_routes, "persist_ping", record_thread)
    raw = _raw_ping()

    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/esp32/900") as websocket:
            assert websocket.receive_json() == {
                "ok": True,
                "device_id": "900",
                "message": "connected",
            }
            websocket.send_text(raw)
            assert websocket.receive_text() == raw

    with factory() as db:
        stored = db.query(PingPayload).one()
        assert (stored.device_id, stored.order, stored.node_timestamp_ms) == (
            101,
            1,
            12345,
        )
        assert db.get(Device, 101).last_seen_at is None
    assert worker_thread_ids and worker_thread_ids[0] != hub.handler_thread_id
    assert side_effects == {"ingest": [], "ack": [], "presence": []}


def test_recognized_invalid_ping_returns_redacted_error_and_connection_stays_open(
    ws_app,
) -> None:
    app, factory, _, side_effects = ws_app
    invalid = _raw_ping().replace('"size" : 8', '"size" : 7')
    valid = _raw_ping()

    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/esp32/900") as websocket:
            websocket.receive_json()
            websocket.send_text(invalid)
            error = websocket.receive_json()
            assert error == {
                "ok": False,
                "type": "ping_error",
                "message": "size: payload UTF-8 byte length does not match size",
            }
            assert "BCDEFGHI" not in error["message"]

            websocket.send_text(valid)
            assert websocket.receive_text() == valid

    with factory() as db:
        assert db.query(PingPayload).count() == 1
        assert db.query(MissingPingPayload).count() == 0
    assert side_effects == {"ingest": [], "ack": [], "presence": []}


def test_persistence_failure_returns_stable_error_and_next_ping_can_succeed(
    ws_app, monkeypatch
) -> None:
    app, factory, _, side_effects = ws_app
    real_persist_ping = websocket_routes.persist_ping
    attempts = 0

    def fail_once(session_factory, ping):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PingPersistenceError("ping persistence failed")
        return real_persist_ping(session_factory, ping)

    monkeypatch.setattr(websocket_routes, "persist_ping", fail_once)

    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/esp32/900") as websocket:
            websocket.receive_json()
            websocket.send_text(_raw_ping())
            assert websocket.receive_json() == {
                "ok": False,
                "type": "ping_error",
                "message": "ping persistence failed",
            }
            websocket.send_text(_raw_ping())
            assert websocket.receive_text() == _raw_ping()

    with factory() as db:
        assert db.query(PingPayload).count() == 1
    assert side_effects == {"ingest": [], "ack": [], "presence": []}


def test_non_ping_json_keeps_existing_gateway_telemetry_pipeline(ws_app) -> None:
    app, factory, _, side_effects = ws_app

    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/esp32/900") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {
                    "device_id": "101",
                    "sensor_type": "temperature",
                    "temperature": 28.5,
                }
            )
            response = websocket.receive_json()

    assert response["ok"] is True
    assert response["received"]["sensor_type"] == "temperature"
    assert response["received"]["topic"] == "ws/900"
    assert "server_receive_ms" in response["received"]
    assert len(side_effects["ack"]) == 1
    assert len(side_effects["ingest"]) == 1
    assert side_effects["presence"] == [900]
    with factory() as db:
        assert db.query(PingPayload).count() == 0


def test_binary_json_ping_commits_then_echoes_exact_bytes_without_telemetry(
    ws_app, monkeypatch
) -> None:
    app, factory, hub, side_effects = ws_app
    worker_thread_ids: list[int] = []
    real_persist_ping = websocket_routes.persist_ping

    def record_thread(session_factory, ping):
        worker_thread_ids.append(threading.get_ident())
        return real_persist_ping(session_factory, ping)

    monkeypatch.setattr(websocket_routes, "persist_ping", record_thread)
    raw = _raw_ping().encode("utf-8")

    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/esp32/900") as websocket:
            websocket.receive_json()
            websocket.send_bytes(raw)
            assert websocket.receive_bytes() == raw

    with factory() as db:
        stored = db.query(PingPayload).one()
        assert (stored.device_id, stored.order, stored.node_timestamp_ms) == (
            101,
            1,
            12345,
        )
    assert worker_thread_ids and worker_thread_ids[0] != hub.handler_thread_id
    assert side_effects == {"ingest": [], "ack": [], "presence": []}


def test_recognized_invalid_binary_ping_returns_text_error(ws_app) -> None:
    app, factory, _, side_effects = ws_app
    invalid = _raw_ping().replace('"size" : 8', '"size" : 7').encode("utf-8")

    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/esp32/900") as websocket:
            websocket.receive_json()
            websocket.send_bytes(invalid)
            error = websocket.receive_json(mode="text")

    assert error == {
        "ok": False,
        "type": "ping_error",
        "message": "size: payload UTF-8 byte length does not match size",
    }
    with factory() as db:
        assert db.query(PingPayload).count() == 0
    assert side_effects == {"ingest": [], "ack": [], "presence": []}


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff\xfe\xfd",
        b'{"sensor_type":"ping"',
        b'{"sensor_type":"temperature","device_id":"101"}',
    ],
)
def test_non_ping_or_undecodable_binary_keeps_existing_binary_pipeline(
    ws_app, raw: bytes
) -> None:
    app, factory, _, _ = ws_app

    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/esp32/900") as websocket:
            websocket.receive_json()
            websocket.send_bytes(raw)
            assert websocket.receive_json() == {
                "ok": True,
                "device_id": "900",
                "echo_bytes": len(raw),
            }

    with factory() as db:
        assert db.query(PingPayload).count() == 0


def test_legacy_ping_prefix_is_no_longer_raw_echoed_by_websocket(ws_app) -> None:
    app, _, _, _ = ws_app

    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/esp32/900") as websocket:
            websocket.receive_json()

            websocket.send_text("PING|abc123")
            assert websocket.receive_json() == {
                "ok": True,
                "device_id": "900",
                "echo": "PING|abc123",
            }

            raw = b"PING|abc123"
            websocket.send_bytes(raw)
            assert websocket.receive_json() == {
                "ok": True,
                "device_id": "900",
                "echo_bytes": len(raw),
            }


def test_text_ping_size_uses_utf8_bytes_and_echoes_exact_raw_text(ws_app) -> None:
    app, factory, _, side_effects = ws_app
    payload = "A🙂"
    raw = json.dumps(
        _ping_payload(payload=payload, size=len(payload.encode("utf-8"))),
        ensure_ascii=False,
        separators=(",", ":"),
    )

    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/esp32/900") as websocket:
            websocket.receive_json()
            websocket.send_text(raw)
            assert websocket.receive_text() == raw

    with factory() as db:
        assert db.query(PingPayload).count() == 1
        assert db.get(Device, 101).last_seen_at is None
    assert side_effects == {"ingest": [], "ack": [], "presence": []}


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        ({"size": 7}, "size: payload UTF-8 byte length does not match size"),
        ({"order": 0}, "order: Input should be greater than or equal to 1"),
        (
            {"order": 4294967296},
            "order: Input should be less than or equal to 4294967295",
        ),
        ({"size": 0}, "size: Input should be greater than or equal to 1"),
        ({"size": 16385}, "size: Input should be less than or equal to 16384"),
        ({"device_id": ""}, "device_id: device ID must be a positive decimal string"),
        ({"device_id": "999"}, "device_id: device not found"),
        ({"timestamp": -1}, "timestamp: Input should be greater than or equal to 0"),
        ({"order": "1"}, "order: Input should be a valid integer"),
        ({"device_id": 101}, "device_id: Input should be a valid string"),
        ({"unexpected": "value"}, "unexpected: Extra inputs are not permitted"),
    ],
)
def test_recognized_invalid_text_ping_contract_matrix_has_no_side_effects(
    ws_app, overrides: dict, expected_message: str
) -> None:
    app, factory, _, side_effects = ws_app
    raw = json.dumps(_ping_payload(**overrides), separators=(",", ":"))

    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/esp32/900") as websocket:
            websocket.receive_json()
            websocket.send_text(raw)
            assert websocket.receive_json() == {
                "ok": False,
                "type": "ping_error",
                "message": expected_message,
            }

            websocket.send_text("   ")
            assert websocket.receive_json() == {
                "ok": True,
                "type": "pong",
                "device_id": "900",
            }

    with factory() as db:
        assert db.query(PingPayload).count() == 0
        assert db.query(MissingPingPayload).count() == 0
        assert db.get(Device, 101).last_seen_at is None
    assert side_effects == {"ingest": [], "ack": [], "presence": []}


def test_malformed_text_json_keeps_connection_alive_without_ping_side_effects(
    ws_app,
) -> None:
    app, factory, _, side_effects = ws_app
    raw = '{"sensor_type":"ping"'

    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/esp32/900") as websocket:
            websocket.receive_json()
            websocket.send_text(raw)
            assert websocket.receive_json() == {
                "ok": True,
                "device_id": "900",
                "echo": raw,
            }

            websocket.send_text("   ")
            assert websocket.receive_json()["type"] == "pong"

    with factory() as db:
        assert db.query(PingPayload).count() == 0
        assert db.get(Device, 101).last_seen_at is None
    assert side_effects == {"ingest": [], "ack": [], "presence": []}


def test_uppercase_ping_sensor_type_uses_existing_telemetry_pipeline(ws_app) -> None:
    app, factory, _, side_effects = ws_app

    with TestClient(app) as client:
        with client.websocket_connect("/api/ws/esp32/900") as websocket:
            websocket.receive_json()
            websocket.send_json(_ping_payload(sensor_type="PING"))
            response = websocket.receive_json()

    assert response["ok"] is True
    assert response["received"]["sensor_type"] == "PING"
    assert len(side_effects["ack"]) == 1
    assert len(side_effects["ingest"]) == 1
    assert side_effects["presence"] == [900]
    with factory() as db:
        assert db.query(PingPayload).count() == 0
