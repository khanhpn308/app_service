"""
Service ghi/đọc dữ liệu cảm biến trên InfluxDB.

Mục tiêu:
    - Ghi điểm dữ liệu cảm biến từ MQTT vào InfluxDB (time-series).
    - Truy vấn lịch sử trong N phút gần nhất (mặc định dùng 30 phút cho dashboard).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from influxdb_client import InfluxDBClient, Point, WriteOptions


class InfluxService:
    """Gateway đơn giản cho InfluxDB: viết điểm và query lịch sử theo khoảng thời gian."""

    def __init__(
        self,
        *,
        enabled: bool,
        url: str,
        token: str,
        org: str,
        bucket: str,
        measurement: str,
    ) -> None:
        self._enabled = bool(enabled)
        self._url = url
        self._token = token
        self._org = org
        self._bucket = bucket
        self._measurement = measurement

        self._client: InfluxDBClient | None = None
        self._writer = None

        self._started = False
        self._last_error: str | None = None

    def start(self) -> None:
        """Khởi tạo Influx client + write API (nếu enabled)."""
        if not self._enabled or self._started:
            return
        try:
            self._client = InfluxDBClient(url=self._url, token=self._token, org=self._org)
            self._writer = self._client.write_api(
                write_options=WriteOptions(batch_size=1, flush_interval=1000)
            )
            self._started = True
            self._last_error = None
        except Exception as exc:  # noqa: BLE001
            self._started = False
            self._last_error = str(exc)

    def stop(self) -> None:
        """Đóng writer/client khi shutdown app."""
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:  # noqa: BLE001
                pass
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
        self._started = False

    def status(self) -> dict[str, Any]:
        """Snapshot trạng thái để route debug/health đọc nhanh."""
        return {
            "enabled": self._enabled,
            "started": self._started,
            "url": self._url,
            "org": self._org,
            "bucket": self._bucket,
            "measurement": self._measurement,
            "last_error": self._last_error,
        }

    def write_sensor_point(self, payload: dict[str, Any]) -> None:
        """
        WSP = Write Sensor Point.

        Công dụng:
            - Nhận payload chuẩn hóa và ghi điểm vào InfluxDB.
            - Bỏ qua payload không có trường đo hợp lệ.
        """
        if not self._enabled or not self._started or self._writer is None:
            return

        sensor_type = str(payload.get("sensor_type") or "")
        device_id = str(payload.get("device_id") or "unknown")
        topic = str(payload.get("topic") or "")
        ts = payload.get("ts")

        try:
            ts_dt = datetime.fromtimestamp(float(ts), tz=UTC)
        except Exception:  # noqa: BLE001
            ts_dt = datetime.now(tz=UTC)

        point = (
            Point(self._measurement)
            .tag("device_id", device_id)
            .tag("sensor_type", sensor_type or "unknown")
            .tag("topic", topic)
            .time(ts_dt)
        )

        wrote = False
        for field_name in ("temperature", "vibration", "voltage", "current"):
            value = payload.get(field_name)
            if value is None:
                continue
            try:
                point = point.field(field_name, float(value))
                wrote = True
            except Exception:  # noqa: BLE001
                continue

        # Lưu raw payload để debug/truy vết khi cần.
        point = point.field("raw_json", json.dumps(payload.get("raw", {}), ensure_ascii=False))

        if not wrote:
            return

        try:
            self._writer.write(bucket=self._bucket, org=self._org, record=point)
            self._last_error = None
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc)

    def query_history(self, *, minutes: int = 30, device_id: str | None = None) -> list[dict[str, Any]]:
        """
        QRY = Query Recent historY.

        Công dụng:
            - Truy vấn dữ liệu cảm biến trong ``minutes`` phút gần nhất.
            - Có thể lọc theo ``device_id`` cho dashboard chi tiết.
        """
        if not self._enabled or not self._started or self._client is None:
            return []

        minutes = max(1, min(int(minutes), 180))
        filter_device = ""
        if device_id:
            safe_device_id = json.dumps(str(device_id))
            filter_device = f"\n  |> filter(fn: (r) => r.device_id == {safe_device_id})"

        query = f'''
from(bucket: {json.dumps(self._bucket)})
  |> range(start: -{minutes}m)
  |> filter(fn: (r) => r._measurement == {json.dumps(self._measurement)}){filter_device}
  |> filter(fn: (r) => r._field == "temperature" or r._field == "vibration" or r._field == "voltage" or r._field == "current")
  |> pivot(rowKey:["_time", "device_id", "sensor_type", "topic"], columnKey:["_field"], valueColumn:"_value")
  |> sort(columns:["_time"], desc: false)
'''

        try:
            rows = self._client.query_api().query(org=self._org, query=query)
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc)
            return []

        out: list[dict[str, Any]] = []
        for table in rows:
            for rec in table.records:
                values = rec.values
                t = rec.get_time()
                out.append(
                    {
                        "ts": t.timestamp() if t else None,
                        "ts_iso": t.isoformat() if t else None,
                        "device_id": str(values.get("device_id") or ""),
                        "sensor_type": str(values.get("sensor_type") or ""),
                        "topic": str(values.get("topic") or ""),
                        "temperature": values.get("temperature"),
                        "vibration": values.get("vibration"),
                        "voltage": values.get("voltage"),
                        "current": values.get("current"),
                    }
                )

        return out
