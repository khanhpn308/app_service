"""
Cấu hình tập trung (đọc từ biến môi trường và file ``.env``).

Thư viện: **Pydantic Settings** — validate kiểu và tên biến. Instance singleton ``settings`` dùng xuyên suốt app.

Viết tắt:
    - **JWT**: JSON Web Token — cấu hình ``jwt_*`` (secret không commit lên git).
    - **MQTT**: broker IoT — ``mqtt_*`` cho subscriber nền.

Lưu ý ``settings_customise_sources``: thứ tự nguồn cấu hình được sắp để **biến môi trường container**
ghi đè ``.env`` khi deploy (Docker/K8s).
"""

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """
    Một class = một bộ cấu hình runtime.

    Thuộc tính viết ``snake_case`` khớp tên biến môi trường (không phân biệt hoa thường theo quy ước Pydantic v2).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Nguồn sau ghi đè nguồn trước. .env không được thắng env Docker; env phải thắng file secret mặc định.
        return (
            init_settings,
            dotenv_settings,
            file_secret_settings,
            env_settings,
        )

    app_name: str = "IoT Backend API"
    environment: str = "dev"
    cors_origins: str = "http://localhost:3000"
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "CHANGE_ME"
    db_name: str = "iot"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    # MQTT subscriber (ví dụ Mosquitto)
    mqtt_enabled: bool = True
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_client_id: str = "iot-backend-subscriber"
    mqtt_keepalive: int = 60
    mqtt_topics: str = "test/topic1,test/topic2"  # Danh sách phân tách dấu phẩy
    mqtt_qos: int = 0
    mqtt_max_messages: int = 500

    # InfluxDB time-series storage
    influx_enabled: bool = True
    influx_url: str = "http://influxdb:8086"
    influx_token: str = "CHANGE_ME_INFLUX_TOKEN"
    influx_org: str = "iot"
    influx_bucket: str = "iot_telemetry"
    influx_measurement: str = "sensor_readings"

    @property
    def database_url(self) -> str:
        """
        Chuỗi DSN SQLAlchemy cho driver ``mysql+pymysql``.

        Dùng khi cần URL dạng text; kết nối thực tế trong ``db.py`` có thể dùng ``creator`` PyMySQL trực tiếp.
        """
        return str(
            URL.create(
                "mysql+pymysql",
                username=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
            )
        )


settings = Settings()
