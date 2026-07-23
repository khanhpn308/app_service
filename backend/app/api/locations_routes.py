"""Backward-compatible active location listing backed by MySQL."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.map_access import can_view_group, is_user_active
from app.models.map_group import MapGroup
from app.models.map_location import LocationUsing
from app.models.user import User

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("")
def get_locations(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    if (actor.role or "").lower() == "admin":
        visible_group_ids = select(MapGroup.group_id)
    else:
        if not is_user_active(actor):
            raise HTTPException(status_code=403, detail="Tài khoản không còn hiệu lực")
        groups = db.execute(select(MapGroup).order_by(MapGroup.group_id.asc())).scalars()
        visible_group_ids = [
            group.group_id
            for group in groups
            if can_view_group(db, actor, group)
        ]
    locations = db.execute(
        select(LocationUsing.location)
        .where(LocationUsing.group_id.in_(visible_group_ids))
        .order_by(LocationUsing.location.asc())
    ).scalars()
    return {"data": list(locations)}
