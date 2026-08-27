"""Gateway targeting, durable MQTT delivery, ACK handling and sync aggregation."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.anchor import Anchor, AnchorConfigDelivery, AnchorConfigOutbox
from app.models.device import Device
from app.models.map_location import LocationUsing
from app.models.user import User

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _canonical(value: str | None) -> str:
    return str(value or "").strip().casefold()


def matching_gateways(db: Session, location: str) -> list[Device]:
    target = _canonical(location)
    return [
        row
        for row in db.query(Device)
        .filter(func.lower(Device.device_type) == "gateway", func.lower(Device.status) == "active")
        .order_by(Device.device_id.asc())
        .all()
        if _canonical(row.location) == target
    ]


def gateway_publish_topic_in_use(db: Session, gateway: Device) -> bool:
    topic = _canonical(gateway.publish_topic)
    if (
        not topic
        or _canonical(gateway.device_type) != "gateway"
        or _canonical(gateway.status) != "active"
    ):
        return False
    return db.query(Device).filter(
        Device.device_id != gateway.device_id,
        func.lower(func.trim(Device.device_type)) == "gateway",
        func.lower(func.trim(Device.status)) == "active",
        func.lower(func.trim(Device.publish_topic)) == topic,
    ).first() is not None


def bootstrap_gateway_configuration(
    db: Session,
    gateway: Device,
    actor: User,
) -> AnchorConfigOutbox | None:
    if (
        _canonical(gateway.device_type) != "gateway"
        or _canonical(gateway.status) != "active"
        or not _canonical(gateway.location)
    ):
        return None
    location = db.query(LocationUsing).filter(
        func.lower(func.trim(LocationUsing.location)) == _canonical(gateway.location)
    ).first()
    if location is None:
        return None
    from app.services.anchor_service import bootstrap_gateway

    return bootstrap_gateway(db, location, actor, gateway.device_id)


def _anchor_state_payload(anchor: Anchor) -> dict:
    return {
        "id": anchor.anchor_id,
        "mac_address": anchor.mac_address,
        "name": anchor.name,
        "x": float(anchor.x),
        "y": float(anchor.y),
        "z": float(anchor.z),
    }


def _compose_gateway_payload(
    db: Session,
    outbox: AnchorConfigOutbox,
    gateway_id: int,
) -> dict:
    applied_revision = db.query(func.max(AnchorConfigDelivery.revision)).filter(
        AnchorConfigDelivery.gateway_id == gateway_id,
        AnchorConfigDelivery.status == "applied",
    ).scalar()
    if applied_revision is None:
        active = (
            db.query(Anchor)
            .filter(
                Anchor.location_id == outbox.location_id,
                Anchor.status == "active",
            )
            .order_by(Anchor.anchor_id.asc())
            .all()
        )
        operation = "replace"
        anchors = [_anchor_state_payload(anchor) for anchor in active]
    else:
        events = (
            db.query(AnchorConfigOutbox)
            .filter(
                AnchorConfigOutbox.location_id == outbox.location_id,
                AnchorConfigOutbox.revision > applied_revision,
                AnchorConfigOutbox.revision <= outbox.revision,
                or_(
                    AnchorConfigOutbox.target_gateway_id.is_(None),
                    AnchorConfigOutbox.target_gateway_id == gateway_id,
                ),
            )
            .order_by(AnchorConfigOutbox.revision.asc())
            .all()
        )
        operation = "delta"
        changes: dict[int, dict] = {}
        state: dict[int, dict] | None = None
        for event in events:
            event_operation = str(event.payload.get("operation") or "replace")
            event_anchors = list(event.payload.get("anchors") or [])
            if event_operation == "replace":
                operation = "replace"
                state = {int(item["id"]): dict(item) for item in event_anchors}
                changes.clear()
                continue
            for item in event_anchors:
                anchor_id = int(item["id"])
                if state is not None:
                    if item.get("action") == "delete":
                        state.pop(anchor_id, None)
                    else:
                        state[anchor_id] = {
                            key: value for key, value in item.items() if key != "action"
                        }
                else:
                    changes[anchor_id] = dict(item)
        anchors = (
            [state[key] for key in sorted(state)]
            if state is not None
            else [changes[key] for key in sorted(changes)]
        )
    return {
        "schema": "anchor_config.v1",
        "operation": operation,
        "gateway_id": gateway_id,
        "location_id": outbox.location_id,
        "location": outbox.location,
        "revision": outbox.revision,
        "generated_at": outbox.payload.get("generated_at"),
        "anchors": anchors,
    }


def reconcile_latest_snapshot(
    db: Session, outbox: AnchorConfigOutbox
) -> list[AnchorConfigDelivery]:
    """Ensure every currently matching active gateway has one delivery."""
    existing = {
        row.gateway_id: row
        for row in db.query(AnchorConfigDelivery)
        .filter(AnchorConfigDelivery.revision == outbox.revision)
        .all()
    }
    rows: list[AnchorConfigDelivery] = []
    changed = False
    gateways = matching_gateways(db, outbox.location)
    if outbox.target_gateway_id is not None:
        gateways = [
            gateway for gateway in gateways
            if gateway.device_id == outbox.target_gateway_id
        ]
    topic_counts = Counter(
        str(gateway.publish_topic or "").strip()
        for gateway in matching_gateways(db, outbox.location)
        if str(gateway.publish_topic or "").strip()
    )
    matching_ids = {gateway.device_id for gateway in gateways}
    for gateway in gateways:
        topic = str(gateway.publish_topic or "").strip() or None
        duplicate_topic = bool(topic and topic_counts[topic] > 1)
        delivery_error = (
            "duplicate_gateway_publish_topic"
            if duplicate_topic
            else ("missing_gateway_publish_topic" if not topic else None)
        )
        deliverable = bool(topic and not duplicate_topic)
        payload = _compose_gateway_payload(db, outbox, gateway.device_id)
        db.query(AnchorConfigDelivery).filter(
            AnchorConfigDelivery.gateway_id == gateway.device_id,
            AnchorConfigDelivery.revision < outbox.revision,
            AnchorConfigDelivery.status.in_(("pending", "published", "misconfigured")),
        ).update(
            {
                "status": "superseded",
                "next_attempt_at": None,
                "leased_by": None,
                "lease_until": None,
            },
            synchronize_session=False,
        )
        delivery = existing.get(gateway.device_id)
        if delivery is None:
            delivery = AnchorConfigDelivery(
                revision=outbox.revision,
                gateway_id=gateway.device_id,
                publish_topic=topic,
                payload=payload,
                status="pending" if deliverable else "misconfigured",
                last_error=delivery_error,
            )
            db.add(delivery)
            changed = True
        elif delivery.status not in {"applied", "rejected", "superseded"}:
            if delivery.payload is None:
                delivery.payload = payload
            if not deliverable and (
                delivery.publish_topic != topic
                or delivery.status != "misconfigured"
                or delivery.last_error != delivery_error
            ):
                changed = True
                delivery.publish_topic = topic
                delivery.status = "misconfigured"
                delivery.next_attempt_at = None
                delivery.last_error = delivery_error
            elif deliverable and (
                delivery.publish_topic != topic
                or delivery.status == "misconfigured"
            ):
                changed = True
                delivery.publish_topic = topic
                delivery.status = "pending"
                delivery.next_attempt_at = None
                delivery.last_error = None
        elif delivery.status != "superseded" and delivery.publish_topic != topic:
            delivery.publish_topic = topic
            delivery.status = "pending" if topic else "misconfigured"
            delivery.next_attempt_at = None
            delivery.acked_at = None
            delivery.last_error = None
            changed = True
        rows.append(delivery)
    for gateway_id, delivery in existing.items():
        if gateway_id not in matching_ids and delivery.status not in {
            "applied",
            "rejected",
            "superseded",
        }:
            delivery.status = "superseded"
            delivery.next_attempt_at = None
            delivery.leased_by = None
            delivery.lease_until = None
            changed = True
    if changed:
        outbox.status = "pending"
        outbox.completed_at = None
    db.flush()
    return rows


def _latest_outbox_for_location_name(db: Session, location: str) -> AnchorConfigOutbox | None:
    target = _canonical(location)
    return (
        db.query(AnchorConfigOutbox)
        .filter(func.lower(func.trim(AnchorConfigOutbox.location)) == target)
        .order_by(AnchorConfigOutbox.revision.desc())
        .first()
    )


def reconcile_gateway_change(
    db: Session,
    gateway: Device,
    *,
    old_location: str | None = None,
) -> None:
    """Reconcile the latest snapshots after an admin changes a Gateway row."""
    if old_location:
        old = _latest_outbox_for_location_name(db, old_location)
        if old is not None and (
            _canonical(old_location) != _canonical(gateway.location)
            or _canonical(gateway.status) != "active"
            or _canonical(gateway.device_type) != "gateway"
        ):
            db.query(AnchorConfigDelivery).filter(
                AnchorConfigDelivery.revision == old.revision,
                AnchorConfigDelivery.gateway_id == gateway.device_id,
                AnchorConfigDelivery.status != "applied",
            ).update({"status": "superseded"}, synchronize_session=False)
    if (
        _canonical(gateway.device_type) == "gateway"
        and _canonical(gateway.status) == "active"
        and _canonical(gateway.location)
    ):
        latest = _latest_outbox_for_location_name(db, gateway.location)
        if latest is not None:
            reconcile_latest_snapshot(db, latest)


def reconcile_pending_locations(db: Session) -> int:
    """Periodic reconciliation also covers Gateways added after a completed snapshot."""
    latest_revisions = (
        db.query(func.max(AnchorConfigOutbox.revision))
        .group_by(AnchorConfigOutbox.location_id)
        .subquery()
    )
    latest_rows = db.query(AnchorConfigOutbox).filter(
        AnchorConfigOutbox.revision.in_(db.query(latest_revisions.c[0]))
    ).all()
    before = db.query(AnchorConfigDelivery).count()
    for outbox in latest_rows:
        reconcile_latest_snapshot(db, outbox)
    db.flush()
    return db.query(AnchorConfigDelivery).count() - before


def _refresh_outbox_status(db: Session, revision: int, now: datetime) -> None:
    outbox = db.get(AnchorConfigOutbox, revision)
    if outbox is None or outbox.status == "superseded":
        return
    states = [
        state
        for (state,) in db.query(AnchorConfigDelivery.status)
        .filter(AnchorConfigDelivery.revision == revision)
        .all()
    ]
    if states and any(state == "rejected" for state in states):
        outbox.status = "failed"
        outbox.completed_at = _naive(now)
    elif states and all(state == "applied" for state in states):
        outbox.status = "completed"
        outbox.completed_at = _naive(now)
    else:
        outbox.status = "pending"
        outbox.completed_at = None


def apply_gateway_ack(
    db: Session,
    *,
    gateway_id: int,
    location_id: int,
    revision: int,
    status: str,
    error: str | None,
    now: datetime | None = None,
) -> bool:
    """Apply a validated ACK idempotently; stale revisions never affect the latest one."""
    if status not in {"applied", "rejected"}:
        return False
    outbox = db.get(AnchorConfigOutbox, int(revision))
    if outbox is None or outbox.location_id != int(location_id):
        return False
    delivery = (
        db.query(AnchorConfigDelivery)
        .filter(
            AnchorConfigDelivery.revision == int(revision),
            AnchorConfigDelivery.gateway_id == int(gateway_id),
        )
        .one_or_none()
    )
    if delivery is None:
        return False
    observed = now or utcnow()
    if delivery.status == "superseded":
        delivery.acked_at = _naive(observed)
        detail = f"stale_ack:{status}"
        if error:
            detail = f"{detail}: {str(error).strip()}"
        delivery.last_error = detail[:500]
        return True
    if delivery.status in {"applied", "rejected"}:
        # Idempotent ACKs also repair a stale parent aggregate left by an older
        # process or interrupted rollout.
        _refresh_outbox_status(db, int(revision), observed)
        return True
    delivery.status = status
    delivery.acked_at = _naive(observed)
    delivery.last_error = (str(error).strip()[:500] or None) if error else None
    # SessionLocal disables autoflush in production. Persist the delivery transition
    # before the aggregate query so the parent outbox sees applied/rejected immediately.
    db.flush([delivery])
    _refresh_outbox_status(db, int(revision), observed)
    return True


def handle_gateway_uplink(
    db: Session,
    payload: dict,
    *,
    mqtt_topic: str | None = None,
    authenticated_gateway_id: int | None = None,
    now: datetime | None = None,
) -> bool:
    """Validate an external MQTT/WS ACK before it reaches delivery state."""
    if payload.get("type") != "anchor_config_ack" or payload.get("schema") != "anchor_config_ack.v1":
        return False
    try:
        gateway_id = int(payload["gateway_id"])
        location_id = int(payload["location_id"])
        revision = int(payload["revision"])
    except (KeyError, TypeError, ValueError):
        return False
    if authenticated_gateway_id is not None and gateway_id != int(authenticated_gateway_id):
        return False
    gateway = db.get(Device, gateway_id)
    if (
        gateway is None
        or _canonical(gateway.device_type) != "gateway"
        or _canonical(gateway.status) != "active"
    ):
        return False
    if mqtt_topic is not None and str(gateway.topic or "").strip() != str(mqtt_topic).strip():
        return False
    outbox = db.get(AnchorConfigOutbox, revision)
    if (
        outbox is None
        or outbox.location_id != location_id
        or _canonical(outbox.location) != _canonical(payload.get("location"))
        or _canonical(gateway.location) != _canonical(outbox.location)
    ):
        return False
    return apply_gateway_ack(
        db,
        gateway_id=gateway_id,
        location_id=location_id,
        revision=revision,
        status=str(payload.get("status") or ""),
        error=payload.get("error"),
        now=now,
    )


def get_location_sync_status(
    db: Session,
    location: LocationUsing,
    *,
    now: datetime | None = None,
    offline_after_seconds: int = 30,
) -> dict:
    observed = now or utcnow()
    gateways = matching_gateways(db, location.location)
    latest = (
        db.query(AnchorConfigOutbox)
        .filter(AnchorConfigOutbox.location_id == location.location_id)
        .order_by(AnchorConfigOutbox.revision.desc())
        .first()
    )
    revision = latest.revision if latest else None
    result_gateways = []
    for gateway in gateways:
        delivery = (
            db.query(AnchorConfigDelivery)
            .join(
                AnchorConfigOutbox,
                AnchorConfigOutbox.revision == AnchorConfigDelivery.revision,
            )
            .filter(
                AnchorConfigDelivery.gateway_id == gateway.device_id,
                AnchorConfigOutbox.location_id == location.location_id,
            )
            .order_by(AnchorConfigDelivery.revision.desc())
            .first()
        )
        applied_revision = db.query(func.max(AnchorConfigDelivery.revision)).filter(
            AnchorConfigDelivery.gateway_id == gateway.device_id,
            AnchorConfigDelivery.status == "applied",
        ).scalar()
        last_seen = gateway.last_seen_at
        aware = last_seen.replace(tzinfo=timezone.utc) if last_seen and last_seen.tzinfo is None else last_seen
        online = bool(aware and observed - aware <= timedelta(seconds=offline_after_seconds))
        result_gateways.append(
            {
                "gateway_id": gateway.device_id,
                "devicename": gateway.devicename,
                "online": online,
                "last_seen_at": aware,
                "target_revision": delivery.revision if delivery else None,
                "applied_revision": applied_revision,
                "delivery_status": delivery.status if delivery else ("misconfigured" if not gateway.publish_topic else "pending"),
                "error": delivery.last_error if delivery else None,
            }
        )
    states = [row["delivery_status"] for row in result_gateways]
    if not result_gateways:
        aggregate = "no_gateway"
    elif any(state in {"rejected", "misconfigured"} for state in states):
        aggregate = "error"
    elif states and all(state == "applied" for state in states):
        aggregate = "synced"
    elif any(state == "applied" for state in states):
        aggregate = "partial"
    else:
        aggregate = "pending"
    return {
        "location_id": location.location_id,
        "location": location.location,
        "revision": revision,
        "aggregate": aggregate,
        "anchor_count": db.query(Anchor).filter(Anchor.location_id == location.location_id, Anchor.status == "active").count(),
        "gateways": result_gateways,
    }


class AnchorDispatcher:
    """Small durable dispatcher; one process claims due rows using a database lease."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        publish: Callable[[str, bytes], bool],
        retry_schedule: Iterable[int] = (5, 15, 30, 60, 300),
        retry_steady: int = 300,
        lease_seconds: int = 30,
        poll_seconds: float = 1.0,
    ):
        self._session_factory = session_factory
        self._publish = publish
        self._retries = tuple(max(1, int(value)) for value in retry_schedule) or (5,)
        self._steady = max(1, int(retry_steady))
        self._lease = timedelta(seconds=max(1, int(lease_seconds)))
        self._poll = max(0.1, float(poll_seconds))
        self._worker_id = f"anchor-dispatcher-{uuid.uuid4()}"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="anchor-dispatcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=max(2.0, self._poll + 1.0))

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("Anchor dispatcher iteration failed")
            self._stop.wait(self._poll)

    def run_once(self, *, now: datetime | None = None) -> int:
        observed = now or utcnow()
        naive_now = _naive(observed)
        db = self._session_factory()
        try:
            reconcile_pending_locations(db)
            db.commit()
            due = (
                db.query(AnchorConfigDelivery)
                .filter(
                    AnchorConfigDelivery.status.in_(("pending", "published")),
                    or_(AnchorConfigDelivery.next_attempt_at.is_(None), AnchorConfigDelivery.next_attempt_at <= naive_now),
                    or_(AnchorConfigDelivery.lease_until.is_(None), AnchorConfigDelivery.lease_until <= naive_now),
                )
                .order_by(AnchorConfigDelivery.revision.asc(), AnchorConfigDelivery.delivery_id.asc())
                .with_for_update(skip_locked=True)
                .all()
            )
            for row in due:
                row.leased_by = self._worker_id
                row.lease_until = naive_now + self._lease
            db.commit()
            grouped: dict[tuple[int, str, str], list[AnchorConfigDelivery]] = defaultdict(list)
            for row in due:
                if row.publish_topic:
                    encoded = json.dumps(
                        row.payload, ensure_ascii=False, separators=(",", ":")
                    )
                    grouped[(row.revision, row.publish_topic, encoded)].append(row)
            published = 0
            for (revision, topic, encoded), rows in grouped.items():
                outbox = db.get(AnchorConfigOutbox, revision)
                if outbox is None or outbox.status == "superseded":
                    for row in rows:
                        row.status = "superseded"
                    continue
                payload = encoded.encode("utf-8")
                success = bool(self._publish(topic, payload))
                for row in rows:
                    row.attempt_count += 1
                    row.leased_by = None
                    row.lease_until = None
                    if success:
                        row.status = "published"
                        row.published_at = naive_now
                        delay = (
                            self._retries[min(row.attempt_count - 1, len(self._retries) - 1)]
                            if row.attempt_count <= len(self._retries)
                            else self._steady
                        )
                        row.next_attempt_at = naive_now + timedelta(seconds=delay)
                        row.last_error = None
                        published += 1
                    else:
                        delay = self._retries[min(row.attempt_count - 1, len(self._retries) - 1)] if row.attempt_count <= len(self._retries) else self._steady
                        row.next_attempt_at = naive_now + timedelta(seconds=delay)
                        row.last_error = "MQTT publish failed"
            db.commit()
            return published
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
