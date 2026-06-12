#!/usr/bin/env bash
# Sinh secret mạnh cho deploy production. Chạy 1 lần, dán kết quả vào các file .env tương ứng.
# KHÔNG commit output.
#
# Lưu ý: INFLUX_TOKEN phải khớp giữa app_service/.env và influxdb_service/.env, NHƯNG
# nên là token sinh trong InfluxDB UI (Data > API Tokens) với scope tối thiểu, không
# tái dùng admin token. Giá trị dưới chỉ dùng cho lần init đầu của influx (admin token).
set -euo pipefail

echo "# === Dán vào app_service/.env ==="
echo "JWT_SECRET=$(openssl rand -hex 32)"
echo
echo "# === Dán vào database_service/.env (đồng bộ DB_PASSWORD bên app_service/.env) ==="
echo "MYSQL_ROOT_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)"
APP_DB_PWD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
echo "MYSQL_PASSWORD=${APP_DB_PWD}"
echo "# app_service/.env: DB_PASSWORD=${APP_DB_PWD}"
echo
echo "# === InfluxDB admin token (init lần đầu) — đồng bộ 2 file ==="
echo "INFLUX_TOKEN=$(openssl rand -hex 32)"
echo
echo "# === MQTT credential (đặt vào app_service/.env: MQTT_USERNAME / MQTT_PASSWORD) ==="
echo "MQTT_USERNAME=iot-backend"
echo "MQTT_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | head -c 24)"
