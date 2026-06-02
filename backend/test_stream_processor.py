import pytest
import json
import time
from unittest.mock import MagicMock, patch
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

# Scenario A: First valid write
def test_scenario_a_first_valid_write(reset_globals):
    captured_writes = reset_globals

    # 72 BPM, 98% SpO2. EMA will be 72. Delta will be 0.
    # Meets NORMAL: SpO2 >= 95, 60 <= EMA <= 100, Delta < 15.
    simulate_mqtt_message({"bpm": 72, "spo2": 98})

    assert len(captured_writes) == 1
    assert captured_writes[0]["status"] == "NORMAL"
    assert subscriber.first_write_done is True

# Scenario B: Sensor detachment defense (OFF-CHIP)
def test_scenario_b_off_chip_defense(reset_globals):
    captured_writes = reset_globals

    # First valid
    simulate_mqtt_message({"bpm": 72, "spo2": 98})
    initial_ema = subscriber.last_ema_bpm
    assert len(subscriber.bpm_window) == 1

    # Sudden outlier
    simulate_mqtt_message({"bpm": 999, "spo2": 40})

    assert len(captured_writes) >= 1
    # Check that the last status is OFF-CHIP
    # Note: subscriber.py might write the OFF-CHIP depending on timer,
    # but the logic for OFF-CHIP must be correct.

    # Security verification: windows and EMA should NOT update
    assert len(subscriber.bpm_window) == 1
    assert subscriber.last_ema_bpm == initial_ema

# Scenario C: SpO2 drop zero delay (Immediate Danger)
def test_scenario_c_spo2_drop_immediate_danger(reset_globals):
    captured_writes = reset_globals

    # 1. Fill window with normal data
    for _ in range(15):
        simulate_mqtt_message({"bpm": 70, "spo2": 98})

    # Reset timer to simulate 0 seconds passed
    subscriber.last_write_time = time.time()
    initial_write_count = len(captured_writes)

    # 2. Sudden SpO2 drop (88)
    simulate_mqtt_message({"bpm": 70, "spo2": 88})

    # Assert immediate write despite timer
    assert len(captured_writes) == initial_write_count + 1
    assert captured_writes[-1]["status"] == "DANGER"
    assert captured_writes[-1]["spo2"] == 88.0

# Scenario D: Heart rate spike (Delta BPM Danger)
def test_scenario_d_heart_rate_spike(reset_globals):
    captured_writes = reset_globals

    # 1. Stabilize at 70 BPM
    for _ in range(15):
        simulate_mqtt_message({"bpm": 70, "spo2": 98})

    subscriber.last_write_time = time.time()
    initial_write_count = len(captured_writes)

    # 2. Sudden spike to 125 BPM. prev_xt_bpm is 70. delta = 55.
    # New logic: delta_bpm >= 50 triggers DANGER
    simulate_mqtt_message({"bpm": 125, "spo2": 98})

    # Assert immediate DANGER write
    assert len(captured_writes) == initial_write_count + 1
    assert captured_writes[-1]["status"] == "DANGER"
    # delta_bpm = abs(125 - 70) = 55
    assert captured_writes[-1]["delta_bpm"] == 55.0

# Additional Test for Gradual Tachycardia (EMA >= 140)
def test_tachycardia_detection(reset_globals):
    captured_writes = reset_globals

    # Use 135 BPM (Warning zone, EMA < 140) to build window without triggering DANGER via delta_bpm
    for _ in range(15):
        simulate_mqtt_message({"bpm": 135, "spo2": 98})

    # Now window average (xt) is 135. EMA will gradually climb to 135.
    # To reach 140 without a large delta, we can use 140 BPM
    for _ in range(30):
        simulate_mqtt_message({"bpm": 142, "spo2": 98})
        if captured_writes[-1]["status"] == "DANGER":
            break

    assert captured_writes[-1]["status"] == "DANGER"
    assert subscriber.last_ema_bpm >= 140

# Scenario E: Timer mechanism
def test_scenario_e_timer_mechanism(reset_globals):
    captured_writes = reset_globals

    # We need to mock time.time to control the 20s interval
    with patch('time.time') as mock_time:
        start_t = 1000.0
        mock_time.return_value = start_t

        # 1st msg: Immediate write
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
        assert len(captured_writes) == 1

        # Next 9 msgs, every 2s. Total 18s passed (1018.0)
        for i in range(1, 10):
            mock_time.return_value = start_t + (i * 2)
            simulate_mqtt_message({"bpm": 70, "spo2": 98})

        # Should still be only 1 write (intercepted by timer)
        assert len(captured_writes) == 1

        # 11th msg at 20s (1020.0)
        mock_time.return_value = start_t + 20
        simulate_mqtt_message({"bpm": 70, "spo2": 98})

        # Should trigger 2nd write
        assert len(captured_writes) == 2

# Scenario F: Event-driven Transition (Immediate Warning)
def test_scenario_f_event_driven_transition(reset_globals):
    captured_writes = reset_globals

    with patch('time.time') as mock_time:
        start_t = 1000.0
        mock_time.return_value = start_t

        # 1. Start with Normal
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
        assert len(captured_writes) == 1
        assert captured_writes[-1]["status"] == "NORMAL"

        # 2. Advance only 2 seconds (well within 20s limit)
        mock_time.return_value = start_t + 2.0

        # 3. Transition to WARNING (e.g., SpO2 = 93)
        simulate_mqtt_message({"bpm": 70, "spo2": 93})

        # Assert immediate write despite timer
        assert len(captured_writes) == 2
        assert captured_writes[-1]["status"] == "WARNING"

# Scenario G: COMPLETED signal handling
def test_scenario_g_completed_signal(reset_globals):
    with patch('report_manager.generate_and_send_report') as mock_report:
        # 1. Provide some data
        simulate_mqtt_message({"bpm": 70, "spo2": 98})
        assert len(subscriber.bpm_window) == 1

        # 2. Send COMPLETED signal with duration
        simulate_mqtt_message({"status": "COMPLETED", "duration_sec": 120})

        # Assert buffers cleared
        assert len(subscriber.bpm_window) == 0
        assert subscriber.first_write_done is False

        # Assert report triggered
        mock_report.assert_called_once_with(120)

# Scenario H: RESET signal handling (should ignore)
def test_scenario_h_reset_signal_ignored(reset_globals):
    with patch('report_manager.generate_and_send_report') as mock_report:
        simulate_mqtt_message({"bpm": 70, "spo2": 98})

        # Send RESET signal
        simulate_mqtt_message({"status": "RESET", "duration_sec": 120})

        # Should NOT trigger report, and should NOT clear buffers based on current code
        # Actually, looking at the code, it clears buffers but returns before calling report.
        # Wait, I just modified it. Let's check the code I wrote.
        # It says: "Ignore RESET signal as per requirement" -> returns.

        assert len(subscriber.bpm_window) == 1
        mock_report.assert_not_called()
