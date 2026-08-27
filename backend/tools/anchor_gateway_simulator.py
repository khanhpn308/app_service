"""Small MQTT Gateway simulator for Anchor configuration smoke/integration tests."""

from __future__ import annotations

import argparse
import json
import queue
import threading
import uuid
from typing import Any

import paho.mqtt.client as mqtt


class AnchorGatewaySimulator:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        gateway_id: int,
        location_id: int,
        location: str,
        down_topic: str,
        up_topic: str,
        reject: bool = False,
        username: str | None = None,
        password: str | None = None,
    ):
        self.host = host
        self.port = int(port)
        self.gateway_id = int(gateway_id)
        self.location_id = int(location_id)
        self.location = location.strip()
        self.down_topic = down_topic.strip()
        self.up_topic = up_topic.strip()
        self.reject = reject
        self.latest_revision = 0
        self.anchors: list[dict[str, Any]] = []
        self._connected = threading.Event()
        self._acks: queue.Queue[dict[str, Any]] = queue.Queue()
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"anchor-gateway-simulator-{gateway_id}-{uuid.uuid4().hex[:8]}",
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        if username:
            self._client.username_pw_set(username, password)

    def start(self, timeout: float = 5) -> None:
        self._client.connect(self.host, self.port, 30)
        self._client.loop_start()
        if not self._connected.wait(timeout):
            self.stop()
            raise TimeoutError("Gateway simulator could not connect to MQTT broker")

    def stop(self) -> None:
        self._client.loop_stop()
        try:
            self._client.disconnect()
        except Exception:
            pass

    def wait_for_ack(self, timeout: float = 5) -> dict[str, Any]:
        return self._acks.get(timeout=timeout)

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties) -> None:
        if int(getattr(reason_code, "value", reason_code)) != 0:
            return
        client.subscribe(self.down_topic, qos=1)
        self._connected.set()

    def _on_message(self, client, _userdata, message) -> None:
        error = None
        status = "applied"
        revision = 0
        try:
            payload = json.loads(bytes(message.payload).decode("utf-8"))
            revision = int(payload["revision"])
            if payload.get("schema") != "anchor_config.v1" or payload.get("operation") != "replace":
                raise ValueError("unsupported schema or operation")
            if int(payload.get("location_id")) != self.location_id or str(payload.get("location", "")).strip().casefold() != self.location.casefold():
                raise ValueError("location mismatch")
            anchors = payload.get("anchors")
            if not isinstance(anchors, list):
                raise ValueError("anchors must be an array")
            if self.reject:
                raise ValueError("simulated rejection")
            if revision >= self.latest_revision:
                self.latest_revision = revision
                self.anchors = anchors
        except Exception as exc:
            status = "rejected"
            error = str(exc)[:500]
        ack = {
            "type": "anchor_config_ack",
            "schema": "anchor_config_ack.v1",
            "gateway_id": self.gateway_id,
            "location_id": self.location_id,
            "location": self.location,
            "revision": revision,
            "status": status,
            "error": error,
        }
        info = client.publish(
            self.up_topic,
            json.dumps(ack, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            qos=1,
            retain=False,
        )
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            self._acks.put(ack)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--gateway-id", type=int, required=True)
    parser.add_argument("--location-id", type=int, required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--down-topic", required=True)
    parser.add_argument("--up-topic", required=True)
    parser.add_argument("--reject", action="store_true")
    parser.add_argument("--username")
    parser.add_argument("--password")
    args = parser.parse_args()
    simulator = AnchorGatewaySimulator(
        host=args.host,
        port=args.port,
        gateway_id=args.gateway_id,
        location_id=args.location_id,
        location=args.location,
        down_topic=args.down_topic,
        up_topic=args.up_topic,
        reject=args.reject,
        username=args.username,
        password=args.password,
    )
    simulator.start()
    print("Gateway simulator connected. Press Ctrl+C to stop.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        simulator.stop()


if __name__ == "__main__":
    main()
