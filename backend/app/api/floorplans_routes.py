"""Backward-compatible floorplan delivery backed by MySQL."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.map_access import can_view_group
from app.models.map_group import MapGroup
from app.models.map_location import LocationUsing
from app.models.user import User

router = APIRouter(prefix="/floorplans", tags=["floorplans"])


@router.get("/{location_name}.webp")
def get_floorplan_webp(
    location_name: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> Response:
    wanted = str(location_name or "").strip()
    if not wanted:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản đồ")
    metadata = db.execute(
        select(LocationUsing.location_id, LocationUsing.group_id).where(
            func.lower(LocationUsing.location) == wanted.lower()
        )
    ).one_or_none()
    if metadata is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản đồ")
    group = db.get(MapGroup, metadata.group_id)
    if group is None or not can_view_group(db, actor, group):
        raise HTTPException(status_code=404, detail="Không tìm thấy bản đồ")
    image = db.execute(
        select(LocationUsing.image_data, LocationUsing.mime_type).where(
            LocationUsing.location_id == metadata.location_id
        )
    ).one()
    return Response(
        content=image.image_data,
        media_type=image.mime_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
