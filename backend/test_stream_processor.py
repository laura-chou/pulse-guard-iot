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
    monkeypatch.setenv("MQTT_TOPIC", "pulse/production")
    monkeypatch.setenv("MQTT_TEST_TOPIC", "pulse/test")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB_NAME", "test_db")
    monkeypatch.setenv("MONGO_COL_NAME", "test_col")

@pytest.fixture
def reset_globals():
    """
    重置 subscriber.py 中的全域變數，確保測試案例之間的隔離性。
    同時 Mock MongoDB collection 並擷取所有寫入動作。
    """
    subscriber.bpm_window.clear()
    subscriber.spo2_window.clear()
    subscriber.last_ema_bpm = None
    subscriber.last_analysis_status = None
    subscriber.first_write_done = False
    subscriber.last_write_time = 0
    subscriber.current_session_id = None

    # Mock MongoDB collection 並捕獲寫入紀錄
    subscriber.collection = MagicMock()
    captured_writes = []
    subscriber.collection.insert_one.side_effect = lambda x: captured_writes.append(x)

    return captured_writes

def simulate_mqtt_message(payload_dict, topic="pulse/production"):
    """模擬接收 MQTT 訊息的輔助函式，預設為生產環境 Topic"""
    msg = MagicMock()
    msg.topic = topic
    msg.payload = json.dumps(payload_dict).encode()
    subscriber.on_message(None, None, msg)

# --- 測試案例 ---

def test_scenario_a_first_valid_write(reset_globals):
    """
    [測試目的] 驗證收到第一筆有效量測資料時，是否立即寫入資料庫並生成 Session ID。
    [實際行為] 當系統收到第一筆符合範圍的資料時，應跳過 20s 定時器立即持久化。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 應額外驗證 timestamp 欄位是否為正確的 datetime 物件。
    """
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 72, "spo2": 98, "device_status": "NORMAL"})
    assert len(captured_writes) == 1
    assert captured_writes[0]["analysis_status"] == "NORMAL"
    assert "device_status" not in captured_writes[0]
    assert subscriber.first_write_done is True
    assert subscriber.current_session_id is not None

def test_scenario_b_invalid_data_discard_logic(reset_globals):
    """
    [測試目的] 驗證無效數值是否被徹底丟棄，不影響計算也不寫入資料庫。
    [實際行為] 先發送一筆有效資料，再發送一筆 BPM 超出範圍的資料，檢查 Window 與資料庫寫入數。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 72, "spo2": 98, "device_status": "NORMAL"})
    initial_ema = subscriber.last_ema_bpm
    initial_write_count = len(captured_writes)
    assert len(subscriber.bpm_window) == 1

    # 發送無效數值 (觸發丟棄邏輯)
    simulate_mqtt_message({"bpm": 999, "spo2": 40, "device_status": "DANGER"})
    assert len(subscriber.bpm_window) == 1
    assert subscriber.last_ema_bpm == initial_ema
    assert len(captured_writes) == initial_write_count # 沒有新紀錄寫入

def test_scenario_c_spo2_drop_immediate_danger(reset_globals):
    """
    [測試目的] 驗證 SpO2 掉落至危險範圍時，是否不計較 20s 定時器立即寫入 DANGER 狀態。
    [實際行為] 填充 Window 後，發送 SpO2=88，檢查資料庫是否立即新增一筆 DANGER 紀錄。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    captured_writes = reset_globals
    for _ in range(15):
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})

    subscriber.last_write_time = time.time()
    initial_write_count = len(captured_writes)

    # 低血氧觸發 DANGER
    simulate_mqtt_message({"bpm": 70, "spo2": 88, "device_status": "DANGER"})
    assert len(captured_writes) == initial_write_count + 1
    assert captured_writes[-1]["analysis_status"] == "DANGER"
    # 驗證 spo2 欄位存儲的是視窗平均值 (視窗大小 15，內容為 14 筆 98 + 1 筆 88)
    assert captured_writes[-1]["spo2"] == pytest.approx(97.33333)

