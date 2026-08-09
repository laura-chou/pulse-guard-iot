import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from config import Config
from processor import StreamProcessor, DeviceState

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("MQTT_BROKERS_CONFIG", '{"DEFAULT": {"host": "localhost", "port": 1883}}')
    monkeypatch.setenv("MQTT_TOPIC_PATTERN", "pulseguard/+/+/data")
    monkeypatch.setenv("MONGO_DB_CONFIG", '{"DEFAULT": {"uri": "mongodb://localhost:27017", "db_name": "test_db", "col_name": "test_col"}}')
    monkeypatch.setenv("LINE_BOT_TOKENS", "{}")
    monkeypatch.setenv("LINE_TARGET_USERS", "{}")

@pytest.fixture
def processor():
    # Set queue limit to 3 for easy testing of eviction and overflow
    config = Config(_env_file=None)
    return StreamProcessor(db_configs=config.MONGO_DB_CONFIG, retry_queue_max_len=3)

@patch('processor.DatabaseHandler')
def test_retry_queue_accumulate_on_failure(mock_db_class, processor):
    """測試當 insert_one 失敗（或斷線）時，資料會正確被快取至 retry_queue"""
    mock_db = mock_db_class.return_value
    mock_db.connect.return_value = True
    # 模擬 insert_one 與 insert_many 都失敗 (斷線狀態)
    mock_db.insert_one.return_value = False
    mock_db.insert_many.return_value = False

    device_id = "DEV_RETRY_1"

    # 第一次寫入 (應該失敗被放進 queue)
    processor.process_message("test", device_id, {"bpm": 70, "spo2": 98})
    state = processor.get_device_state("test", device_id)
    assert len(state.retry_queue) == 1
    assert state.retry_queue[0]["avg_bpm"] == 70.0

    # 狀態變更 (應該失敗再次被放進 queue)
    processor.process_message("test", device_id, {"bpm": 120, "spo2": 90}) # DANGER
    assert len(state.retry_queue) == 2
    assert state.retry_queue[1]["avg_bpm"] == 95.0 # (70+120)/2 = 95

@patch('processor.DatabaseHandler')
def test_retry_queue_fifo_eviction(mock_db_class, processor):
    """測試佇列滿載時，FIFO 淘汰最舊資料的機制 (Max length = 3)"""
    mock_db = mock_db_class.return_value
    mock_db.connect.return_value = True
    mock_db.insert_one.return_value = False
    mock_db.insert_many.return_value = False

    device_id = "DEV_RETRY_2"
    state = processor.get_device_state("test", device_id)

    # 依序放入4筆資料（上限為 3）
    processor.process_message("test", device_id, {"bpm": 70, "spo2": 98})  # 1 (avg_bpm=70)
    state.last_analysis_status = None # 強制觸發寫入
    processor.process_message("test", device_id, {"bpm": 71, "spo2": 98})  # 2 (avg_bpm=70.5)
    state.last_analysis_status = None
    processor.process_message("test", device_id, {"bpm": 72, "spo2": 98})  # 3 (avg_bpm=71)
    state.last_analysis_status = None
    processor.process_message("test", device_id, {"bpm": 73, "spo2": 98})  # 4 (avg_bpm=71.5)

    assert len(state.retry_queue) == 3
    # 第一筆 (70.0) 應該被剔除，保留 2, 3, 4
    assert state.retry_queue[0]["avg_bpm"] == 70.5
    assert state.retry_queue[1]["avg_bpm"] == 71.0
    assert state.retry_queue[2]["avg_bpm"] == 71.5

