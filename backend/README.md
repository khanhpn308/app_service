# Backend (FastAPI)

## Setup virtual environment (Windows PowerShell)

```powershell
cd backend
py -V:3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

MySQL 8 uses `caching_sha2_password` by default; PyMySQL needs the **`cryptography`** package for that (already listed in `requirements.txt`).

## Run dev server

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: `http://localhost:8000/api/health`
DB check: `http://localhost:8000/api/health/db`

## MQTT subscriber

On startup, the API also starts an MQTT subscriber (Mosquitto).

- Status: `http://localhost:8000/api/mqtt/status`
- Latest messages: `http://localhost:8000/api/mqtt/messages?limit=50`
- Topics (admin): `GET /api/mqtt/topics`
- Subscribe topic (admin): `POST /api/mqtt/topics/subscribe`
- Unsubscribe topic (admin): `POST /api/mqtt/topics/unsubscribe`
- History from InfluxDB (30m default): `GET /api/mqtt/history?minutes=30&device_id=101`
- WebSocket global: `ws://localhost:8000/ws/global`
- WebSocket by device: `ws://localhost:8000/ws/devices/{device_id}`

Configure via `.env` (see `.env.example`): `MQTT_HOST`, `MQTT_PORT`, `MQTT_TOPICS`, ...

### Binary payload decode (NanoPB template)

File: `app/core/payload_decoder.py`

- API server decodes MQTT binary payload with a template layout (`_decode_nanopb_template`).
- This is a scaffold only; replace the template parser to match your real `.proto` schema.
- Decoded fields are normalized for storage/realtime: `device_id`, `sensor_type`, `temperature`, `vibration`, `voltage`, `current`, `ts`.

### InfluxDB time-series

API writes decoded sensor points into InfluxDB (`sensor_readings` by default).

Recommended deployment: run InfluxDB in a separate stack (`influxdb_service`) and connect from backend via service name `influxdb` on shared Docker network `iot-net`.

Required env vars:

- `INFLUX_ENABLED`
- `INFLUX_URL`
- `INFLUX_TOKEN`
- `INFLUX_ORG`
- `INFLUX_BUCKET`
- `INFLUX_MEASUREMENT`

### Device topic persistence (DB)

- Bảng `device` có thêm cột `topic` để lưu topic MQTT theo từng thiết bị.
- Khi backend khởi động, hệ thống tự nạp lại các topic này để subscribe runtime.
- Khi admin cập nhật `topic` qua `PATCH /api/devices/{device_id}`, backend sẽ tự đồng bộ subscribe/unsubscribe tương ứng.

## Environment variables

Copy `.env.example` to `.env` and adjust values.

## Default admin account

On startup, the API ensures a built-in admin exists (only if username `AD00000` is not present):

- Username: `AD00000`
- Password: `khanhxx007`

Password is stored hashed (bcrypt). Change the password after deployment.

## First admin (bootstrap)

When the `user` table is empty, create the first admin once:

```http
POST /api/auth/bootstrap
Content-Type: application/json

{
  "username": "admin",
  "password": "your-password",
  "fullname": "Administrator",
  "cccd": "000000000001",
  "email": "admin@example.com",
  "phone": 912345678
}
```

After that, use **Đăng nhập** on the frontend, then admin can create more users under **User Management**.

## MySQL schema (table creation)

When deploying on server, paste your `CREATE TABLE ...` statements into `sql/schema.sql`
and mount it to the MySQL container init directory (see `docker-compose.yml` comment).

Passwords are stored as **bcrypt hashes** (not plaintext). If your `password` column is `VARCHAR(45)`, run the SQL in `sql/002_password_column_for_bcrypt.sql`.
