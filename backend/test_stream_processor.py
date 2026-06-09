import pytest
import json
import time
import logging
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime, timezone
import stream_processor as subscriber

# Mock environment variables before importing or running logic
@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER", "localhost")
    monkeypatch.setenv("MQTT_PORT", "1883")
    monkeypatch.setenv("MQTT_USER", "user")
    monkeypatch.setenv("MQTT_PASSWORD", "pass")
    monkeypatch.setenv("MQTT_TOPIC", "test/topic")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB_NAME", "test_db")
    monkeypatch.setenv("MONGO_COL_NAME", "test_col")

@pytest.fixture
def reset_globals():
    # Reset all relevant global variables in subscriber.py
    subscriber.bpm_window.clear()
    subscriber.spo2_window.clear()
    subscriber.last_ema_bpm = None
    subscriber.last_status = None
    subscriber.first_write_done = False
    subscriber.last_write_time = 0

    # Mock the MongoDB collection and capture writes
    subscriber.collection = MagicMock()
    captured_writes = []
    subscriber.collection.insert_one.side_effect = lambda x: captured_writes.append(x)

    return captured_writes

def simulate_mqtt_message(payload_dict):
    msg = MagicMock()
    msg.payload = json.dumps(payload_dict).encode()
    subscriber.on_message(None, None, msg)

# --- EXISTING TESTS ---

def test_scenario_a_first_valid_write(reset_globals):
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 72, "spo2": 98})
    assert len(captured_writes) == 1
    assert captured_writes[0]["status"] == "NORMAL"
    assert subscriber.first_write_done is True

def test_scenario_b_off_chip_defense(reset_globals):
    captured_writes = reset_globals
    simulate_mqtt_message({"bpm": 72, "spo2": 98})
    initial_ema = subscriber.last_ema_bpm
    assert len(subscriber.bpm_window) == 1
    simulate_mqtt_message({"bpm": 999, "spo2": 40})
    assert len(captured_writes) >= 1
    assert len(subscriber.bpm_window) == 1
    assert subscriber.last_ema_bpm == initial_ema

def test_scenario_c_spo2_drop_immediate_danger(reset_globals):
    captured_writes = reset_globals
    for _ in range(15):
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
    subscriber.last_write_time = time.time()
    initial_write_count = len(captured_writes)
    simulate_mqtt_message({"bpm": 70, "spo2": 88})
    assert len(captured_writes) == initial_write_count + 1
    assert captured_writes[-1]["status"] == "DANGER"
    assert captured_writes[-1]["spo2"] == 88.0

def test_scenario_d_heart_rate_spike(reset_globals):
    captured_writes = reset_globals
    for _ in range(15):
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
    subscriber.last_write_time = time.time()
    initial_write_count = len(captured_writes)
    simulate_mqtt_message({"bpm": 125, "spo2": 98})
    assert len(captured_writes) == initial_write_count + 1
    assert captured_writes[-1]["status"] == "DANGER"
    assert captured_writes[-1]["delta_bpm"] == 55.0

def test_tachycardia_detection(reset_globals):
    captured_writes = reset_globals
    for _ in range(15):
        simulate_mqtt_message({"bpm": 135, "spo2": 98})
    for _ in range(30):
        simulate_mqtt_message({"bpm": 142, "spo2": 98})
        if captured_writes[-1]["status"] == "DANGER":
            break
    assert captured_writes[-1]["status"] == "DANGER"
    assert subscriber.last_ema_bpm >= 140

def test_scenario_e_timer_mechanism(reset_globals):
    captured_writes = reset_globals
    with patch('time.time') as mock_time:
        start_t = 1000.0
        mock_time.return_value = start_t
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
        assert len(captured_writes) == 1
        for i in range(1, 10):
            mock_time.return_value = start_t + (i * 2)
            simulate_mqtt_message({"bpm": 70, "spo2": 98})
        assert len(captured_writes) == 1
        mock_time.return_value = start_t + 20
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
        assert len(captured_writes) == 2

def test_scenario_f_event_driven_transition(reset_globals):
    captured_writes = reset_globals
    with patch('time.time') as mock_time:
        start_t = 1000.0
        mock_time.return_value = start_t
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
        assert len(captured_writes) == 1
        assert captured_writes[-1]["status"] == "NORMAL"
        mock_time.return_value = start_t + 2.0
        simulate_mqtt_message({"bpm": 70, "spo2": 93})
        assert len(captured_writes) == 2
        assert captured_writes[-1]["status"] == "WARNING"

def test_scenario_g_completed_signal(reset_globals):
    with patch('report_manager.generate_and_send_report') as mock_report:
        subscriber.last_status = "NORMAL"
        subscriber.last_write_time = 1234.5
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
        assert len(subscriber.bpm_window) == 1
        simulate_mqtt_message({"status": "COMPLETED", "duration_sec": 120})
        assert len(subscriber.bpm_window) == 0
        assert subscriber.first_write_done is False
        assert subscriber.last_status is None
        assert subscriber.last_write_time == 0
        mock_report.assert_called_once_with(120)

def test_scenario_h_reset_signal_ignored(reset_globals):
    with patch('report_manager.generate_and_send_report') as mock_report:
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
        simulate_mqtt_message({"status": "RESET", "duration_sec": 120})
        assert len(subscriber.bpm_window) == 1
        mock_report.assert_not_called()

# --- NEW TESTS ---

