import json
from typing import Optional, Dict, Any
from pydantic import model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Config(BaseSettings):
    # MQTT Settings (Dynamic Routing)
    MQTT_BROKERS_CONFIG: Dict[str, Dict[str, Any]]
    MQTT_TOPIC_PATTERN: str

    # MongoDB Settings (Mandatory)
    MONGO_URI: str
    MONGO_DB_NAME: str
    MONGO_COL_NAME: str

    # LINE Messaging API Settings (Dynamic Routing)
    LINE_BOT_TOKENS: Dict[str, str]
    LINE_TARGET_USERS: Dict[str, str]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("LINE_BOT_TOKENS", "LINE_TARGET_USERS", "MQTT_BROKERS_CONFIG", mode="before")
    @classmethod
    def parse_json(cls, v: Any, info) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError as e:
                raise ValueError(f"Field {info.field_name} has invalid JSON format: {e}")
        return v
