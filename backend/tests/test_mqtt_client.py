import pytest
import json
from unittest.mock import MagicMock, patch
from mqtt_client import MQTTManager

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.MQTT_USER = "user"
    config.MQTT_PASSWORD = "pass"
    config.MQTT_TOPIC_PATTERN = "test/+/data"
    config.MQTT_BROKER = "localhost"
    config.MQTT_PORT = 1883
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

def test_on_connect(mock_config, mock_processor):
    with patch('paho.mqtt.client.Client'):
        manager = MQTTManager(mock_config, mock_processor)
        client = MagicMock()
        manager._on_connect(client, None, {}, 0)
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

def test_run_exception(mock_config, mock_processor):
    with patch('paho.mqtt.client.Client') as mock_client:
        manager = MQTTManager(mock_config, mock_processor)
        mock_client.return_value.connect.side_effect = Exception("Connect Error")

        # 應捕捉異常而不崩潰
        manager.run()
