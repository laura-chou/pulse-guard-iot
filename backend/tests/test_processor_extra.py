import pytest
from unittest.mock import MagicMock, patch
from processor import StreamProcessor, DeviceState

@pytest.fixture
def db_handler():
    return MagicMock()

@pytest.fixture
def processor(db_handler):
    return StreamProcessor(db_handler)

def test_device_state_reset_exception(db_handler):
    """測試 DeviceState 重置時發生異常的情況"""
    db_handler.delete_many.side_effect = Exception("DB Error")
    state = DeviceState("test", "DEV001")
    state.current_session_id = "session-123"

    # 應捕捉異常並繼續清理
    state.reset_and_delete(db_handler)

    assert state.current_session_id is None
    assert len(state.bpm_window) == 0

def test_process_message_exception(processor):
    """測試 process_message 發生未預期異常的情況"""
    # 模擬 get_device_state 拋出異常
    with patch.object(processor, 'get_device_state', side_effect=Exception("Unexpected Error")):
        processor.process_message("test", "DEV001", {"bpm": 80, "spo2": 95})
        # 應該捕捉異常且不崩潰

def test_process_message_missing_data(processor):
    """測試 payload 缺少關鍵欄位"""
    processor.process_message("test", "DEV001", {"bpm": 80}) # 缺 spo2
    assert processor.db_handler.insert_one.called is False

def test_process_message_smart_write_conditions(processor, db_handler):
    """測試智慧寫入的分支條件 (分析狀態變更, 時間間隔)"""
    device_id = "DEV001"

    # 1. 第一次寫入 (應寫入)
    processor.process_message("test", device_id, {"bpm": 80, "spo2": 95})
    assert db_handler.insert_one.call_count == 1

    # 2. 狀態未變且時間未到 (不應寫入)
    processor.process_message("test", device_id, {"bpm": 80, "spo2": 95})
    assert db_handler.insert_one.call_count == 1

    # 3. 分析狀態變更 (應寫入)
    # 觸發警告：SpO2 低於 95
    processor.process_message("test", device_id, {"bpm": 80, "spo2": 90})
    assert db_handler.insert_one.call_count == 2

    # 3.5 分析狀態變更為 DANGER (應寫入，覆蓋 L124)
    # 觸發危險：SpO2 低於 90
    processor.process_message("test", device_id, {"bpm": 80, "spo2": 85})
    assert db_handler.insert_one.call_count == 3

    # 4. 時間間隔超過 20 秒 (應寫入)
    state = processor.get_device_state("test", device_id)
    state.last_write_time -= 21 # 人為回推時間
    processor.process_message("test", device_id, {"bpm": 80, "spo2": 85})
    assert db_handler.insert_one.call_count == 4

def test_check_timeouts(processor, db_handler):
    """測試逾時清理邏輯"""
    # 建立一個有 Session 的裝置
    state = processor.get_device_state("test", "DEV_TIMEOUT")
    state.current_session_id = "session-timeout"
    state.last_seen = 0 # 模擬很久以前

    processor.check_timeouts(timeout_sec=10)

    assert state.current_session_id is None
    db_handler.delete_many.assert_called_with({"session_id": "session-timeout"})
