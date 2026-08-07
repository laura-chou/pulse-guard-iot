import pytest
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import pytz
from unittest.mock import MagicMock, patch
import app
import core.i18n as i18n
import core.database as database
import core.processor as processor
import components.ui as ui

@pytest.fixture
def mock_mongo_client():
    """Mock MongoDB Client，避免測試時連接真實資料庫"""
    with patch('core.database.MongoClient') as mock:
        yield mock

@pytest.fixture
def sample_df():
    """提供模擬的生理量測 DataFrame 用於測試"""
    local_tz = pytz.timezone('Asia/Taipei')
    data = {
        'timestamp': [
            local_tz.localize(datetime(2026, 5, 1, 10, 0, 0)),
            local_tz.localize(datetime(2026, 5, 1, 10, 30, 0)), # 與上一筆同小時，用於測試去重
            local_tz.localize(datetime(2026, 5, 1, 14, 0, 0)),
            local_tz.localize(datetime(2026, 5, 1, 20, 0, 0)),
            local_tz.localize(datetime(2026, 5, 2, 10, 0, 0)),
        ],
        'analysis_status': ['NORMAL', 'WARNING', 'DANGER', 'NORMAL', 'NORMAL'],
        'avg_bpm': [70.4, 110.6, 150.1, 72.8, 75.0],
        'ema_bpm': [70.0, 105.0, 140.0, 71.5, 74.0],
        'spo2': [98.123, 92.456, 88.789, 97.0, 99.1]
    }
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

# 1. get_default_range()
def test_get_default_range():
    """
    [測試目的] 驗證預設日期範圍計算邏輯。
    """
    fixed_now = datetime.now(pytz.timezone('Asia/Taipei'))
    with patch('core.processor.datetime') as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        mock_datetime.combine = datetime.combine

        start_date, end_date = processor.get_default_range()
        expected_start = fixed_now.date() - timedelta(days=90)
        assert start_date == expected_start
        assert end_date == fixed_now.date()

# 2. fetch_data()
def test_fetch_data_logic(mock_mongo_client):
    """
    [測試目的] 驗證從 MongoDB 抓取數據的查詢條件與預處理。
    """
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_mongo_client.return_value.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_col

    naive_now = datetime(2026, 6, 9, 0, 0, 0)

    # 模擬 daily aggregation 回傳的資料
    mock_daily_cursor = [{
        'date': '2026-06-09',
        'bpm_min': 60.0,
        'bpm_max': 120.0,
        'bpm_mean': 80.0,
        'spo2_min': 95.0
    }]
    # 模擬 hourly aggregation 回傳的資料
    mock_hourly_cursor = [{
        'timestamp': naive_now,
        'analysis_status': 'NORMAL',
        'avg_bpm': 70,
        'spo2': 98,
        'device_id': 'MOCK_DEVICE_001'
    }]

    # 第一次調用 aggregate 回傳 daily cursor，第二次調用回傳 hourly cursor
    mock_col.aggregate.side_effect = [mock_daily_cursor, mock_hourly_cursor]
    mock_col.distinct.return_value = ["session-123"]

    # 測試正式環境
    with patch('core.database.MongoClient', return_value=mock_mongo_client.return_value):
        df_hourly, df_daily, err = database.fetch_data.__wrapped__(date(2026, 5, 1), date(2026, 5, 31), env="prod")

    # 驗證 distinct 呼叫
    mock_col.distinct.assert_called_once()

    # 驗證 aggregate 被呼叫兩次
    assert mock_col.aggregate.call_count == 2
    err_msg = "Expected aggregate to be called with query matching 'prod'"
    daily_call_args = mock_col.aggregate.call_args_list[0][0][0]
    assert daily_call_args[0]['$match']['data_source'] == "prod"
    assert daily_call_args[0]['$match']['session_id'] == {"$in": ["session-123"]}
    assert err is False

    assert df_hourly['timestamp'].dt.tz == pytz.timezone('Asia/Taipei')
    assert '_id' not in df_hourly.columns
    assert not df_daily.empty

