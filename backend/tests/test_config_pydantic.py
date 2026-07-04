import pytest
from pydantic import ValidationError
from backend.config import Config

def test_config_missing_mandatory_fields():
    # Test with empty environment
    with pytest.raises(ValidationError):
        Config(_env_file=None)

def test_config_valid_minimal(monkeypatch):
    monkeypatch.setenv("MQTT_BROKERS_CONFIG", '{"DEFAULT": {"host": "localhost", "port": 1883}}')
    monkeypatch.setenv("MQTT_TOPIC_PATTERN", "test/topic")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB_NAME", "testdb")
    monkeypatch.setenv("MONGO_COL_NAME", "testcol")
    monkeypatch.setenv("LINE_BOT_TOKENS", '{"DEV01": "token01"}')
    monkeypatch.setenv("LINE_TARGET_USERS", '{"DEV01": "user01"}')

    config = Config(_env_file=None)
    assert config.MQTT_BROKERS_CONFIG["DEFAULT"]["host"] == "localhost"

def test_config_mqtt_brokers_config(monkeypatch):
    monkeypatch.setenv("MQTT_BROKERS_CONFIG", '{"DEFAULT": {"host": "localhost", "port": 1883}, "HOSPITAL": {"host": "remote", "port": 8883, "user": "u", "password": "p"}}')
    monkeypatch.setenv("MQTT_TOPIC_PATTERN", "test/topic")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB_NAME", "testdb")
    monkeypatch.setenv("MONGO_COL_NAME", "testcol")
    monkeypatch.setenv("LINE_BOT_TOKENS", '{"DEV01": "token01"}')
    monkeypatch.setenv("LINE_TARGET_USERS", '{"DEV01": "user01"}')

    config = Config(_env_file=None)
    assert config.MQTT_BROKERS_CONFIG["DEFAULT"]["host"] == "localhost"
    assert config.MQTT_BROKERS_CONFIG["HOSPITAL"]["user"] == "u"

def test_config_invalid_json(monkeypatch):
    monkeypatch.setenv("MQTT_BROKERS_CONFIG", '{"DEFAULT": {"host": "localhost"}}')
    monkeypatch.setenv("MQTT_TOPIC_PATTERN", "test/topic")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB_NAME", "testdb")
    monkeypatch.setenv("MONGO_COL_NAME", "testcol")
    monkeypatch.setenv("LINE_BOT_TOKENS", 'invalid-json')
    monkeypatch.setenv("LINE_TARGET_USERS", '{"DEV01": "user01"}')

    # In Pydantic Settings v2, if a validator fails during EnvSettingsSource parsing,
    # it might be wrapped in a SettingsError.
    with pytest.raises(Exception) as excinfo:
        Config(_env_file=None)

    error_msg = str(excinfo.value)
    # Check if the cause contains our ValueError message if wrapped,
    # or if the message itself is there.
    assert "LINE_BOT_TOKENS" in error_msg
