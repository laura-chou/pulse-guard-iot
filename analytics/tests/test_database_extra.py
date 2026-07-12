import pytest
import pandas as pd
from datetime import datetime
from core.database import get_mock_data

def test_get_mock_data():
    t = {
        'status_map': {'NORMAL': '正常', 'DANGER': '危險', 'WARNING': '警告'},
        'diag': {'low_spo2': '血氧低'},
        'tt_min_spo2': '最低血氧',
        'col_no': '編號',
        'col_time': '時間',
        'col_status': '狀態',
        'col_desc': '說明',
        'col_avg_bpm': '平均心率',
        'col_ema_bpm': 'EMA 心率',
        'col_spo2': '血氧'
    }

    # 測試 prod
    df_prod = get_mock_data("prod", t)
    assert not df_prod.empty
    assert df_prod.iloc[0]['狀態'] == '正常'

    # 測試 test
    df_test = get_mock_data("test", t)
    assert len(df_test) == 2
    assert df_test.iloc[0]['狀態'] == '危險'
    assert '血氧' in df_test.columns
