import pytest
from pydantic import ValidationError
from backend.config import Config

def test_config_missing_mandatory_fields():
    # Test with empty environment
    with pytest.raises(ValidationError):
        Config(_env_file=None)

def test_config_valid_minimal(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER", "localhost")
    monkeypatch.setenv("MQTT_PORT", "1883")
    monkeypatch.setenv("MQTT_TOPIC_PATTERN", "test/topic")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB_NAME", "testdb")
    monkeypatch.setenv("MONGO_COL_NAME", "testcol")
    monkeypatch.setenv("LINE_BOT_TOKENS", '{"DEV01": "token01"}')
    monkeypatch.setenv("LINE_TARGET_USERS", '{"DEV01": "user01"}')

    config = Config(_env_file=None)
    assert config.MQTT_BROKER == "localhost"
    assert config.MQTT_PORT == 1883
    assert config.MQTT_USER is None

def test_config_mqtt_auth_both_present(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER", "localhost")
    monkeypatch.setenv("MQTT_PORT", "1883")
    monkeypatch.setenv("MQTT_TOPIC_PATTERN", "test/topic")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB_NAME", "testdb")
    monkeypatch.setenv("MONGO_COL_NAME", "testcol")
    monkeypatch.setenv("LINE_BOT_TOKENS", '{"DEV01": "token01"}')
    monkeypatch.setenv("LINE_TARGET_USERS", '{"DEV01": "user01"}')

    monkeypatch.setenv("MQTT_USER", "user")
    monkeypatch.setenv("MQTT_PASSWORD", "pass")

    config = Config(_env_file=None)
    assert config.MQTT_USER == "user"
    assert config.MQTT_PASSWORD == "pass"

def test_config_mqtt_auth_partial_user(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER", "localhost")
    monkeypatch.setenv("MQTT_PORT", "1883")
    monkeypatch.setenv("MQTT_TOPIC_PATTERN", "test/topic")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB_NAME", "testdb")
    monkeypatch.setenv("MONGO_COL_NAME", "testcol")
    monkeypatch.setenv("LINE_BOT_TOKENS", '{"DEV01": "token01"}')
    monkeypatch.setenv("LINE_TARGET_USERS", '{"DEV01": "user01"}')

    monkeypatch.setenv("MQTT_USER", "user")
    # MQTT_PASSWORD is missing

    with pytest.raises(ValidationError) as excinfo:
        Config(_env_file=None)
    assert "Both MQTT_USER and MQTT_PASSWORD must be provided" in str(excinfo.value)

def test_config_mqtt_auth_partial_password(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER", "localhost")
    monkeypatch.setenv("MQTT_PORT", "1883")
    monkeypatch.setenv("MQTT_TOPIC_PATTERN", "test/topic")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB_NAME", "testdb")
    monkeypatch.setenv("MONGO_COL_NAME", "testcol")
    monkeypatch.setenv("LINE_BOT_TOKENS", '{"DEV01": "token01"}')
    monkeypatch.setenv("LINE_TARGET_USERS", '{"DEV01": "user01"}')

    monkeypatch.setenv("MQTT_PASSWORD", "pass")
    # MQTT_USER is missing

    with pytest.raises(ValidationError) as excinfo:
        Config(_env_file=None)
    assert "Both MQTT_USER and MQTT_PASSWORD must be provided" in str(excinfo.value)

def test_config_invalid_json(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER", "localhost")
    monkeypatch.setenv("MQTT_PORT", "1883")
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
