"""
WebSocket routes cho dashboard và thiết bị ESP32.

Prefix thực tế khi chạy API là ``/api/ws`` vì router này được include dưới ``/api`` trong ``main``.
"""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.realtime_hub import RealtimeHub

router = APIRouter(prefix="/ws", tags=["websocket"])


def _get_realtime_hub(websocket: WebSocket) -> RealtimeHub | None:
    app = websocket.app
    return getattr(app.state, "realtime_hub", None)

@router.websocket("/esp32/{device_id}")
async def ws_esp32(websocket: WebSocket, device_id: str) -> None:
    """Kết nối realtime cho ESP32 theo ``device_id``.

    Thiết bị có thể gửi text JSON hoặc binary. Server sẽ giữ kết nối mở, phản hồi ping
    và phát lại các message cần thiết qua ``realtime_hub``.
    """
    hub = _get_realtime_hub(websocket)
    if hub is None:
        await websocket.close(code=1011)
        return

    await hub.connect_esp32(websocket, device_id)
    try:
        await websocket.send_json({"ok": True, "device_id": device_id, "message": "connected"})
        while True:
            try:
                message = await websocket.receive()
                raw_text = message.get("text")
                raw_bytes = message.get("bytes")

                if raw_text is None and raw_bytes is None:
                    continue

                if raw_bytes is not None:
                    await websocket.send_json(
                        {
                            "ok": True,
                            "device_id": device_id,
                            "echo_bytes": len(raw_bytes),
                        }
                    )
                    continue

                if not str(raw_text).strip():
                    await websocket.send_json({"ok": True, "type": "pong", "device_id": device_id})
                    continue
                try:
                    payload = json.loads(str(raw_text))
                except json.JSONDecodeError:
                    await websocket.send_json({"ok": True, "device_id": device_id, "echo": str(raw_text)})
                    continue

                await websocket.send_json({"ok": True, "device_id": device_id, "received": payload})
            except WebSocketDisconnect:
                break
    finally:
        await hub.disconnect_esp32(websocket, device_id)