import pytest
import json
import time
import logging
from unittest.mock import MagicMock, patch
from config import Config
from database import DatabaseHandler
from processor import StreamProcessor

# Mock 環境變數，確保測試環境不依賴實際的 .env 檔案
@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("MQTT_BROKERS_CONFIG", '{"DEFAULT": {"host": "localhost", "port": 1883}}')
    monkeypatch.setenv("MQTT_TOPIC_PATTERN", "pulseguard/+/+/data")
    monkeypatch.setenv("MONGO_DB_CONFIG", '{"DEFAULT": {"uri": "mongodb://localhost:27017", "db_name": "test_db", "col_name": "test_col"}}')
    monkeypatch.setenv("LINE_BOT_TOKENS", "{}")
    monkeypatch.setenv("LINE_TARGET_USERS", "{}")

@pytest.fixture
def processor():
    # 使用 real Config 從 mock_env 加載
    config = Config(_env_file=None)
    return StreamProcessor(db_configs=config.MONGO_DB_CONFIG)

# --- 測試案例 ---

def test_multi_device_isolation(processor):
    """驗證不同裝置之間的狀態是隔離的"""
    processor.process_message("prod", "dev1", {"bpm": 70, "spo2": 98})
    state1 = processor.get_device_state("prod", "dev1")
    assert len(state1.bpm_window) == 1
    assert state1.current_session_id is not None

    processor.process_message("prod", "dev2", {"bpm": 80, "spo2": 95})
    state2 = processor.get_device_state("prod", "dev2")
    assert len(state2.bpm_window) == 1
    assert state2.current_session_id != state1.current_session_id
    assert len(state1.bpm_window) == 1

@patch('processor.DatabaseHandler')
def test_scenario_a_first_valid_write(mock_db_class, processor):
    mock_db = mock_db_class.return_value
    mock_db.connect.return_value = True
    mock_db.insert_one.return_value = True

    processor.process_message("prod", "device1", {"bpm": 72, "spo2": 98, "device_status": "NORMAL"})
    state = processor.get_device_state("prod", "device1")

    assert mock_db.insert_one.called
    assert state.first_write_done is True
    assert state.current_session_id is not None

@patch('processor.DatabaseHandler')
def test_lazy_db_connection(mock_db_class, processor):
    mock_db = mock_db_class.return_value
    mock_db.connect.return_value = True

    # 第一次獲取會建立連線
    handler1 = processor._get_db_handler("dev_new")
    assert mock_db.connect.called
    assert "DEFAULT" in processor.db_handlers

    # 第二次獲取應從緩存拿
    mock_db.connect.reset_mock()
    handler2 = processor._get_db_handler("dev_new")
    assert not mock_db.connect.called
    assert handler1 == handler2

@patch('processor.DatabaseHandler')
def test_reset_deletion(mock_db_class, processor):
    mock_db = mock_db_class.return_value
    mock_db.connect.return_value = True
    mock_db.delete_many.return_value = 1

    processor.process_message("prod", "device1", {"bpm": 70, "spo2": 98})
    state = processor.get_device_state("prod", "device1")
    sid = state.current_session_id

    processor.process_message("prod", "device1", {"device_status": "RESET"})
    mock_db.delete_many.assert_called_with({"session_id": sid})
    assert state.current_session_id is None

def test_close_all_dbs(processor):
    mock_handler = MagicMock()
    processor.db_handlers["test"] = mock_handler

    processor.close_all_dbs()
    mock_handler.close.assert_called_once()
    assert len(processor.db_handlers) == 0
