import pytest
from backend.utils.status_utils import is_valid_bpm, is_valid_spo2, get_status, evaluate_session_health

def test_is_valid_bpm():
    assert is_valid_bpm(70) is True
    assert is_valid_bpm(25) is False
    assert is_valid_bpm(225) is False
    assert is_valid_bpm(None) is False

def test_is_valid_spo2():
    assert is_valid_spo2(98) is True
    assert is_valid_spo2(45) is False
    assert is_valid_spo2(101) is False
    assert is_valid_spo2(None) is False

def test_get_status():
    # NORMAL Case: SpO2>=95, 60<=EMA<=100, delta<15
    assert get_status(75, 75, 5, 98) == "NORMAL"

    # DANGER Case: SpO2<=90
    assert get_status(75, 75, 5, 89) == "DANGER"
    # DANGER Case: EMA<=50
    assert get_status(75, 45, 5, 98) == "DANGER"
    # DANGER Case: EMA>=140
    assert get_status(75, 145, 5, 98) == "DANGER"
    # DANGER Case: delta>=50
    assert get_status(75, 75, 55, 98) == "DANGER"

    # WARNING Case: Falling between DANGER and NORMAL
    # Not danger, but SpO2=93 (below 95)
    assert get_status(75, 75, 5, 93) == "WARNING"
    # Not danger, but EMA=110 (above 100)
    assert get_status(75, 110, 5, 98) == "WARNING"
    # Not danger, but delta=20 (above 15)
    assert get_status(75, 75, 20, 98) == "WARNING"

def test_evaluate_session_health():
    # 情境 A: 持續危險 (DANGER >= 2)
    res = evaluate_session_health(["NORMAL", "DANGER", "WARNING", "DANGER"])
    assert "DANGER" in res[0]
    assert res[1] == "#DC3545"

    # 情境 B: 突發性異常 (DANGER == 1)
    res = evaluate_session_health(["NORMAL", "DANGER", "NORMAL", "NORMAL"])
    assert "WARNING" in res[0]
    assert res[1] == "#FD7E14"

    # 情境 C: 狀態不穩定 (WARNING >= 30%)
    # 1/3 = 33% > 30%
    res = evaluate_session_health(["NORMAL", "NORMAL", "WARNING"])
    assert "WARNING" in res[0]
    assert res[1] == "#FCC419"

    # 情境 D: 完全正常
    res = evaluate_session_health(["NORMAL", "NORMAL", "NORMAL"])
    assert "NORMAL" in res[0]
    assert res[1] == "#2B8A3E"
