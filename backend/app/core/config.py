from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
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
        # Later sources override earlier ones. Dotenv must not beat Docker env; env must also
        # beat optional secret files (file_secret last in default tuple would override env).
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

    # MQTT subscriber (Mosquitto)
    mqtt_enabled: bool = True
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_client_id: str = "iot-backend-subscriber"
    mqtt_keepalive: int = 60
    # Comma-separated list; you will edit later
    mqtt_topics: str = "test/topic1,test/topic2"
    mqtt_qos: int = 0
    mqtt_max_messages: int = 500

    @property
    def database_url(self) -> str:
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