@patch('processor.DatabaseHandler')
def test_retry_queue_success_reconnect_bulk_insert(mock_db_class, processor):
    """測試當連線恢復時，優先批次寫入佇列中所有資料，再寫入最新資料"""
    mock_db = mock_db_class.return_value
    mock_db.connect.return_value = True

    # 1. 斷線：兩次寫入都失敗
    mock_db.insert_one.return_value = False
    mock_db.insert_many.return_value = False
    device_id = "DEV_RETRY_3"
    state = processor.get_device_state("test", device_id)

    processor.process_message("test", device_id, {"bpm": 70, "spo2": 98})
    state.last_analysis_status = None
    processor.process_message("test", device_id, {"bpm": 71, "spo2": 98})
    assert len(state.retry_queue) == 2

    # 2. 重置 mock 的呼叫紀錄，以便精確驗證接下來的恢復連線寫入
    mock_db.insert_many.reset_mock()
    mock_db.insert_one.reset_mock()

    # 恢復連線
    mock_db.insert_many.return_value = True
    mock_db.insert_one.return_value = True

    # 觸發下一次寫入 (第三次)
    state.last_analysis_status = None
    processor.process_message("test", device_id, {"bpm": 72, "spo2": 98})

    # 驗證歷史資料是否順利批次寫入且清空
    mock_db.insert_many.assert_called_once()
    bulk_records = mock_db.insert_many.call_args[0][0]
    assert len(bulk_records) == 2
    assert bulk_records[0]["avg_bpm"] == 70.0
    assert bulk_records[1]["avg_bpm"] == 70.5

    # 驗證 queue 已清空
    assert len(state.retry_queue) == 0
    # 驗證最新一筆也成功寫入
    last_record_insert = mock_db.insert_one.call_args[0][0]
    assert last_record_insert["avg_bpm"] == 71.0

@patch('processor.DatabaseHandler')
def test_retry_queue_bulk_insert_success_current_failed(mock_db_class, processor):
    """測試 Edge Case：批次寫入成功，但最新一筆不幸失敗。應只將最新一筆放進剛清空的 queue"""
    mock_db = mock_db_class.return_value
    mock_db.connect.return_value = True

    # 1. 斷線
    mock_db.insert_one.return_value = False
    mock_db.insert_many.return_value = False
    device_id = "DEV_RETRY_4"
    state = processor.get_device_state("test", device_id)
    processor.process_message("test", device_id, {"bpm": 70, "spo2": 98})
    assert len(state.retry_queue) == 1

    # 重置 mock 呼叫歷史
    mock_db.insert_many.reset_mock()
    mock_db.insert_one.reset_mock()

    # 2. 恢復連線：批次寫入成功，但最新一筆失敗
    mock_db.insert_many.return_value = True
    mock_db.insert_one.return_value = False

    state.last_analysis_status = None
    processor.process_message("test", device_id, {"bpm": 71, "spo2": 98})

    # 批次寫入成功，歷史資料清空，呼叫 insert_many 時內容應該是歷史那筆 (70.0)
    mock_db.insert_many.assert_called_once()
    bulk_records = mock_db.insert_many.call_args[0][0]
    assert len(bulk_records) == 1
    assert bulk_records[0]["avg_bpm"] == 70.0

    # 佇列現在應該只有新失敗的這一筆 (70.5)
    assert len(state.retry_queue) == 1
    assert state.retry_queue[0]["avg_bpm"] == 70.5

@patch('processor.DatabaseHandler')
def test_graceful_shutdown_flush_success(mock_db_class, processor):
    """測試優雅關閉（Graceful Shutdown）時，成功將佇列中的資料 flush 到資料庫"""
    mock_db = mock_db_class.return_value
    mock_db.connect.return_value = True

    # 斷線累積
    mock_db.insert_one.return_value = False
    mock_db.insert_many.return_value = False
    device_id = "DEV_RETRY_5"
    state = processor.get_device_state("test", device_id)
    processor.process_message("test", device_id, {"bpm": 70, "spo2": 98})
    assert len(state.retry_queue) == 1

    # 重置 mock
    mock_db.insert_many.reset_mock()

    # 關閉時恢復連線
    mock_db.insert_many.return_value = True

    # 執行優雅 Flush
    processor.flush_all_queues()

    # 驗證是否寫入資料庫並清空
    mock_db.insert_many.assert_called_once()
    assert len(state.retry_queue) == 0

@patch('processor.DatabaseHandler')
def test_graceful_shutdown_flush_failure(mock_db_class, processor):
    """測試優雅關閉時若資料庫依然斷線，Flush 失敗但程序不崩潰且資料繼續保留在 queue"""
    mock_db = mock_db_class.return_value
    mock_db.connect.return_value = True

    mock_db.insert_one.return_value = False
    mock_db.insert_many.return_value = False
    device_id = "DEV_RETRY_6"
    state = processor.get_device_state("test", device_id)
    processor.process_message("test", device_id, {"bpm": 70, "spo2": 98})
    assert len(state.retry_queue) == 1

    # 依然斷線
    mock_db.insert_many.return_value = False

    # 執行 Flush 應捕獲不崩潰
    processor.flush_all_queues()

    # 驗證資料繼續留在佇列中
    assert len(state.retry_queue) == 1
