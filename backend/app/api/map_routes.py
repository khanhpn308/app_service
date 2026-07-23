"""REST endpoints for floorplan upload, delivery and archive history."""

from pathlib import PurePosixPath

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.map_access import can_manage_group, can_view_group
from app.core.rate_limit import limiter
from app.core.security import decode_token
from app.core.webp_validator import (
    MAX_WEBP_BYTES,
    WEBP_MIME_TYPE,
    WebPValidationError,
    validate_webp,
)
from app.models.map_group import MapGroup
from app.models.map_location import LocationUsing
from app.models.user import User
from app.schemas.maps import MapPublic

router = APIRouter(tags=["maps"])


def _upload_rate_key(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        try:
            payload = decode_token(authorization[7:].strip())
            identity = payload.get("uid") or payload.get("sub")
            if identity is not None:
                return f"map-upload-user:{identity}"
        except Exception:
            pass
    return f"map-upload-ip:{get_remote_address(request)}"


def _manageable_group_or_404(
    db: Session,
    group_id: int,
    actor: User,
) -> MapGroup:
    group = db.get(MapGroup, group_id)
    if group is None or not can_manage_group(actor, group):
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm")
    return group


def _viewable_group_or_404(
    db: Session,
    group_id: int,
    actor: User,
) -> MapGroup:
    group = db.get(MapGroup, group_id)
    if group is None or not can_view_group(db, actor, group):
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm")
    return group


def _normalize_location(value: str) -> str:
    location = str(value or "").strip()
    if not location:
        raise HTTPException(status_code=422, detail="Location không được để trống")
    if len(location) > 255:
        raise HTTPException(status_code=422, detail="Location không được quá 255 ký tự")
    return location


def _safe_filename(value: str | None) -> str:
    normalized = str(value or "").replace("\\", "/")
    filename = PurePosixPath(normalized).name.strip() or "map.webp"
    if len(filename) > 255:
        raise HTTPException(status_code=422, detail="Tên file không được quá 255 ký tự")
    return filename


def _validation_http_error(error: WebPValidationError) -> HTTPException:
    if error.code == "file_too_large":
        return HTTPException(
            status_code=413,
            detail="Ảnh WebP không được vượt quá 5 MB",
        )
    if error.code == "unsupported_media_type":
        return HTTPException(
            status_code=415,
            detail="Chỉ chấp nhận file WebP",
        )
    messages = {
        "empty_file": "File ảnh đang rỗng",
        "invalid_width": "Chiều rộng ảnh phải đúng 800 pixel",
        "invalid_height": "Chiều cao ảnh phải từ 1 đến 8000 pixel",
        "animated_webp": "Không hỗ trợ ảnh WebP động",
        "invalid_webp": "Nội dung file không phải ảnh WebP hợp lệ",
    }
    return HTTPException(
        status_code=422,
        detail=messages.get(error.code, "Ảnh WebP không hợp lệ"),
    )


def _map_public(row) -> MapPublic:
    return MapPublic(
        location_id=row.location_id,
        location=row.location,
        mime_type=row.mime_type,
        original_filename=row.original_filename,
        checksum_sha256=row.checksum_sha256,
        file_size_bytes=row.file_size_bytes,
        width=row.width,
        height=row.height,
        group_id=row.group_id,
        owner_user_id=row.owner_user_id,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        image_url=f"/api/maps/{row.location_id}/image",
    )


def _map_metadata_columns():
    return (
        LocationUsing.location_id,
        LocationUsing.location,
        LocationUsing.mime_type,
        LocationUsing.original_filename,
        LocationUsing.checksum_sha256,
        LocationUsing.file_size_bytes,
        LocationUsing.width,
        LocationUsing.height,
        LocationUsing.group_id,
        LocationUsing.owner_user_id,
        LocationUsing.created_by_user_id,
        LocationUsing.created_at,
    )


@router.get("/map-groups/{group_id}/maps", response_model=list[MapPublic])
def list_group_maps(
    group_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> list[MapPublic]:
    _viewable_group_or_404(db, group_id, actor)
    rows = db.execute(
        select(*_map_metadata_columns())
        .where(LocationUsing.group_id == group_id)
        .order_by(LocationUsing.location.asc(), LocationUsing.location_id.asc())
    ).all()
    return [_map_public(row) for row in rows]


@router.post(
    "/map-groups/{group_id}/maps",
    response_model=MapPublic,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/hour", key_func=_upload_rate_key)
async def upload_group_map(
    request: Request,
    group_id: int,
    location: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> MapPublic:
    group = _manageable_group_or_404(db, group_id, actor)
    normalized_location = _normalize_location(location)
    duplicate = db.execute(
        select(LocationUsing.location_id).where(
            func.lower(LocationUsing.location) == normalized_location.lower()
        )
    ).first()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Location đang được sử dụng")

    filename = _safe_filename(file.filename)
    content = await file.read(MAX_WEBP_BYTES + 1)
    await file.close()
    try:
        metadata = validate_webp(
            content,
            filename=filename,
            content_type=file.content_type,
        )
    except WebPValidationError as error:
        raise _validation_http_error(error) from error

    active = LocationUsing(
        location=normalized_location,
        image_data=content,
        mime_type=WEBP_MIME_TYPE,
        original_filename=filename,
        checksum_sha256=metadata.checksum_sha256,
        file_size_bytes=metadata.file_size_bytes,
        width=metadata.width,
        height=metadata.height,
        group_id=group.group_id,
        owner_user_id=group.owner_user_id,
        created_by_user_id=actor.user_id,
    )
    db.add(active)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Location đang được sử dụng",
        ) from error
    db.refresh(active)
    return _map_public(active)