def test_scenario_d_heart_rate_spike(reset_globals):
    """
    [測試目的] 驗證心率劇烈變化 (|ΔBPM| >= 50) 時，是否立即觸發 DANGER。
    [實際行為] 穩定一段時間後突然發送 BPM=125 (差值 55)，檢查狀態。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    captured_writes = reset_globals
    for _ in range(15):
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})

    subscriber.last_write_time = time.time()
    initial_write_count = len(captured_writes)

    # 心率突然跳升 (裝置可能還判定為 WARNING，但 Python 判定為 DANGER)
    simulate_mqtt_message({"bpm": 125, "spo2": 98, "device_status": "WARNING"})
    assert len(captured_writes) == initial_write_count + 1
    assert captured_writes[-1]["analysis_status"] == "DANGER"
    assert "device_status" not in captured_writes[-1]
    assert captured_writes[-1]["delta_bpm"] == 55.0

def test_tachycardia_detection(reset_globals):
    """
    [測試目的] 驗證持續高心率導致 EMA 達到 DANGER 門檻 (>= 140)。
    [實際行為] 連續發送多筆 142 BPM 的資料，直到 EMA 越過 140。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 臨床上 EMA 雖然可以濾波，但反應較慢，建議視需求調整 alpha 值。
    """
    captured_writes = reset_globals
    # 填充 Window
    for _ in range(15):
        simulate_mqtt_message({"bpm": 135, "spo2": 98, "device_status": "DANGER"})

    # 持續高心率
    for _ in range(30):
        simulate_mqtt_message({"bpm": 142, "spo2": 98, "device_status": "DANGER"})
        if captured_writes[-1]["analysis_status"] == "DANGER":
            break

    assert captured_writes[-1]["analysis_status"] == "DANGER"
    assert subscriber.last_ema_bpm >= 140

def test_scenario_e_timer_mechanism(reset_globals):
    """
    [測試目的] 驗證 20 秒定時寫入 (Heartbeat) 機制。
    [實際行為] 使用 patch time.time 模擬時間流逝，檢查 15s 與 20s 時的寫入行為。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    captured_writes = reset_globals
    with patch('time.time') as mock_time:
        start_t = 1000.0
        mock_time.return_value = start_t
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})
        assert len(captured_writes) == 1

        # 20 秒內
        mock_time.return_value = start_t + 15
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})
        assert len(captured_writes) == 1

        # 達到 20 秒
        mock_time.return_value = start_t + 20
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})
        assert len(captured_writes) == 2

def test_scenario_f_event_driven_transition(reset_globals):
    """
    [測試目的] 驗證分析狀態改變 (NORMAL -> WARNING) 時是否立即寫入。
    [實際行為] 發送 NORMAL 後，短時間內發送會觸發 WARNING 的資料 (SpO2=93)。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    captured_writes = reset_globals
    with patch('time.time') as mock_time:
        start_t = 1000.0
        mock_time.return_value = start_t
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"}) # NORMAL
        assert len(captured_writes) == 1

        # 2 秒後分析狀態改變 (SpO2 93 觸發 WARNING)
        mock_time.return_value = start_t + 2.0
        simulate_mqtt_message({"bpm": 70, "spo2": 93, "device_status": "NORMAL"}) # WARNING (Python)
        assert len(captured_writes) == 2
        assert captured_writes[-1]["analysis_status"] == "WARNING"
        assert "device_status" not in captured_writes[-1]

def test_scenario_g_completed_signal(reset_globals):
    """
    [測試目的] 驗證 COMPLETED 訊號是否正確觸發報告生成並徹底重置系統狀態。
    [實際行為] 發送 COMPLETED，檢查 report_manager 呼叫與全域變數重置。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    with patch('report_manager.generate_and_send_report') as mock_report:
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})
        session_id = subscriber.current_session_id
        assert session_id is not None
        assert subscriber.first_write_done is True

        simulate_mqtt_message({"device_status": "COMPLETED", "duration_sec": 120})
        # 驗證所有狀態欄位均已重置
        assert len(subscriber.bpm_window) == 0
        assert subscriber.current_session_id is None
        assert subscriber.last_write_time == 0
        assert subscriber.first_write_done is False
        assert subscriber.last_ema_bpm is None
        # 驗證報告呼叫
        mock_report.assert_called_once_with(session_id, 120)

