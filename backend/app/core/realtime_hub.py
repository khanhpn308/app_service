"""
Realtime hub cho WebSocket: broadcast dữ liệu MQTT đã chuẩn hóa tới frontend.

Kênh hỗ trợ:
    - Global dashboard: ``/ws/global``
    - Device dashboard: ``/ws/devices/{device_id}``
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class RealtimeHub:
    """Quản lý kết nối WebSocket và phát dữ liệu realtime theo scope global/device."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[dict[str, Any]] | None = None
        self._worker_task: asyncio.Task | None = None

        self._global_clients: set[WebSocket] = set()
        self._device_clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Khởi tạo event loop state và worker tiêu thụ queue broadcast."""
        if self._worker_task is not None:
            return
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._worker_task = asyncio.create_task(self._broadcast_worker())

    async def stop(self) -> None:
        """Dừng worker và đóng mọi kết nối WebSocket còn mở."""
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        async with self._lock:
            all_ws = set(self._global_clients)
            for group in self._device_clients.values():
                all_ws.update(group)
            self._global_clients.clear()
            self._device_clients.clear()

        for ws in all_ws:
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass

    async def connect_global(self, websocket: WebSocket) -> None:
        """Accept kết nối và thêm vào nhóm global dashboard."""
        await websocket.accept()
        async with self._lock:
            self._global_clients.add(websocket)

    async def connect_device(self, websocket: WebSocket, device_id: str) -> None:
        """Accept kết nối và thêm vào nhóm dashboard của một thiết bị."""
        await websocket.accept()
        key = str(device_id)
        async with self._lock:
            self._device_clients[key].add(websocket)

    async def disconnect_global(self, websocket: WebSocket) -> None:
        """Gỡ kết nối khỏi nhóm global khi client ngắt."""
        async with self._lock:
            self._global_clients.discard(websocket)

    async def disconnect_device(self, websocket: WebSocket, device_id: str) -> None:
        """Gỡ kết nối khỏi nhóm device khi client ngắt."""
        key = str(device_id)
        async with self._lock:
            group = self._device_clients.get(key)
            if not group:
                return
            group.discard(websocket)
            if not group:
                self._device_clients.pop(key, None)

    def publish_from_thread(self, message: dict[str, Any]) -> None:
        """
        PFT = Publish From Thread.

        Công dụng:
            - Nhận dữ liệu từ callback MQTT (thread nền paho) và đẩy vào queue asyncio.
        """
        if self._loop is None or self._queue is None:
            return

        def _push() -> None:
            if self._queue is None:
                return
            self._queue.put_nowait(message)

        self._loop.call_soon_threadsafe(_push)

    async def _broadcast_worker(self) -> None:
        """Worker vòng lặp vô hạn: đọc queue rồi broadcast cho global + đúng device_id."""
        if self._queue is None:
            return

        while True:
            msg = await self._queue.get()
            device_id = str(msg.get("device_id") or "")

            async with self._lock:
                targets = set(self._global_clients)
                if device_id and device_id in self._device_clients:
                    targets.update(self._device_clients[device_id])

            stale: list[WebSocket] = []
            for ws in targets:
                try:
                    await ws.send_json(msg)
                except Exception:  # noqa: BLE001
                    stale.append(ws)

            if stale:
                async with self._lock:
                    for ws in stale:
                        self._global_clients.discard(ws)
                    for key, group in list(self._device_clients.items()):
                        for ws in stale:
                            group.discard(ws)
                        if not group:
                            self._device_clients.pop(key, None)
