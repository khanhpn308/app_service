"""Transactional sequence tracking for validated application-level pings."""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.ping import MissingPingPayload, PingPayload
from app.schemas.pings import PingMessage

MAX_MISSING_GAP = 10000


class PingDeviceNotFoundError(ValueError):
    """The source Node is absent from the authenticated device catalog."""


class PingGapTooLargeError(ValueError):
    """The inferred missing range exceeds the bounded bulk-insert limit."""


class PingPersistenceError(RuntimeError):
    """Stable public failure for internal database errors."""


@dataclass(frozen=True)
class PingPersistenceResult:
    record_id: int
    device_id: int
    cycle_id: int
    order: int
    node_timestamp_ms: int
    predicted_order: int


def _max_cycle(db: Session, device_id: int) -> int | None:
    return db.scalar(
        select(func.max(PingPayload.cycle_id)).where(
            PingPayload.device_id == device_id
        )
    )


def _predicted_order(db: Session, device_id: int, cycle_id: int) -> int:
    maximum = db.scalar(
        select(func.max(PingPayload.order)).where(
            PingPayload.device_id == device_id,
            PingPayload.cycle_id == cycle_id,
        )
    )
    return 1 if maximum is None else maximum + 1


def persist_ping(
    session_factory: Callable[[], Session], ping: PingMessage
) -> PingPersistenceResult:
    """Persist one ping and its missing-order transitions in one transaction."""

    with session_factory() as db:
        try:
            device_id = ping.canonical_device_id
            device = db.scalar(
                select(Device)
                .where(Device.device_id == device_id)
                .with_for_update()
            )
            if device is None:
                raise PingDeviceNotFoundError("device_id: device not found")

            maximum_cycle = _max_cycle(db, device_id)
            if maximum_cycle is None:
                cycle_id = 1
            elif ping.order == 1:
                cycle_id = maximum_cycle + 1
            else:
                cycle_id = maximum_cycle

            predicted_order = _predicted_order(db, device_id, cycle_id)
            if ping.order > predicted_order:
                gap_count = ping.order - predicted_order
                if gap_count > MAX_MISSING_GAP:
                    raise PingGapTooLargeError("order: gap exceeds 10000")
                db.execute(
                    insert(MissingPingPayload),
                    [
                        {
                            "payload_id": missing_order,
                            "device_id": device_id,
                            "cycle_id": cycle_id,
                        }
                        for missing_order in range(predicted_order, ping.order)
                    ],
                )
            elif 1 < ping.order < predicted_order:
                db.execute(
                    delete(MissingPingPayload).where(
                        MissingPingPayload.device_id == device_id,
                        MissingPingPayload.cycle_id == cycle_id,
                        MissingPingPayload.payload_id == ping.order,
                    )
                )

            row = PingPayload(
                device_id=device_id,
                cycle_id=cycle_id,
                order=ping.order,
                node_timestamp_ms=ping.timestamp,
            )
            db.add(row)
            db.flush()
            record_id = row.id
            next_predicted_order = max(predicted_order, ping.order + 1)
            db.commit()
            return PingPersistenceResult(
                record_id=record_id,
                device_id=device_id,
                cycle_id=cycle_id,
                order=ping.order,
                node_timestamp_ms=ping.timestamp,
                predicted_order=next_predicted_order,
            )
        except (PingDeviceNotFoundError, PingGapTooLargeError):
            db.rollback()
            raise
        except Exception as error:
            db.rollback()
            raise PingPersistenceError("ping persistence failed") from error