def test_scenario_h_reset_signal(reset_globals):
    """
    [測試目的] 驗證 RESET 訊號是否寫入資料庫並重置系統，但不生成報告。
    [實際行為] 發送 RESET，檢查 DB 紀錄中 analysis_status 為 RESET 且狀態清空。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    with patch('report_manager.generate_and_send_report') as mock_report:
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})
        session_id = subscriber.current_session_id

        simulate_mqtt_message({"device_status": "RESET"})
        # 驗證資料庫紀錄 (現在統一寫入 analysis_status 欄位)
        assert reset_globals[-1]["analysis_status"] == "RESET"
        assert reset_globals[-1]["session_id"] == session_id
        # 驗證重置
        assert subscriber.current_session_id is None
        assert subscriber.last_write_time == 0
        mock_report.assert_not_called()

@pytest.mark.parametrize("spo2, ema, delta, expected", [
    # SpO2 邊界 (浮點數測試)
    (90.0, 70, 0, "DANGER"),
    (90.1, 70, 0, "WARNING"),
    (94.9, 70, 0, "WARNING"),
    (95.0, 70, 0, "NORMAL"),
    # EMA 邊界
    (98, 50.0, 0, "DANGER"),
    (98, 50.1, 0, "WARNING"),
    (98, 59.9, 0, "WARNING"),
    (98, 60.0, 0, "NORMAL"),
    (98, 100.0, 0, "NORMAL"),
    (98, 100.1, 0, "WARNING"),
    (98, 139.9, 0, "WARNING"),
    (98, 140.0, 0, "DANGER"),
    # Delta BPM 邊界
    (98, 70, 14.9, "NORMAL"),
    (98, 70, 15.0, "WARNING"),
    (98, 70, 49.9, "WARNING"),
    (98, 70, 50.0, "DANGER"),
])
def test_get_status_floating_boundaries(spo2, ema, delta, expected):
    """
    [測試目的] 驗證 get_status 在浮點數邊界上的判斷是否符合預期。
    [實際行為] 傳入多組測試數據到 get_status。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    assert subscriber.get_status(70, ema, delta, spo2) == expected

def test_session_id_immediate_generation(reset_globals):
    """
    [測試目的] 驗證一旦有有效資料，Session ID 必須立即生成，不論是否寫入資料庫。
    [實際行為] 發送一筆會寫入的資料，檢查 Session ID，再模擬不寫入的情況檢查 Session ID 是否維持。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    # 這裡我們手動讓 should_write 為 False 的情境 (比如剛寫入完又要寫入)
    simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"}) # 第一筆，會生成 Session 並寫入
    first_session = subscriber.current_session_id
    assert first_session is not None

    # 重置標記但不清空 Session，模擬後續量測
    subscriber.last_write_time = time.time()
    simulate_mqtt_message({"bpm": 71, "spo2": 98, "device_status": "NORMAL"})
    assert subscriber.current_session_id == first_session

def test_invalid_data_discard_behavior(reset_globals):
    """
    [測試目的] 驗證當裝置訊號無效或數據超出合理範圍時，系統應直接忽略該筆訊息。
    [實際行為] 發送 BPM=0, SpO2=0 或 OFF-CHIP，檢查 captured_writes 長度。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"}) # NORMAL
    initial_count = len(captured_writes)

    # 立即發送無效資料 (BPM 0, SpO2 0)
    simulate_mqtt_message({"bpm": 0, "spo2": 0, "device_status": "OFF-CHIP"})
    assert len(captured_writes) == initial_count # 應維持原樣，不寫入也不處理

