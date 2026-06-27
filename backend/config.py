import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Config:
    MQTT_BROKER: str = os.getenv("MQTT_BROKER")
    MQTT_PORT: int = int(os.getenv("MQTT_PORT"))
    MQTT_USER: Optional[str] = os.getenv("MQTT_USER")
    MQTT_PASSWORD: Optional[str] = os.getenv("MQTT_PASSWORD")
    MQTT_TOPIC_PATTERN: str = os.getenv("MQTT_TOPIC_PATTERN")

    MONGO_URI: str = os.getenv("MONGO_URI")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME")
    MONGO_COL_NAME: str = os.getenv("MONGO_COL_NAME")

    LINE_CHANNEL_ACCESS_TOKEN: Optional[str] = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    LINE_USER_ID: Optional[str] = os.getenv("LINE_USER_ID")

    @classmethod
    def validate(cls) -> bool:
        """驗證必要設定是否存在"""
        return bool(cls.MONGO_URI and cls.MQTT_BROKER)
