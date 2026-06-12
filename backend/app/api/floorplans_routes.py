import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/floorplans", tags=["floorplans"])


def get_floorplan_dir() -> str:
    env_path = os.getenv("FLOORPLAN_DIR")
    if env_path and os.path.exists(env_path):
        return os.path.abspath(env_path)

    try:
        current_file = os.path.abspath(__file__)
        api_dir = os.path.dirname(current_file)
        app_dir = os.path.dirname(api_dir)
        backend_dir = os.path.dirname(app_dir)

        path1 = os.path.abspath(os.path.join(backend_dir, "..", "src", "assets", "floorplans"))
        if os.path.exists(path1):
            return path1

        path2 = os.path.abspath(os.path.join(os.getcwd(), "..", "src", "assets", "floorplans"))
        if os.path.exists(path2):
            return path2

        return path1
    except Exception:
        return "../src/assets/floorplans"


@router.get("/{location_name}.webp")
def get_floorplan_webp(location_name: str, user: User = Depends(get_current_user)):
    target_dir = get_floorplan_dir()
    if not target_dir or not os.path.exists(target_dir):
        raise HTTPException(status_code=404, detail="Floorplan directory not found")

    wanted = str(location_name or "").strip()
    # Chống path traversal: từ chối separator và "..".
    if not wanted or "/" in wanted or "\\" in wanted or ".." in wanted:
        raise HTTPException(status_code=404, detail="Floorplan not found")

    wanted_lower = wanted.lower()
    real_dir = os.path.realpath(target_dir)
    for file_name in os.listdir(target_dir):
        if not file_name.lower().endswith(".webp"):
            continue
        stem, _ = os.path.splitext(file_name)
        if stem.lower() == wanted_lower:
            file_path = os.path.join(target_dir, file_name)
            # Xác nhận path đã resolve vẫn nằm trong thư mục cho phép.
            if os.path.commonpath([real_dir, os.path.realpath(file_path)]) != real_dir:
                raise HTTPException(status_code=404, detail="Floorplan not found")
            return FileResponse(
                file_path,
                media_type="image/webp",
                filename=file_name,
                headers={
                    # Allow browser/proxy caching (image content is static)
                    "Cache-Control": "public, max-age=86400",
                },
            )

    raise HTTPException(status_code=404, detail="Floorplan not found")
