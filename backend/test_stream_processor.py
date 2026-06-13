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
    [預期行為] 1. 資料庫應有一筆紀錄。 2. 分析狀態為 NORMAL。 3. first_write_done 標記為 True。
    """
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 72, "spo2": 98, "device_status": "NORMAL"})
    assert len(captured_writes) == 1
    assert captured_writes[0]["analysis_status"] == "NORMAL"
    assert captured_writes[0]["device_status"] == "NORMAL"
    assert subscriber.first_write_done is True
    assert subscriber.current_session_id is not None

def test_scenario_b_off_chip_defense(reset_globals):
    """
    [測試目的] 驗證 OFF-CHIP (無效數值) 是否不會污染 EMA 計算與 Sliding Window。
    [預期行為] 1. 有效資料後接無效資料，EMA 與 Window 長度應保持不變。
    """
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 72, "spo2": 98, "device_status": "NORMAL"})
    initial_ema = subscriber.last_ema_bpm
    assert len(subscriber.bpm_window) == 1

    # 發送無效數值 (OFF-CHIP)
    simulate_mqtt_message({"bpm": 999, "spo2": 40, "device_status": "DANGER"})
    assert len(subscriber.bpm_window) == 1
    assert subscriber.last_ema_bpm == initial_ema

def test_scenario_c_spo2_drop_immediate_danger(reset_globals):
    """
    [測試目的] 驗證 SpO2 掉落至危險範圍時，是否不計較 20s 定時器立即寫入 DANGER 狀態。
    [預期行為] 資料庫應新增一筆 DANGER 紀錄。
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

def test_scenario_d_heart_rate_spike(reset_globals):
    """
    [測試目的] 驗證心率劇烈變化 (|ΔBPM| >= 50) 時，是否立即觸發 DANGER。
    [預期行為] delta_bpm 為 55，狀態為 DANGER。
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
    assert captured_writes[-1]["device_status"] == "WARNING"
    assert captured_writes[-1]["delta_bpm"] == 55.0

def test_tachycardia_detection(reset_globals):
    """
    [測試目的] 驗證持續高心率導致 EMA 達到 DANGER 門檻 (>= 140)。
    [預期行為] 當 EMA 爬升至 140 以上，狀態變為 DANGER。
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
    [預期行為] 20 秒內的重複 NORMAL 不會寫入，超過 20 秒則寫入。
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
    [預期行為] 不受 20s 定時器限制，發生轉變即寫入。
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
        assert captured_writes[-1]["device_status"] == "NORMAL"

def test_scenario_g_completed_signal(reset_globals):
    """
    [測試目的] 驗證 COMPLETED 訊號是否正確觸發報告生成並重置系統狀態。
    [預期行為] 呼叫 report_manager，清空 Window 與 Session。
    """
    with patch('report_manager.generate_and_send_report') as mock_report:
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})
        session_id = subscriber.current_session_id
        assert session_id is not None

        simulate_mqtt_message({"device_status": "COMPLETED", "duration_sec": 120})
        # 驗證狀態重置
        assert len(subscriber.bpm_window) == 0
        assert subscriber.current_session_id is None
        assert subscriber.last_write_time == 0
        # 驗證報告呼叫
        mock_report.assert_called_once_with(session_id, 120)