@pytest.mark.parametrize("spo2, ema, delta, expected", [
    (90, 70, 0, "DANGER"), (91, 70, 0, "WARNING"),
    (94, 70, 0, "WARNING"), (95, 70, 0, "NORMAL"),
    (98, 50, 0, "DANGER"), (98, 51, 0, "WARNING"),
    (98, 59, 0, "WARNING"), (98, 60, 0, "NORMAL"),
    (98, 100, 0, "NORMAL"), (98, 101, 0, "WARNING"),
    (98, 139, 0, "WARNING"), (98, 140, 0, "DANGER"),
    (98, 70, 14, "NORMAL"), (98, 70, 15, "WARNING"),
    (98, 70, 49, "WARNING"), (98, 70, 50, "DANGER"),
])
def test_get_status_boundaries(spo2, ema, delta, expected):
    assert subscriber.get_status(70, ema, delta, spo2) == expected

def test_on_message_empty_json(reset_globals):
    simulate_mqtt_message({})
    assert len(reset_globals) == 0

def test_on_message_malformed_json(reset_globals, caplog):
    msg = MagicMock()
    msg.payload = b'{"invalid": json'
    with caplog.at_level(logging.ERROR):
        subscriber.on_message(None, None, msg)
        assert "Error:" in caplog.text

def test_mongodb_insert_failure_state_preservation(reset_globals, caplog):
    subscriber.collection.insert_one.side_effect = Exception("DB Fail")
    subscriber.last_status = "OLD_STATUS"
    subscriber.last_write_time = 1000.0

    with caplog.at_level(logging.ERROR):
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
        assert "MongoDB Insert Error: DB Fail" in caplog.text
        # Verify state NOT updated
        assert subscriber.last_status == "OLD_STATUS"
        assert subscriber.last_write_time == 1000.0

def test_on_connect_success(caplog):
    client = MagicMock()
    with caplog.at_level(logging.INFO):
        subscriber.on_connect(client, None, None, 0)
        assert "Connected to MQTT Broker!" in caplog.text
        client.subscribe.assert_called_once_with("test/topic")

def test_on_connect_failure(caplog):
    client = MagicMock()
    with caplog.at_level(logging.ERROR):
        subscriber.on_connect(client, None, None, 1)
        assert "Failed to connect, return code 1" in caplog.text

def test_ema_calculation_correctness(reset_globals):
    subscriber.last_ema_bpm = None
    simulate_mqtt_message({"bpm": 100, "spo2": 98})
    assert subscriber.last_ema_bpm == 100.0
    simulate_mqtt_message({"bpm": 110, "spo2": 98})
    assert subscriber.last_ema_bpm == pytest.approx(101.5)

def test_sliding_window_behavior(reset_globals):
    for i in range(15):
        simulate_mqtt_message({"bpm": 60 + i, "spo2": 95})
    assert len(subscriber.bpm_window) == 15
    simulate_mqtt_message({"bpm": 80, "spo2": 95})
    assert len(subscriber.bpm_window) == 15
    assert subscriber.bpm_window[0] == 61.0

def test_completed_signal_full_reset(reset_globals):
    with patch('report_manager.generate_and_send_report') as mock_report:
        subscriber.last_status = "DANGER"
        subscriber.last_write_time = 5000.0
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
        simulate_mqtt_message({"status": "COMPLETED", "duration_sec": 0})
        assert len(subscriber.bpm_window) == 0
        assert subscriber.last_ema_bpm is None
        assert subscriber.first_write_done is False
        assert subscriber.last_status is None
        assert subscriber.last_write_time == 0
        mock_report.assert_not_called()

def test_main_missing_config(monkeypatch, caplog):
    monkeypatch.delenv("MQTT_BROKER", raising=False)
    with caplog.at_level(logging.ERROR):
        subscriber.main()
        assert "Missing config." in caplog.text

def test_main_full_success():
    with patch('stream_processor.MongoClient') as mock_mongo:
        with patch('stream_processor.mqtt.Client') as mock_mqtt:
            mock_instance = mock_mqtt.return_value
            mock_instance.loop_forever.side_effect = Exception("Exit")
            with pytest.raises(Exception, match="Exit"):
                subscriber.main()
            mock_instance.username_pw_set.assert_called_with("user", "pass")
            mock_instance.tls_set.assert_called()
            mock_instance.connect.assert_called_with("localhost", 1883, 60)
            mock_instance.loop_forever.assert_called()

def test_main_mongodb_connection_failure(caplog):
    with patch('stream_processor.MongoClient', side_effect=Exception("Mongo Fail")):
        with patch('stream_processor.mqtt.Client') as mock_mqtt:
            mock_mqtt.return_value.connect.side_effect = Exception("Stop")
            with caplog.at_level(logging.ERROR):
                subscriber.main()
                assert "DB Error: Mongo Fail" in caplog.text

def test_main_mqtt_connection_failure(caplog):
    with patch('stream_processor.MongoClient'):
        with patch('stream_processor.mqtt.Client') as mock_mqtt:
            mock_mqtt.return_value.connect.side_effect = Exception("MQTT Fail")
            with caplog.at_level(logging.ERROR):
                subscriber.main()
                assert "MQTT Error: MQTT Fail" in caplog.text

@pytest.mark.parametrize("bpm, spo2", [
    (20, 98), (70, 40), (20, 40),
])
def test_on_message_off_chip_detection(reset_globals, bpm, spo2):
    captured_writes = reset_globals
    with patch('time.time') as mock_time:
        start_t = 1000.0
        mock_time.return_value = start_t
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
        mock_time.return_value = start_t + 21.0
        simulate_mqtt_message({"bpm": bpm, "spo2": spo2})
        assert len(captured_writes) == 2
        assert captured_writes[1]["status"] == "OFF-CHIP"

def test_on_message_exception(caplog):
    msg = MagicMock()
    msg.payload.decode.side_effect = Exception("Fail")
    with caplog.at_level(logging.ERROR):
        subscriber.on_message(None, None, msg)
        assert "Error: Fail" in caplog.text