# 3. Language selection
def test_language_selection():
    """
    [測試目的] 驗證多語系字掛與狀態對照表的正確性。
    """
    t_en, lang_en = i18n.get_translations('en')
    assert lang_en == 'en'
    assert t_en['status_map']['NORMAL'] == 'NORMAL'

    t_zh, lang_zh = i18n.get_translations('zh')
    assert lang_zh == 'zh'
    assert t_zh['status_map']['NORMAL'] == '正常'

# 4. KPI calculations
def test_calculate_kpis(sample_df):
    """
    [測試目的] 驗證 KPI (總數、危險數、警告數) 的計算邏輯。
    """
    total, danger, warning = processor.calculate_kpis(sample_df)
    assert total == 5
    assert danger == 1
    assert warning == 1

# 5. Data Aggregation: get_daily_summary
def test_get_daily_summary():
    """
    [測試目的] 驗證日聚合格式轉換邏輯。
    """
    raw_daily = pd.DataFrame({
        'date': ['2026-05-01', '2026-05-02'],
        'bpm_min': [70.4, 75.0],
        'bpm_max': [150.1, 75.0],
        'bpm_mean': [98.5, 75.0],
        'spo2_min': [88.789, 99.1]
    })
    summary = processor.get_daily_summary(raw_daily)
    assert len(summary) == 2
    assert summary.iloc[0]['date'] == date(2026, 5, 1)
    assert pytest.approx(summary.iloc[0]['bpm_min']) == 70.4
    assert pytest.approx(summary.iloc[0]['bpm_max']) == 150.1
    assert pytest.approx(summary.iloc[0]['spo2_min']) == 88.789

# 6. Data De-duplication: get_hourly_deduplicated
def test_get_hourly_deduplicated(sample_df):
    """
    [測試目的] 驗證「小時去重」機制現在為 Pass-through 直接回傳。
    """
    dedup = processor.get_hourly_deduplicated(sample_df)
    assert len(dedup) == len(sample_df)
    assert (dedup == sample_df).all().all()

# 7. UI Rendering: render_dataframe
@patch('components.ui.st.dataframe')
def test_render_dataframe(mock_st_dataframe):
    """
    [測試目的] 驗證 render_dataframe 會正確設定欄位、上色樣式並呼叫 st.dataframe。
    """
    t = {
        'col_time': 'Time',
        'col_avg_bpm': 'Avg BPM',
        'col_ema_bpm': 'EMA BPM',
        'col_spo2': 'SpO2',
        'col_desc': 'Description',
        'col_no': 'No.',
        'status_map': {
            'DANGER': 'DANGER_ZH',
            'WARNING': 'WARNING_ZH',
            'NORMAL': 'NORMAL_ZH'
        }
    }
    df = pd.DataFrame({
        'Time': ['2026-05-01 10:00:00'],
        'No.': [1],
        'Status': ['DANGER_ZH'],
        'Description': ['High heart rate'],
        'Avg BPM': [145.0],
        'EMA BPM': [142.5],
        'SpO2': [88]
    })

    ui.render_dataframe(df, t, 'Status')

    # 驗證 st.dataframe 確實被呼叫
    mock_st_dataframe.assert_called_once()
    args, kwargs = mock_st_dataframe.call_args

    # 驗證 hide_index 與 use_container_width
    assert kwargs.get('hide_index') is True
    assert kwargs.get('use_container_width') is True

    # 驗證 column_config 中的設定
    column_config = kwargs.get('column_config')
    assert 'Time' in column_config
    assert 'Avg BPM' in column_config
    assert 'EMA BPM' in column_config
    assert 'SpO2' in column_config
    assert 'Status' in column_config
    assert 'Description' in column_config
    assert 'No.' in column_config
