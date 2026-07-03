from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Config(BaseSettings):
    # MQTT Settings (Mandatory)
    MQTT_BROKER: str
    MQTT_PORT: int
    MQTT_TOPIC_PATTERN: str

    # MQTT Auth (Optional, but must both exist if one exists)
    MQTT_USER: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None

    # MongoDB Settings (Mandatory)
    MONGO_URI: str
    MONGO_DB_NAME: str
    MONGO_COL_NAME: str

    # LINE Messaging API Settings (Mandatory as per request)
    LINE_CHANNEL_ACCESS_TOKEN: str
    LINE_USER_ID: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def check_mqtt_auth(self) -> "Config":
        if (self.MQTT_USER is None) != (self.MQTT_PASSWORD is None):
            raise ValueError("Both MQTT_USER and MQTT_PASSWORD must be provided, or both must be omitted.")
        return self