def test_mongodb_insert_failure_preservation(reset_globals, caplog):
    """
    [測試目的] 驗證 MongoDB 寫入失敗時，系統狀態不應更新，且後續訊息應能觸發重試。
    [實際行為] 當 insert_one 失敗時，first_write_done 與 last_analysis_status 應維持原狀。
    [是否正確] 是 (修復後)。先前實作中 first_write_done 會在寫入前更新，導致失敗後不再重試。
    [可能 Flaky] 否。
    [建議修改] 確保 first_write_done 也在寫入成功後才更新。
    """
    # 第一次寫入失敗
    subscriber.collection.insert_one.side_effect = Exception("DB Fail")
    subscriber.last_analysis_status = None
    subscriber.last_write_time = 0.0
    subscriber.first_write_done = False

    with caplog.at_level(logging.ERROR):
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})
        assert "MongoDB write error" in caplog.text
        # 狀態應保持初始值，代表尚未成功寫入，first_write_done 應仍為 False
        assert subscriber.last_analysis_status is None
        assert subscriber.last_write_time == 0.0
        assert subscriber.first_write_done is False

    # 第二次嘗試寫入成功 (重置 mock)
    subscriber.collection.insert_one.side_effect = None
    simulate_mqtt_message({"bpm": 71, "spo2": 98, "device_status": "NORMAL"})

    # 驗證最終寫入成功並更新了狀態
    assert subscriber.last_analysis_status == "NORMAL"
    assert subscriber.last_write_time > 0
    assert subscriber.first_write_done is True

def test_ema_calculation_correctness(reset_globals):
    """
    [測試目的] 驗證 EMA 計算公式：ema = 0.3 * current + 0.7 * last
    [實際行為] 手動計算預期 EMA 並與程式結果比對。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    subscriber.last_ema_bpm = None
    simulate_mqtt_message({"bpm": 100, "spo2": 98, "device_status": "NORMAL"}) # 初始 EMA = 100
    assert subscriber.last_ema_bpm == 100.0

    simulate_mqtt_message({"bpm": 110, "spo2": 98, "device_status": "NORMAL"}) # xt_bpm = (100+110)/2 = 105; EMA = 0.3*105 + 0.7*100 = 101.5
    assert subscriber.last_ema_bpm == pytest.approx(101.5)

def test_sliding_window_behavior(reset_globals):
    """
    [測試目的] 驗證心率滑動視窗 (Sliding Window) 的長度限制與先進先出行為。
    [實際行為] 發送超過 15 筆數據，檢查 Window 內容。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    for i in range(15):
        simulate_mqtt_message({"bpm": 60 + i, "spo2": 95, "device_status": "NORMAL"})
    assert len(subscriber.bpm_window) == 15

    simulate_mqtt_message({"bpm": 80, "spo2": 95, "device_status": "NORMAL"})
    assert len(subscriber.bpm_window) == 15
    assert subscriber.bpm_window[0] == 61.0 # 60 已被彈出

def test_completed_with_no_session(reset_globals):
    """
    [測試目的] 驗證若在無 Session 狀態下收到 COMPLETED，不應報錯也不應產生報告。
    [實際行為] 在 session_id 為 None 時發送 COMPLETED。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    with patch('report_manager.generate_and_send_report') as mock_report:
        # 確保當前無 Session
        subscriber.current_session_id = None
        simulate_mqtt_message({"device_status": "COMPLETED", "duration_sec": 60})
        mock_report.assert_not_called()

def test_on_connect_success(caplog):
    """
    [測試目的] 驗證 MQTT 連線成功時的訂閱行為。
    [實際行為] 模擬 on_connect(rc=0)，檢查日誌與 subscribe 呼叫。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    client = MagicMock()
    with caplog.at_level(logging.INFO):
        subscriber.on_connect(client, None, None, 0)
        assert "Connected to MQTT Broker!" in caplog.text
        # 驗證同時訂閱了生產與測試 Topic
        from unittest.mock import call
        calls = [call("pulse/production"), call("pulse/test")]
        client.subscribe.assert_has_calls(calls, any_order=True)

