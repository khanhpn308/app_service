from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.core.deps import get_current_user, get_db
from app.models.base import Base
from app.models.device import Device
from app.models.ping import MissingPingPayload, PingPayload


@pytest.fixture
def api():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    actor = {"user": SimpleNamespace(role="admin")}

    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    def override_db():
        try:
            yield db
        except Exception:
            db.rollback()
            raise

    def override_user():
        return actor["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as client:
        yield client, db, actor
    db.close()


def _add_device(db: Session, device_id: int = 101) -> Device:
    device = Device(
        device_id=device_id,
        devicename=f"ESP32 Node {device_id}",
        status="active",
        user_device_asignment_id=0,
    )
    db.add(device)
    db.flush()
    return device


def _add_ping(
    db: Session,
    *,
    order: int,
    timestamp: int,
    device_id: int = 101,
    cycle_id: int = 1,
) -> PingPayload:
    row = PingPayload(
        device_id=device_id,
        cycle_id=cycle_id,
        order=order,
        node_timestamp_ms=timestamp,
    )
    db.add(row)
    db.flush()
    return row


def _add_missing(
    db: Session,
    *,
    payload_id: int,
    device_id: int = 101,
    cycle_id: int = 1,
) -> None:
    db.add(
        MissingPingPayload(
            payload_id=payload_id,
            device_id=device_id,
            cycle_id=cycle_id,
        )
    )


def test_admin_summary_uses_latest_record_id_and_aggregate_totals(api) -> None:
    client, db, _ = api
    _add_device(db)
    _add_ping(db, order=15, timestamp=111)
    latest = _add_ping(db, order=2, timestamp=222)
    _add_missing(db, payload_id=3)
    _add_missing(db, payload_id=4, cycle_id=2)
    db.commit()

    response = client.get("/api/pings/101/summary")

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "101",
        "total_payload": 2,
        "current_payload": {
            "id": latest.id,
            "order": 2,
            "timestamp": 222,
        },
        "total_missing_payload": 2,
    }


def test_admin_summary_returns_zero_state_for_existing_device(api) -> None:
    client, db, _ = api
    _add_device(db)
    db.commit()

    response = client.get("/api/pings/101/summary")

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "101",
        "total_payload": 0,
        "current_payload": None,
        "total_missing_payload": 0,
    }


def test_admin_delete_clears_both_tables_and_is_idempotent(api) -> None:
    client, db, _ = api
    _add_device(db)
    _add_ping(db, order=3, timestamp=100)
    _add_ping(db, order=4, timestamp=200)
    _add_missing(db, payload_id=1)
    _add_missing(db, payload_id=2)
    db.commit()

    deleted = client.delete("/api/pings/101")

    assert deleted.status_code == 200
    assert deleted.json() == {
        "ok": True,
        "device_id": "101",
        "deleted_payloads": 2,
        "deleted_missing_payloads": 2,
        "predicted_order": 1,
    }
    assert db.query(PingPayload).count() == 0
    assert db.query(MissingPingPayload).count() == 0

    deleted_again = client.delete("/api/pings/101")
    assert deleted_again.status_code == 200
    assert deleted_again.json() == {
        "ok": True,
        "device_id": "101",
        "deleted_payloads": 0,
        "deleted_missing_payloads": 0,
        "predicted_order": 1,
    }


@pytest.mark.parametrize("method", ["get", "delete"])
def test_ping_admin_endpoints_reject_non_admin(api, method: str) -> None:
    client, db, actor = api
    _add_device(db)
    _add_ping(db, order=1, timestamp=100)
    db.commit()
    actor["user"] = SimpleNamespace(role="user")
    path = "/api/pings/101/summary" if method == "get" else "/api/pings/101"

    response = getattr(client, method)(path)

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin role required"}
    assert db.query(PingPayload).count() == 1


@pytest.mark.parametrize("method", ["get", "delete"])
def test_ping_admin_endpoints_return_404_for_unknown_device(api, method: str) -> None:
    client, _, _ = api
    path = "/api/pings/999/summary" if method == "get" else "/api/pings/999"

    response = getattr(client, method)(path)

    assert response.status_code == 404
    assert response.json() == {"detail": "Device not found"}


def test_delete_rolls_back_both_tables_when_commit_fails(api, monkeypatch) -> None:
    client, db, _ = api
    _add_device(db)
    _add_ping(db, order=3, timestamp=100)
    _add_missing(db, payload_id=1)
    db.commit()

    def fail_commit() -> None:
        raise RuntimeError("simulated commit failure")

    with monkeypatch.context() as patcher:
        patcher.setattr(db, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="simulated commit failure"):
            client.delete("/api/pings/101")

    db.expire_all()
    assert db.query(PingPayload).count() == 1
    assert db.query(MissingPingPayload).count() == 1
