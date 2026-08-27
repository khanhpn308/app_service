import json
import os
import threading
import uuid

import paho.mqtt.client as mqtt
import pytest

from tools.anchor_gateway_simulator import AnchorGatewaySimulator


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MQTT_INTEGRATION") != "1",
    reason="set RUN_MQTT_INTEGRATION=1 with a local Mosquitto broker",
)


def test_retained_qos1_snapshot_is_applied_and_acked():
    host = os.getenv("MQTT_TEST_HOST", "localhost")
    port = int(os.getenv("MQTT_TEST_PORT", "1883"))
    suffix = uuid.uuid4().hex
    down = f"codex-test/{suffix}/down"
    up = f"codex-test/{suffix}/up"
    simulator = AnchorGatewaySimulator(
        host=host, port=port, gateway_id=9101, location_id=12,
        location="Floor_1", down_topic=down, up_topic=up,
        username=os.getenv("MQTT_TEST_USERNAME"),
        password=os.getenv("MQTT_TEST_PASSWORD"),
    )
    simulator.start()
    publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"publisher-{suffix}")
    if os.getenv("MQTT_TEST_USERNAME"):
        publisher.username_pw_set(os.getenv("MQTT_TEST_USERNAME"), os.getenv("MQTT_TEST_PASSWORD"))
    publisher.connect(host, port, 30)
    publisher.loop_start()
    payload = {
        "schema": "anchor_config.v1", "operation": "replace",
        "location_id": 12, "location": "Floor_1", "revision": 7,
        "generated_at": "2026-08-08T10:00:00Z", "anchors": [],
    }
    info = publisher.publish(down, json.dumps(payload).encode(), qos=1, retain=True)
    info.wait_for_publish(timeout=5)
    ack = simulator.wait_for_ack(timeout=5)
    assert ack["schema"] == "anchor_config_ack.v1"
    assert (ack["revision"], ack["status"]) == (7, "applied")

    retained = {}
    ready = threading.Event()
    probe = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"probe-{suffix}")
    if os.getenv("MQTT_TEST_USERNAME"):
        probe.username_pw_set(os.getenv("MQTT_TEST_USERNAME"), os.getenv("MQTT_TEST_PASSWORD"))

    def on_message(_client, _userdata, message):
        retained["flag"] = message.retain
        retained["payload"] = json.loads(message.payload)
        ready.set()

    probe.on_message = on_message
    probe.connect(host, port, 30)
    probe.subscribe(down, qos=1)
    probe.loop_start()
    assert ready.wait(5)
    assert retained["flag"] is True
    assert retained["payload"]["revision"] == 7

    probe.loop_stop()
    probe.disconnect()
    simulator.reject = True
    rejected_payload = {**payload, "revision": 8}
    publisher.publish(down, json.dumps(rejected_payload).encode(), qos=1, retain=True).wait_for_publish(timeout=5)
    rejected = simulator.wait_for_ack(timeout=5)
    assert (rejected["revision"], rejected["status"]) == (8, "rejected")
    assert rejected["error"] == "simulated rejection"
    publisher.publish(down, payload=b"", qos=1, retain=True).wait_for_publish(timeout=5)
    publisher.loop_stop()
    publisher.disconnect()
    simulator.stop()
