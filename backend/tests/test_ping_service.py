import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.device import Device
from app.models.ping import MissingPingPayload, PingPayload
from app.schemas.pings import PingMessage


def _service_api():
    try:
        from app.services.ping_service import (
            PingDeviceNotFoundError,
            PingGapTooLargeError,
            PingPersistenceError,
            persist_ping,
        )
    except ImportError:
        pytest.fail("PING-04 sequence persistence service is not implemented")
    return (
        persist_ping,
        PingDeviceNotFoundError,
        PingGapTooLargeError,
        PingPersistenceError,
    )


@pytest.fixture
def database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add(
            Device(
                device_id=101,
                devicename="Node 101",
                status="active",
                user_device_asignment_id=0,
            )
        )
        db.add(
            Device(
                device_id=102,
                devicename="Node 102",
                status="active",
                user_device_asignment_id=0,
            )
        )
        db.commit()
    return factory


def _ping(order: int, *, device_id: str = "101", timestamp: int = 1) -> PingMessage:
    return PingMessage.model_validate(
        {
            "device_id": device_id,
            "sensor_type": "ping",
            "order": order,
            "size": 1,
            "payload": "X",
            "location": "",
            "timestamp": timestamp,
        }
    )


def _orders(factory, model, *, device_id: int = 101, cycle_id: int | None = None):
    with factory() as db:
        query = db.query(model).filter(model.device_id == device_id)
        if cycle_id is not None:
            query = query.filter(model.cycle_id == cycle_id)
        column = model.order if model is PingPayload else model.payload_id
        return [value for (value,) in query.order_by(model.id).with_entities(column).all()]


def test_forward_gap_and_late_recovery_preserve_predicted_state(database) -> None:
    persist_ping, *_ = _service_api()

    first = persist_ping(database, _ping(1, timestamp=100))
    jumped = persist_ping(database, _ping(5, timestamp=500))
    late = persist_ping(database, _ping(3, timestamp=300))

    assert (first.cycle_id, first.predicted_order) == (1, 2)
    assert (jumped.cycle_id, jumped.predicted_order) == (1, 6)
    assert (late.cycle_id, late.predicted_order) == (1, 6)
    assert _orders(database, PingPayload) == [1, 5, 3]
    assert _orders(database, MissingPingPayload) == [2, 4]
    with database() as db:
        assert [row.node_timestamp_ms for row in db.query(PingPayload).order_by(PingPayload.id)] == [
            100,
            500,
            300,
        ]


def test_duplicate_is_stored_without_missing_or_predicted_regression(database) -> None:
    persist_ping, *_ = _service_api()

    persist_ping(database, _ping(1))
    persist_ping(database, _ping(2))
    duplicate = persist_ping(database, _ping(2))

    assert duplicate.predicted_order == 3
    assert _orders(database, PingPayload) == [1, 2, 2]
    assert _orders(database, MissingPingPayload) == []


def test_order_one_opens_new_cycle_and_clear_restarts_cycle_one(database) -> None:
    persist_ping, *_ = _service_api()

    persist_ping(database, _ping(1))
    persist_ping(database, _ping(2))
    reset = persist_ping(database, _ping(1))

    assert (reset.cycle_id, reset.predicted_order) == (2, 2)
    with database() as db:
        assert [row.cycle_id for row in db.query(PingPayload).order_by(PingPayload.id)] == [
            1,
            1,
            2,
        ]
        db.query(MissingPingPayload).filter(
            MissingPingPayload.device_id == 101
        ).delete(synchronize_session=False)
        db.query(PingPayload).filter(PingPayload.device_id == 101).delete(
            synchronize_session=False
        )
        db.commit()

    after_clear = persist_ping(database, _ping(1))
    assert (after_clear.cycle_id, after_clear.predicted_order) == (1, 2)


def test_gap_limit_accepts_10000_and_rolls_back_10001(database) -> None:
    persist_ping, _, PingGapTooLargeError, _ = _service_api()

    accepted = persist_ping(database, _ping(10001))
    assert accepted.predicted_order == 10002
    assert len(_orders(database, MissingPingPayload)) == 10000

    with pytest.raises(PingGapTooLargeError, match="order: gap exceeds 10000"):
        persist_ping(database, _ping(10002, device_id="102"))

    assert _orders(database, PingPayload, device_id=102) == []
    assert _orders(database, MissingPingPayload, device_id=102) == []


def test_unknown_device_rolls_back_without_rows(database) -> None:
    persist_ping, PingDeviceNotFoundError, *_ = _service_api()

    with pytest.raises(PingDeviceNotFoundError, match="device_id: device not found"):
        persist_ping(database, _ping(1, device_id="999"))

    with database() as db:
        assert db.query(PingPayload).count() == 0
        assert db.query(MissingPingPayload).count() == 0


def test_database_error_is_stable_and_rolls_back_partial_rows(database) -> None:
    persist_ping, *_, PingPersistenceError = _service_api()
    bind = database.kw["bind"]

    class FailingCommitSession(Session):
        def commit(self) -> None:
            self.flush()
            raise RuntimeError("secret database detail")

    failing_factory = sessionmaker(
        bind=bind,
        class_=FailingCommitSession,
        expire_on_commit=False,
    )

    with pytest.raises(PingPersistenceError) as error:
        persist_ping(failing_factory, _ping(3))

    assert str(error.value) == "ping persistence failed"
    assert "secret database detail" not in str(error.value)
    with database() as db:
        assert db.query(PingPayload).count() == 0
        assert db.query(MissingPingPayload).count() == 0
