import pytest
from unittest.mock import MagicMock, patch
from main import main

@patch('main.Config')
@patch('main.DatabaseHandler')
@patch('main.StreamProcessor')
@patch('main.MQTTManager')
def test_main_success(mock_mqtt_manager, mock_processor, mock_db_handler, mock_config):
    # 設定 Mock
    mock_config.return_value.validate.return_value = True
    mock_db_handler.return_value.connect.return_value = True

    # 執行 main
    with patch('main.logger') as mock_logger:
        main()

        # 驗證流程
        mock_config.return_value.validate.assert_called_once()
        mock_db_handler.return_value.connect.assert_called_once()
        mock_mqtt_manager.return_value.start_timeout_monitor.assert_called_once()
        mock_mqtt_manager.return_value.run.assert_called_once()
        mock_db_handler.return_value.close.assert_called_once()

@patch('main.Config')
def test_main_config_fail(mock_config):
    mock_config.return_value.validate.return_value = False

    with patch('main.logger') as mock_logger:
        main()
        mock_logger.error.assert_called_with("Missing critical configuration (MONGO_URI or MQTT_BROKER). Please check your .env file.")

@patch('main.Config')
@patch('main.DatabaseHandler')
def test_main_db_fail(mock_db_handler, mock_config):
    mock_config.return_value.validate.return_value = True
    mock_db_handler.return_value.connect.return_value = False

    with patch('main.logger') as mock_logger:
        main()
        mock_logger.error.assert_called_with("Failed to connect to database. Exiting.")