def test_main_config_check(monkeypatch, caplog):
    """
    [測試目的] 驗證配置缺失時主程式應報錯並停止。
    [實際行為] 刪除環境變數後執行 main()。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    monkeypatch.delenv("MQTT_BROKER", raising=False)
    with caplog.at_level(logging.ERROR):
        subscriber.main()
        assert "Missing config." in caplog.text

def test_data_source_production_saved_to_db(reset_globals):
    """
    [測試目的] 驗證來自生產 Topic 的訊息，寫入資料庫時 data_source 標記為 production。
    [實際行為] 使用生產 topic 發送訊息。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 72, "spo2": 98, "device_status": "NORMAL"}, topic="pulse/production")
    assert captured_writes[0]["data_source"] == "production"

def test_data_source_test_saved_to_db(reset_globals):
    """
    [測試目的] 驗證來自測試 Topic 的訊息，寫入資料庫時 data_source 標記為 test。
    [實際行為] 使用測試 topic 發送訊息。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 72, "spo2": 98, "device_status": "NORMAL"}, topic="pulse/test")
    assert captured_writes[0]["data_source"] == "test"

def test_completed_production_data_source_should_send_report(reset_globals):
    """
    [測試目的] 驗證生產環境收到 COMPLETED 訊號時，必須觸發報告生成。
    [實際行為] 生產環境發送 COMPLETED。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    with patch('report_manager.generate_and_send_report') as mock_report:
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"}, topic="pulse/production")
        session_id = subscriber.current_session_id
        simulate_mqtt_message({"device_status": "COMPLETED", "duration_sec": 60}, topic="pulse/production")
        mock_report.assert_called_once_with(session_id, 60)

def test_completed_test_data_source_should_not_send_report(reset_globals):
    """
    [測試目的] 驗證測試環境 (pulse/test) 收到 COMPLETED 訊號時，不應觸發報告生成。
    [實際行為] 測試環境發送 COMPLETED。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    with patch('report_manager.generate_and_send_report') as mock_report:
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"}, topic="pulse/test")
        simulate_mqtt_message({"device_status": "COMPLETED", "duration_sec": 60}, topic="pulse/test")
        mock_report.assert_not_called()

def test_reset_data_source_saved_to_db(reset_globals):
    """
    [測試目的] 驗證 RESET 訊號在不同來源下，data_source 欄位是否正確紀錄。
    [實際行為] 發送測試來源的 RESET。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    captured_writes = reset_globals
    simulate_mqtt_message({"device_status": "RESET"}, topic="pulse/test")
    assert captured_writes[-1]["analysis_status"] == "RESET"
    assert captured_writes[-1]["data_source"] == "test"

def test_analysis_status_persistence(reset_globals):
    """
    [測試目的] 驗證 MongoDB 僅保存 analysis_status (Python 趨勢判斷)，不含 device_status。
    [實際行為] 發送帶有 device_status 的訊息，檢查 DB 紀錄。
    [是否正確] 是。
    [可能 Flaky] 否。
    [建議修改] 無。
    """
    captured_writes = reset_globals
    # 模擬硬體判定為 WARNING，但 Python 分析 EMA/Delta 後判定為 NORMAL 的情境
    simulate_mqtt_message({"bpm": 80, "spo2": 96, "device_status": "WARNING"})
    assert "device_status" not in captured_writes[0]
    assert captured_writes[0]["analysis_status"] == "NORMAL"
