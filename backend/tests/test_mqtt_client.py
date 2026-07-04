import pytest
import json
from unittest.mock import MagicMock, patch
from mqtt_client import MQTTManager

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.MQTT_TOPIC_PATTERN = "pulseguard/+/+/data"
    config.MQTT_BROKERS_CONFIG = {
        "DEFAULT": {"host": "localhost", "port": 1883, "user": "user", "password": "pass"}
    }
    return config

@pytest.fixture
def mock_processor():
    return MagicMock()

@patch('paho.mqtt.client.Client')
def test_mqtt_manager_init(mock_mqtt_client, mock_config, mock_processor):
    manager = MQTTManager(mock_config, mock_processor)

    # 驗證初始化
    mock_mqtt_client.return_value.username_pw_set.assert_called_with("user", "pass")
    mock_mqtt_client.return_value.tls_set.assert_called()
    assert "DEFAULT" in manager.clients

def test_on_connect(mock_config, mock_processor):
    with patch('paho.mqtt.client.Client'):
        manager = MQTTManager(mock_config, mock_processor)
        client = MagicMock()
        # V2 signature: (client, userdata, flags, reason_code, properties)
        manager._on_connect(client, "DEFAULT", {}, 0, None)
        client.subscribe.assert_called_with(mock_config.MQTT_TOPIC_PATTERN)

def test_on_message_valid(mock_config, mock_processor):
    with patch('paho.mqtt.client.Client'):
        manager = MQTTManager(mock_config, mock_processor)
        msg = MagicMock()
        msg.topic = "pulseguard/prod/DEV001/data"
        msg.payload = b'{"bpm": 80, "spo2": 95}'

        manager._on_message(None, None, msg)

        mock_processor.process_message.assert_called_with("prod", "DEV001", {"bpm": 80, "spo2": 95})

def test_on_message_invalid_topic(mock_config, mock_processor):
    with patch('paho.mqtt.client.Client'):
        manager = MQTTManager(mock_config, mock_processor)
        msg = MagicMock()
        msg.topic = "wrong/topic"

        manager._on_message(None, None, msg)
        assert mock_processor.process_message.called is False

def test_run_logic(mock_config, mock_processor):
    with patch('paho.mqtt.client.Client') as mock_client:
        # Create a real-ish MQTTManager with mocked clients
        manager = MQTTManager(mock_config, mock_processor)

        # Mock loop_start and connect on the created client
        client_mock = manager.clients["DEFAULT"]

        # Patch check_timeouts to raise an exception to break the while loop
        with patch.object(mock_processor, 'check_timeouts', side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                manager.run()

        client_mock.connect.assert_called_with("localhost", 1883, 60)
        client_mock.loop_start.assert_called_once()
