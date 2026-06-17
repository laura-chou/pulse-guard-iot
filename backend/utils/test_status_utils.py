import pytest
from backend.utils.status_utils import is_valid_bpm, is_valid_spo2, get_status, get_highest_status

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

def test_get_highest_status():
    assert get_highest_status(["NORMAL", "NORMAL"]) == "NORMAL"
    assert get_highest_status(["NORMAL", "WARNING", "NORMAL"]) == "WARNING"
    assert get_highest_status(["NORMAL", "DANGER", "WARNING"]) == "DANGER"
    assert get_highest_status([]) == "NORMAL"
