"""
Endpoint kiểm tra sức khỏe dịch vụ (healthcheck).

Dùng cho load balancer, Kubernetes probe, hoặc giám sát: ``/api/health`` không đụng DB;
``/api/health/db`` chạy ``SELECT 1`` và trả độ trễ.
"""

from fastapi import APIRouter
from fastapi import HTTPException

from app.core.db import db_ping

router = APIRouter()


@router.get("/health")
def health():
    """Trả ``{status: ok}`` nếu process FastAPI đang chạy (không kiểm tra DB)."""
    return {"status": "ok"}


@router.get("/health/db")
def health_db():
    """Kiểm tra kết nối MySQL; 503 nếu không ping được."""
    try:
        latency_ms = db_ping()
        return {"status": "ok", "db": "ok", "db_latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001 — trả lỗi gom nhất cho monitor
        raise HTTPException(status_code=503, detail=f"db unavailable: {exc}") from exc
