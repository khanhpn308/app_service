"""
Pipeline nạp dữ liệu cảm biến dùng CHUNG cho mọi nguồn uplink.

Bối cảnh:
    Trước đây chỉ nhánh MQTT subscriber (``main.lifespan``) mới ghi InfluxDB, còn các
    endpoint WebSocket uplink (``/ws/esp32/{id}``, ``/ws/devices/{id}``) chỉ broadcast qua
    RealtimeHub — nên dữ liệu gửi bằng WebSocket hiển thị realtime nhưng KHÔNG bao giờ vào
    InfluxDB. Tập trung hoá tại đây để mọi nguồn (MQTT + WS) đi CÙNG một đường:
        1) ghi InfluxDB (time-series)
        2) broadcast realtime cho dashboard

Dùng ``app.state`` làm nguồn sự thật cho ``influx`` / ``realtime_hub`` (được set trong
``main.lifespan``), tránh vòng import giữa ``main`` và ``websocket_routes``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("uvicorn.error")


def ingest_sensor_payload(app: Any, payload: dict[str, Any]) -> None:
    """
    ISP = Ingest Sensor Payload.

    Công dụng:
        - Ghi payload đã chuẩn hoá vào InfluxDB (nếu service sẵn sàng).
        - Broadcast payload cho các client realtime qua RealtimeHub.

    An toàn:
        - Lỗi ghi Influx không được làm hỏng broadcast (và ngược lại) — mỗi nhánh bọc riêng.
        - Gọi được từ cả thread MQTT lẫn event loop WebSocket (đều dùng ``publish_from_thread``).
    """
    influx = getattr(app.state, "influx", None)
    if influx is not None:
        try:
            influx.write_sensor_point(payload)
        except Exception:  # noqa: BLE001
            logger.exception("ingest: ghi InfluxDB thất bại (device_id=%s)", payload.get("device_id"))

    hub = getattr(app.state, "realtime_hub", None)
    if hub is not None:
        try:
            hub.publish_from_thread(payload)
        except Exception:  # noqa: BLE001
            logger.exception("ingest: broadcast realtime thất bại (device_id=%s)", payload.get("device_id"))
