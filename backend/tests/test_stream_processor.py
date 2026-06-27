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
    monkeypatch.setenv("MQTT_BROKER", "localhost")
    monkeypatch.setenv("MQTT_PORT", "1883")
    monkeypatch.setenv("MQTT_USER", "user")
    monkeypatch.setenv("MQTT_PASSWORD", "pass")
    monkeypatch.setenv("MQTT_TOPIC_PATTERN", "pulseguard/+/+/data")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB_NAME", "test_db")
    monkeypatch.setenv("MONGO_COL_NAME", "test_col")

@pytest.fixture
def mock_db():
    db = MagicMock(spec=DatabaseHandler)
    db.insert_one.return_value = True
    db.delete_many.return_value = 1
    return db

@pytest.fixture
def processor(mock_db):
    return StreamProcessor(db_handler=mock_db)

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

def test_scenario_a_first_valid_write(processor, mock_db):
    processor.process_message("prod", "device1", {"bpm": 72, "spo2": 98, "device_status": "NORMAL"})
    state = processor.get_device_state("prod", "device1")
    assert mock_db.insert_one.called
    assert state.first_write_done is True
    assert state.current_session_id is not None

def test_scenario_b_invalid_data_discard_logic(processor, mock_db):
    processor.process_message("prod", "device1", {"bpm": 72, "spo2": 98, "device_status": "NORMAL"})
    state = processor.get_device_state("prod", "device1")
    initial_ema = state.last_ema_bpm
    mock_db.insert_one.reset_mock()

    # 發送無效數值
    processor.process_message("prod", "device1", {"bpm": 999, "spo2": 40, "device_status": "DANGER"})
    assert len(state.bpm_window) == 1
    assert state.last_ema_bpm == initial_ema
    assert not mock_db.insert_one.called

def test_scenario_c_spo2_drop_immediate_danger(processor, mock_db):
    for _ in range(15):
        processor.process_message("prod", "device1", {"bpm": 70, "spo2": 98, "device_status": "NORMAL"})

    state = processor.get_device_state("prod", "device1")
    state.last_write_time = time.time()
    mock_db.insert_one.reset_mock()

    # 低血氧觸發 DANGER
    processor.process_message("prod", "device1", {"bpm": 70, "spo2": 88, "device_status": "DANGER"})
    assert mock_db.insert_one.called
    record = mock_db.insert_one.call_args[0][0]
    assert record["analysis_status"] == "DANGER"
    assert record["spo2"] == pytest.approx(97.33333)

def test_timeout_deletion(processor, mock_db):
    """驗證逾時後會刪除資料庫紀錄並重置狀態"""
    processor.process_message("prod", "device1", {"bpm": 70, "spo2": 98})
    state = processor.get_device_state("prod", "device1")
    sid = state.current_session_id
    assert sid is not None

    # 模擬逾時
    state.last_seen = time.time() - 11
    processor.check_timeouts(timeout_sec=10)

    mock_db.delete_many.assert_called_with({"session_id": sid})
    assert state.current_session_id is None
    assert len(state.bpm_window) == 0

def test_reset_deletion(processor, mock_db):
    """驗證 RESET 會刪除資料庫紀錄"""
    processor.process_message("prod", "device1", {"bpm": 70, "spo2": 98})
    state = processor.get_device_state("prod", "device1")
    sid = state.current_session_id

    processor.process_message("prod", "device1", {"device_status": "RESET"})
    mock_db.delete_many.assert_called_with({"session_id": sid})
    assert state.current_session_id is None

def test_scenario_g_completed_signal(processor, mock_db):
    with patch('report_manager.generate_and_send_report') as mock_report:
        processor.process_message("prod", "device1", {"bpm": 70, "spo2": 98, "device_status": "NORMAL"})
        state = processor.get_device_state("prod", "device1")
        session_id = state.current_session_id

        processor.process_message("prod", "device1", {"device_status": "COMPLETED", "duration_sec": 120})
        assert len(state.bpm_window) == 0
        assert state.current_session_id is None
        mock_report.assert_called_once_with(session_id, 120)
