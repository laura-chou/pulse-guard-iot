import pytest
from backend.utils.status_utils import is_valid_bpm, is_valid_spo2, get_status, evaluate_session_health

def test_is_valid_bpm():
    assert is_valid_bpm(70) is True
    assert is_valid_bpm(30) is True
    assert is_valid_bpm(220) is True
    assert is_valid_bpm(29) is False
    assert is_valid_bpm(221) is False
    assert is_valid_bpm(None) is False

def test_is_valid_spo2():
    assert is_valid_spo2(98) is True
    assert is_valid_spo2(50) is True
    assert is_valid_spo2(100) is True
    assert is_valid_spo2(49) is False
    assert is_valid_spo2(101) is False
    assert is_valid_spo2(None) is False

def test_get_status():
    # DANGER cases
    assert get_status(70, 70, 0, 90) == "DANGER"
    assert get_status(70, 50, 0, 98) == "DANGER"
    assert get_status(70, 140, 0, 98) == "DANGER"
    assert get_status(120, 70, 50, 98) == "DANGER"

    # NORMAL cases
    assert get_status(70, 70, 0, 98) == "NORMAL"
    assert get_status(70, 60, 14, 95) == "NORMAL"

    # WARNING cases
    assert get_status(70, 70, 20, 98) == "WARNING"
    assert get_status(70, 55, 0, 98) == "WARNING"
    assert get_status(70, 110, 0, 98) == "WARNING"
    assert get_status(70, 70, 0, 93) == "WARNING"

def test_evaluate_session_health():
    # 情境 A: 持續危險 (DANGER >= 2)
    res = evaluate_session_health(["NORMAL", "DANGER", "WARNING", "DANGER"])
    assert "DANGER (持續危險)" in res[0]
    assert res[1] == "#DC3545"
    assert "持續性嚴重異常" in res[2]
    assert res[3] == "DANGER"

    # 情境 B: 突發性異常 (DANGER == 1)
    res = evaluate_session_health(["NORMAL", "WARNING", "DANGER", "NORMAL"])
    assert "WARNING (突發性異常提示)" in res[0]
    assert res[1] == "#FD7E14"
    assert "單次瞬時生理數值異常" in res[2]
    assert res[3] == "WARNING"

    # 情境 C: 狀態不穩定 (DANGER == 0, WARNING >= 30%)
    # 3/10 = 30%
    res = evaluate_session_health(["WARNING", "WARNING", "WARNING", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL", "NORMAL"])
    assert "WARNING (狀態不穩定)" in res[0]
    assert res[1] == "#FD7E14"
    assert "異常狀態比例偏高" in res[2]
    assert res[3] == "WARNING"

    # 情境 D: 完全正常
    res = evaluate_session_health(["NORMAL", "WARNING", "NORMAL", "NORMAL"]) # 1/4 = 25% < 30%
    assert "NORMAL (正常)" in res[0]
    assert res[1] == "#2B8A3E"
    assert "整體生理數據表現良好" in res[2]
    assert res[3] == "NORMAL"

    # 空清單
    res = evaluate_session_health([])
    assert "NORMAL" in res[0]
