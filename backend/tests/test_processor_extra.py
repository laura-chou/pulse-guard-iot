import pytest
from unittest.mock import MagicMock, patch
from processor import StreamProcessor, DeviceState

@pytest.fixture
def db_configs():
    return {
        "DEFAULT": {"uri": "mongodb://localhost", "db_name": "db", "col_name": "col"}
    }

@pytest.fixture
def processor(db_configs):
    return StreamProcessor(db_configs)

def test_device_state_reset_exception():
    """測試 DeviceState 重置時發生異常的情況"""
    db_handler = MagicMock()
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

@patch('processor.DatabaseHandler')
def test_process_message_missing_data(mock_db_class, processor):
    """測試 payload 缺少關鍵欄位"""
    mock_db = mock_db_class.return_value
    mock_db.connect.return_value = True

    processor.process_message("test", "DEV001", {"bpm": 80}) # 缺 spo2
    # 檢查是否沒有 insert_one 被呼叫
    # 因為 db_handler 是延遲載入的，如果沒進入寫入邏輯就不會建立連線
    assert mock_db.insert_one.called is False

@patch('processor.DatabaseHandler')
def test_process_message_smart_write_conditions(mock_db_class, processor):
    """測試智慧寫入的分支條件 (分析狀態變更, 時間間隔)"""
    mock_db = mock_db_class.return_value
    mock_db.connect.return_value = True
    mock_db.insert_one.return_value = True

    device_id = "DEV001"

    # 1. 第一次寫入 (應寫入)
    processor.process_message("test", device_id, {"bpm": 80, "spo2": 95})
    assert mock_db.insert_one.call_count == 1

    # 2. 狀態未變且時間未到 (不應寫入)
    processor.process_message("test", device_id, {"bpm": 80, "spo2": 95})
    assert mock_db.insert_one.call_count == 1

    # 3. 分析狀態變更 (應寫入)
    # 觸發警告：SpO2 低於 95
    processor.process_message("test", device_id, {"bpm": 80, "spo2": 90})
    assert mock_db.insert_one.call_count == 2

    # 4. 時間間隔超過 20 秒 (應寫入)
    state = processor.get_device_state("test", device_id)
    state.last_write_time -= 21 # 人為回推時間
    processor.process_message("test", device_id, {"bpm": 80, "spo2": 90})
    assert mock_db.insert_one.call_count == 3

@patch('processor.DatabaseHandler')
def test_check_timeouts(mock_db_class, processor):
    """測試逾時清理邏輯"""
    mock_db = mock_db_class.return_value
    mock_db.connect.return_value = True
    mock_db.delete_many.return_value = 1

    # 建立一個有 Session 的裝置
    state = processor.get_device_state("test", "DEV_TIMEOUT")
    state.current_session_id = "session-timeout"
    state.last_seen = 0 # 模擬很久以前

    processor.check_timeouts(timeout_sec=10)

    assert state.current_session_id is None
    mock_db.delete_many.assert_called_with({"session_id": "session-timeout"})
