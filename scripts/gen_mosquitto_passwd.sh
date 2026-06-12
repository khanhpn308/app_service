#!/usr/bin/env bash
# Tạo file mosquitto/passwd (đã hash) từ MQTT_USERNAME/MQTT_PASSWORD.
# Chạy tại thư mục app_service. File output: app_service/mosquitto/passwd (đã .gitignore).
set -euo pipefail

USER="${1:-${MQTT_USERNAME:-iot-backend}}"
PASS="${2:-${MQTT_PASSWORD:?Đặt MQTT_PASSWORD hoặc truyền arg thứ 2}}"

mkdir -p mosquitto
docker run --rm -v "$(pwd)/mosquitto:/m" eclipse-mosquitto:2.0 \
  mosquitto_passwd -b -c /m/passwd "$USER" "$PASS"

echo "Đã tạo mosquitto/passwd cho user '$USER'."
echo "Thêm device ESP32 (mỗi thiết bị 1 credential) bằng: mosquitto_passwd -b /m/passwd <device-user> <device-pass>"
