"""
Rate limiting dùng chung (slowapi) — chống brute-force các endpoint nhạy cảm.

Limiter định danh client theo IP (``get_remote_address``). Gắn vào app trong ``main.create_app``;
áp giới hạn cho từng route bằng decorator ``@limiter.limit("5/minute")`` (route phải có tham số
``request: Request``).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
