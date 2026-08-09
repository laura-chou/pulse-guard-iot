import json
from typing import Optional, Dict, Any
from pydantic import model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Config(BaseSettings):
    # MQTT Settings (Dynamic Routing)
    MQTT_BROKERS_CONFIG: Dict[str, Dict[str, Any]]
    MQTT_TOPIC_PATTERN: str

    # MongoDB Settings (Lazy Connection Pool)
    MONGO_DB_CONFIG: Dict[str, Dict[str, Any]]

    # LINE Messaging API Settings (Dynamic Routing)
    LINE_BOT_TOKENS: Dict[str, str]
    LINE_TARGET_USERS: Dict[str, str]

    # Retry Queue settings
    RETRY_QUEUE_MAX_LEN: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("LINE_BOT_TOKENS", "LINE_TARGET_USERS", "MQTT_BROKERS_CONFIG", "MONGO_DB_CONFIG", mode="before")
    @classmethod
    def parse_json(cls, v: Any, info) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError as e:
                raise ValueError(f"Field {info.field_name} has invalid JSON format: {e}")
        return v

    @model_validator(mode="after")
    def check_mongo_default(self) -> "Config":
        if "DEFAULT" not in self.MONGO_DB_CONFIG:
            raise ValueError("MONGO_DB_CONFIG must contain a 'DEFAULT' configuration.")
        return self
