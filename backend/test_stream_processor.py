import pytest
import json
import time
import logging
import uuid
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime, timezone
import stream_processor as subscriber

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
def reset_globals():
    """
    重置 subscriber.py 中的全域變數，確保測試案例之間的隔離性。
    同時 Mock MongoDB collection 並擷取所有寫入動作。
    """
    with subscriber.device_states_lock:
        subscriber.device_states.clear()

    # Mock MongoDB collection 並捕獲寫入紀錄
    subscriber.collection = MagicMock()
    captured_writes = []
    subscriber.collection.insert_one.side_effect = lambda x: captured_writes.append(x)

    # 用於 delete_many 的 mock
    subscriber.collection.delete_many.return_value = MagicMock(deleted_count=1)

    return captured_writes

def simulate_mqtt_message(payload_dict, topic="pulseguard/production/device1/data"):
    """模擬接收 MQTT 訊息的輔助函式"""
    msg = MagicMock()
    msg.topic = topic
    msg.payload = json.dumps(payload_dict).encode()
    subscriber.on_message(None, None, msg)

def get_state(data_source="production", device_id="device1"):
    return subscriber.get_device_state(data_source, device_id)

# --- 測試案例 ---

def test_multi_device_isolation(reset_globals):
    """驗證不同裝置之間的狀態是隔離的"""
    # 裝置 1 發送資料
    simulate_mqtt_message({"bpm": 70, "spo2": 98}, topic="pulseguard/production/dev1/data")
    state1 = get_state("production", "dev1")
    assert len(state1.bpm_window) == 1
    assert state1.current_session_id is not None

    # 裝置 2 發送資料
    simulate_mqtt_message({"bpm": 80, "spo2": 95}, topic="pulseguard/production/dev2/data")
    state2 = get_state("production", "dev2")
    assert len(state2.bpm_window) == 1
    assert state2.current_session_id != state1.current_session_id
    assert len(state1.bpm_window) == 1 # 確保沒被影響

def test_scenario_a_first_valid_write(reset_globals):
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 72, "spo2": 98, "device_status": "NORMAL"})
    state = get_state("production", "device1")
    assert len(captured_writes) == 1
    assert captured_writes[0]["analysis_status"] == "NORMAL"
    assert state.first_write_done is True
    assert state.current_session_id is not None

def test_scenario_b_invalid_data_discard_logic(reset_globals):
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 72, "spo2": 98, "device_status": "NORMAL"})
    state = get_state("production", "device1")
    initial_ema = state.last_ema_bpm
    initial_write_count = len(captured_writes)
    assert len(state.bpm_window) == 1

    # 發送無效數值
    simulate_mqtt_message({"bpm": 999, "spo2": 40, "device_status": "DANGER"})
    assert len(state.bpm_window) == 1
    assert state.last_ema_bpm == initial_ema
    assert len(captured_writes) == initial_write_count

def test_scenario_c_spo2_drop_immediate_danger(reset_globals):
    captured_writes = reset_globals
    for _ in range(15):
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})

    state = get_state("production", "device1")
    state.last_write_time = time.time()
    initial_write_count = len(captured_writes)

    # 低血氧觸發 DANGER
    simulate_mqtt_message({"bpm": 70, "spo2": 88, "device_status": "DANGER"})
    assert len(captured_writes) == initial_write_count + 1
    assert captured_writes[-1]["analysis_status"] == "DANGER"
    assert captured_writes[-1]["spo2"] == pytest.approx(97.33333)

def test_timeout_deletion(reset_globals):
    """驗證逾時後會刪除資料庫紀錄並重置狀態"""
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 70, "spo2": 98})
    state = get_state("production", "device1")
    sid = state.current_session_id
    assert sid is not None

    # 模擬逾時
    state.last_seen = time.time() - 11

    # 手動觸發一次 monitor 邏輯 (因為背景執行緒可能沒那麼快)
    # 模擬 timeout_monitor 中的核心邏輯
    with subscriber.device_states_lock:
        to_delete = [s for s in subscriber.device_states.values() if s.current_session_id and (time.time() - s.last_seen > 10)]

    for s in to_delete:
        s.reset_and_delete(subscriber.collection)

    # 驗證刪除呼叫
    subscriber.collection.delete_many.assert_called_with({"session_id": sid})
    assert state.current_session_id is None
    assert len(state.bpm_window) == 0

def test_reset_deletion(reset_globals):
    """驗證 RESET 會刪除資料庫紀錄"""
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 70, "spo2": 98})
    state = get_state("production", "device1")
    sid = state.current_session_id

    simulate_mqtt_message({"device_status": "RESET"})
    subscriber.collection.delete_many.assert_called_with({"session_id": sid})
    assert state.current_session_id is None

def test_scenario_g_completed_signal(reset_globals):
    with patch('report_manager.generate_and_send_report') as mock_report:
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})
        state = get_state("production", "device1")
        session_id = state.current_session_id

        simulate_mqtt_message({"device_status": "COMPLETED", "duration_sec": 120})
        # 驗證狀態已重置 (不應呼叫刪除，COMPLETED 是完成量測)
        assert len(state.bpm_window) == 0
        assert state.current_session_id is None
        subscriber.collection.delete_many.assert_not_called()
        # 驗證報告呼叫
        mock_report.assert_called_once_with(session_id, 120)

def test_main_config_check(monkeypatch, caplog):
    monkeypatch.setenv("MONGO_URI", "") # 破壞配置
    with caplog.at_level(logging.ERROR):
        subscriber.main()
        assert "Missing critical config" in caplog.text
