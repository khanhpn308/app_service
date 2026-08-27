"""Admin REST endpoints for application-level ping statistics."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.models.device import Device
from app.models.ping import MissingPingPayload, PingPayload
from app.models.user import User
from app.schemas.pings import (
    PingCurrentPayload,
    PingDeleteResponse,
    PingSummaryResponse,
)

router = APIRouter(prefix="/pings", tags=["pings"])


def _device_or_404(db: Session, device_id: int, *, lock: bool = False) -> Device:
    statement = select(Device).where(Device.device_id == device_id)
    if lock:
        statement = statement.with_for_update()
    device = db.scalar(statement)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    return device


@router.get("/{device_id}/summary", response_model=PingSummaryResponse)
def get_ping_summary(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PingSummaryResponse:
    """Return aggregate ping counters and the latest row by monotonic record ID."""
    _device_or_404(db, device_id)

    total_payload = db.scalar(
        select(func.count(PingPayload.id)).where(
            PingPayload.device_id == device_id
        )
    )
    total_missing = db.scalar(
        select(func.count(MissingPingPayload.id)).where(
            MissingPingPayload.device_id == device_id
        )
    )
    latest = db.execute(
        select(
            PingPayload.id,
            PingPayload.order,
            PingPayload.node_timestamp_ms,
        )
        .where(PingPayload.device_id == device_id)
        .order_by(PingPayload.id.desc())
        .limit(1)
    ).one_or_none()

    current_payload = None
    if latest is not None:
        current_payload = PingCurrentPayload(
            id=latest.id,
            order=latest.order,
            timestamp=latest.node_timestamp_ms,
        )
    return PingSummaryResponse(
        device_id=str(device_id),
        total_payload=int(total_payload or 0),
        current_payload=current_payload,
        total_missing_payload=int(total_missing or 0),
    )


@router.delete("/{device_id}", response_model=PingDeleteResponse)
def delete_ping_history(
    device_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PingDeleteResponse:
    """Atomically clear received/missing pings and reset inferred sequence state."""
    _device_or_404(db, device_id, lock=True)
    deleted_missing = db.execute(
        delete(MissingPingPayload).where(
            MissingPingPayload.device_id == device_id
        )
    ).rowcount
    deleted_payloads = db.execute(
        delete(PingPayload).where(PingPayload.device_id == device_id)
    ).rowcount
    db.commit()

    hub = getattr(request.app.state, "realtime_hub", None)
    publish = getattr(hub, "publish_ping_stats_from_thread", None)
    if callable(publish):
        publish(str(device_id), reason="cleared")

    return PingDeleteResponse(
        device_id=str(device_id),
        deleted_payloads=int(deleted_payloads or 0),
        deleted_missing_payloads=int(deleted_missing or 0),
    )