def test_scenario_h_reset_signal(reset_globals):
    """
    [測試目的] 驗證 RESET 訊號是否寫入資料庫並重置系統，但不生成報告。
    [預期行為] 寫入 RESET 紀錄，清空 Window 與 Session，不呼叫報告生成。
    """
    with patch('report_manager.generate_and_send_report') as mock_report:
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})
        session_id = subscriber.current_session_id

        simulate_mqtt_message({"device_status": "RESET"})
        # 驗證資料庫紀錄
        assert reset_globals[-1]["device_status"] == "RESET"
        assert reset_globals[-1]["session_id"] == session_id
        # 驗證重置
        assert subscriber.current_session_id is None
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
    [預期行為] 確保 90.1 是 WARNING，90.0 是 DANGER 等精確判斷。
    """
    assert subscriber.get_status(70, ema, delta, spo2) == expected

def test_session_id_immediate_generation(reset_globals):
    """
    [測試目的] 驗證一旦有有效資料，Session ID 必須立即生成，不論是否寫入資料庫。
    [預期行為] 即使尚未觸發寫入，Session ID 也不能為 None。
    """
    # 這裡我們手動讓 should_write 為 False 的情境 (比如剛寫入完又要寫入)
    simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"}) # 第一筆，會生成 Session 並寫入
    first_session = subscriber.current_session_id
    assert first_session is not None

    # 重置標記但不清空 Session，模擬後續量測
    subscriber.last_write_time = time.time()
    simulate_mqtt_message({"bpm": 71, "spo2": 98, "device_status": "NORMAL"})
    assert subscriber.current_session_id == first_session

def test_off_chip_immediate_write(reset_globals):
    """
    [測試目的] 驗證變更為 OFF-CHIP 狀態時，是否立即寫入資料庫。
    [預期行為] 從 NORMAL 變為 OFF-CHIP 應立即觸發一筆資料庫紀錄。
    """
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"}) # NORMAL
    initial_count = len(captured_writes)

    # 立即發送無效資料
    simulate_mqtt_message({"bpm": 0, "spo2": 0, "device_status": "DANGER"}) # OFF-CHIP
    assert len(captured_writes) == initial_count + 1
    assert captured_writes[-1]["analysis_status"] == "OFF-CHIP"

def test_mongodb_insert_failure_preservation(reset_globals, caplog):
    """
    [測試目的] 驗證 MongoDB 寫入失敗時，系統狀態（last_analysis_status, last_write_time）不應更新，以便下次重試。
    """
    subscriber.collection.insert_one.side_effect = Exception("DB Fail")
    subscriber.last_analysis_status = "OLD_STATUS"
    subscriber.last_write_time = 1000.0

    with caplog.at_level(logging.ERROR):
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"})
        assert "MongoDB Insert Error" in caplog.text
        # 狀態應保持舊值，不因失敗而標記為已更新
        assert subscriber.last_analysis_status == "OLD_STATUS"
        assert subscriber.last_write_time == 1000.0

def test_ema_calculation_correctness(reset_globals):
    """
    [測試目的] 驗證 EMA 計算公式：ema = 0.3 * current + 0.7 * last
    """
    subscriber.last_ema_bpm = None
    simulate_mqtt_message({"bpm": 100, "spo2": 98, "device_status": "NORMAL"}) # 初始 EMA = 100
    assert subscriber.last_ema_bpm == 100.0

    simulate_mqtt_message({"bpm": 110, "spo2": 98, "device_status": "NORMAL"}) # xt_bpm = (100+110)/2 = 105; EMA = 0.3*105 + 0.7*100 = 101.5
    assert subscriber.last_ema_bpm == pytest.approx(101.5)

def test_sliding_window_behavior(reset_globals):
    """
    [測試目的] 驗證心率滑動視窗 (Sliding Window) 的長度限制與先進先出行為。
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
    """
    with patch('report_manager.generate_and_send_report') as mock_report:
        # 確保當前無 Session
        subscriber.current_session_id = None
        simulate_mqtt_message({"status": "COMPLETED", "duration_sec": 60})
        mock_report.assert_not_called()

def test_on_connect_success(caplog):
    """驗證 MQTT 連線成功時的訂閱行為"""
    client = MagicMock()
    with caplog.at_level(logging.INFO):
        subscriber.on_connect(client, None, None, 0)
        assert "Connected to MQTT Broker!" in caplog.text
        # 驗證同時訂閱了生產與測試 Topic
        from unittest.mock import call
        calls = [call("pulse/production"), call("pulse/test")]
        client.subscribe.assert_has_calls(calls, any_order=True)

def test_main_config_check(monkeypatch, caplog):
    """驗證配置缺失時主程式應報錯並停止"""
    monkeypatch.delenv("MQTT_BROKER", raising=False)
    with caplog.at_level(logging.ERROR):
        subscriber.main()
        assert "Missing config." in caplog.text

def test_data_source_production_saved_to_db(reset_globals):
    """
    [測試目的] 驗證來自生產 Topic 的訊息，寫入資料庫時 data_source 標記為 production。
    """
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 72, "spo2": 98, "device_status": "NORMAL"}, topic="pulse/production")
    assert captured_writes[0]["data_source"] == "production"

def test_data_source_test_saved_to_db(reset_globals):
    """
    [測試目的] 驗證來自測試 Topic 的訊息，寫入資料庫時 data_source 標記為 test。
    """
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 72, "spo2": 98, "device_status": "NORMAL"}, topic="pulse/test")
    assert captured_writes[0]["data_source"] == "test"

def test_completed_production_data_source_should_send_report(reset_globals):
    """
    [測試目的] 驗證生產環境收到 COMPLETED 訊號時，必須觸發報告生成。
    """
    with patch('report_manager.generate_and_send_report') as mock_report:
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"}, topic="pulse/production")
        session_id = subscriber.current_session_id
        simulate_mqtt_message({"device_status": "COMPLETED", "duration_sec": 60}, topic="pulse/production")
        mock_report.assert_called_once_with(session_id, 60)

def test_completed_test_data_source_should_not_send_report(reset_globals):
    """
    [測試目的] 驗證測試環境 (pulse/test) 收到 COMPLETED 訊號時，不應觸發報告生成。
    """
    with patch('report_manager.generate_and_send_report') as mock_report:
        simulate_mqtt_message({"bpm": 70, "spo2": 98, "device_status": "NORMAL"}, topic="pulse/test")
        simulate_mqtt_message({"device_status": "COMPLETED", "duration_sec": 60}, topic="pulse/test")
        mock_report.assert_not_called()

def test_reset_data_source_saved_to_db(reset_globals):
    """
    [測試目的] 驗證 RESET 訊號在不同來源下，data_source 欄位是否正確紀錄。
    """
    captured_writes = reset_globals
    simulate_mqtt_message({"device_status": "RESET"}, topic="pulse/test")
    assert captured_writes[-1]["device_status"] == "RESET"
    assert captured_writes[-1]["data_source"] == "test"

def test_dual_status_persistence(reset_globals):
    """
    [測試目的] 驗證 MongoDB 同時保存 device_status (硬體判斷) 與 analysis_status (Python 趨勢判斷)。
    [預期行為] 紀錄中應包含兩個明確區分的狀態欄位。
    """
    captured_writes = reset_globals
    # 模擬硬體判定為 WARNING，但 Python 分析 EMA/Delta 後判定為 NORMAL 的情境
    simulate_mqtt_message({"bpm": 80, "spo2": 96, "device_status": "WARNING"})
    assert captured_writes[0]["device_status"] == "WARNING"
    assert captured_writes[0]["analysis_status"] == "NORMAL"
