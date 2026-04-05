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

Configure via `.env` (see `.env.example`): `MQTT_HOST`, `MQTT_PORT`, `MQTT_TOPICS`, ...

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

