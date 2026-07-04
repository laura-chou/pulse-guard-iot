import logging
from unittest.mock import MagicMock, patch
from main import main

def test_main_success():
    # 使用 patch 模擬所有依賴，但不使用 pytest.fixture 以免 main.Config 被提前載入
    with patch('main.Config') as mock_config, \
         patch('main.StreamProcessor') as mock_processor, \
         patch('main.MQTTManager') as mock_mqtt_manager:

        # 執行 main
        with patch('main.logger') as mock_logger:
            main()

            # 驗證流程
            mock_config.assert_called_once()
            mock_mqtt_manager.return_value.run.assert_called_once()
            mock_processor.return_value.close_all_dbs.assert_called_once()

def test_main_config_error():
    from pydantic import ValidationError
    from pydantic_core import InitErrorDetails

    # 模擬 Pydantic 驗證失敗
    with patch('main.Config', side_effect=ValidationError.from_exception_data(title='Config', line_errors=[InitErrorDetails(type='missing', loc=('MQTT_TOPIC_PATTERN',), input=None)])), \
         patch('main.logger') as mock_logger:

        main()
        mock_logger.error.assert_called()
        assert "Configuration error" in mock_logger.error.call_args[0][0]
