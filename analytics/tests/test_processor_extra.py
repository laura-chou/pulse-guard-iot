import pytest
import pandas as pd
from core.processor import translate_reason_codes, get_daily_summary, get_hourly_deduplicated

def test_translate_reason_codes():
    t_zh = {
        'tt_week': '週別',
        'diag': {
            'low_spo2': '血氧偏低',
            'high_hr': '心率過高'
        }
    }
    t_en = {
        'tt_week': 'Week',
        'diag': {
            'low_spo2': 'Low SpO2',
            'high_hr': 'High Heart Rate'
        }
    }

    # 中文測試
    assert translate_reason_codes(['low_spo2', 'high_hr'], t_zh) == "血氧偏低、心率過高"
    # 英文測試
    assert translate_reason_codes(['low_spo2', 'high_hr'], t_en) == "Low SpO2, High Heart Rate"
    # 空值或非列表測試
    assert translate_reason_codes(None, t_zh) == ""
    assert translate_reason_codes("not a list", t_zh) == ""
    # 未定義代碼
    assert translate_reason_codes(['unknown'], t_zh) == "unknown"

def test_get_daily_summary_empty():
    df = pd.DataFrame(columns=['timestamp', 'avg_bpm', 'spo2', 'analysis_status'])
    summary = get_daily_summary(df)
    assert summary.empty
    assert list(summary.columns) == ['date', 'bpm_min', 'bpm_max', 'bpm_mean', 'spo2_min']

def test_get_hourly_deduplicated_empty():
    df = pd.DataFrame(columns=['timestamp', 'analysis_status'])
    dedup = get_hourly_deduplicated(df)
    assert dedup.empty
