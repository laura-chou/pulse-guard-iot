import pytest
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import pytz
from unittest.mock import MagicMock, patch
import analytics.app as app
import analytics.i18n as i18n
import analytics.database as database
import analytics.processor as processor
import analytics.components as components

@pytest.fixture
def mock_mongo_client():
    """Mock MongoDB Client，避免測試時連接真實資料庫"""
    with patch('analytics.database.MongoClient') as mock:
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
    [預期行為] 應返回過去兩個完整日曆月的起始與結束日。
    """
    fixed_now = datetime.now(pytz.timezone('Asia/Taipei'))
    with patch('processor.datetime') as mock_datetime:
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
    [預期行為] 1. 查詢應過濾正確的 data_source。 2. 應排除 RESET 狀態。 3. 返回轉為本地時區的 DataFrame。
    """
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_mongo_client.return_value.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_col

    naive_now = datetime(2026, 6, 9, 0, 0, 0)
    mock_cursor = [{'timestamp': naive_now, 'analysis_status': 'NORMAL', 'avg_bpm': 70, 'spo2': 98}]
    mock_col.find.return_value.sort.return_value = mock_cursor

    # 測試正式環境
    with patch('database.MongoClient', return_value=mock_mongo_client.return_value):
        df, err = database.fetch_data.__wrapped__(date(2026, 5, 1), date(2026, 5, 31), env="prod")

    args, _ = mock_col.find.call_args
    assert args[0]['data_source'] == "prod"
    assert err is False

    # 測試測試環境
    with patch('database.MongoClient', return_value=mock_mongo_client.return_value):
        df, err = database.fetch_data.__wrapped__(date(2026, 5, 1), date(2026, 5, 31), env="test")

    args, _ = mock_col.find.call_args
    assert args[0]['data_source'] == "test"
    assert args[0]['analysis_status']['$nin'] == ["RESET", "ABORTED"]
    assert err is False

    assert df['timestamp'].dt.tz == pytz.timezone('Asia/Taipei')
    assert '_id' not in df.columns

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
    # 5 筆中有 1 DANGER, 1 WARNING.
    assert total == 5
    assert danger == 1
    assert warning == 1

# 5. Data Aggregation: get_daily_summary
def test_get_daily_summary(sample_df):
    """
    [測試目的] 驗證日聚合邏輯 (用於生理趨勢圖)。
    """
    summary = processor.get_daily_summary(sample_df)
    assert len(summary) == 2 # 5/1 與 5/2
    # 5/1 的統計驗證
    assert pytest.approx(summary.iloc[0]['bpm_min']) == 70.4
    assert pytest.approx(summary.iloc[0]['bpm_max']) == 150.1
    assert pytest.approx(summary.iloc[0]['spo2_min']) == 88.789

# 6. Data De-duplication: get_hourly_deduplicated
def test_get_hourly_deduplicated(sample_df):
    """
    [測試目的] 驗證「小時去重」機制：每小時僅保留最高優先級事件 (DANGER > WARNING > NORMAL)。
    [預期行為] 5/1 10:00 有 NORMAL 與 WARNING，應保留 WARNING。
    """
    dedup = processor.get_hourly_deduplicated(sample_df)
    may1_10am_row = dedup[(dedup['timestamp'].dt.date == date(2026, 5, 1)) & (dedup['timestamp'].dt.hour == 10)]
    assert len(may1_10am_row) == 1
    assert may1_10am_row.iloc[0]['analysis_status'] == 'WARNING'
    assert len(dedup) == 4 # 原本 5 筆，10:00 那小時被去重為 1 筆

# 7. Color status logic
def test_color_status():
    """
    [測試目的] 驗證表格顏色標記邏輯。
    """
    t_zh, _ = i18n.get_translations('zh')
    assert "crimson" in components.color_status("危險", t_zh)
    assert "orange" in components.color_status("警告", t_zh)
    assert components.color_status("正常", t_zh) == ''

# 8. UI Logic Tests
def test_main_ui_various_inputs(sample_df):
    """
    [測試目的] 模擬 Streamlit UI 的渲染流程。
    """
    with patch('analytics.app.st') as mock_st:
        # 設置 columns 的 side_effect 以應對所有可能的調用
        # 1. KPI 欄位 (3 cols)
        # 2. Expander 內部 (2 cols)
        # 3. 統計欄位 (2 cols)
        mock_st.columns.side_effect = lambda n: [MagicMock() for _ in range(n)]

        # 情況 1: 查無數據 (僅顯示警告，不再顯示模擬數據)
        mock_st.sidebar.date_input.return_value = (date(2026, 5, 1), date(2026, 5, 31))
        mock_st.sidebar.multiselect.return_value = ["NORMAL"]
        mock_st.query_params = {}
        with patch('analytics.app.fetch_data', return_value=(pd.DataFrame(), False)):
            app.main()
            # 驗證是否顯示了查無數據的警告
            mock_st.warning.assert_any_call("No data found for the selected range.")
            # 確保沒有顯示模擬數據提示
            with pytest.raises(AssertionError):
                mock_st.info.assert_any_call("Displaying feature sample data:")

        # 情況 2: 資料庫連線失敗 (觸發模擬數據與 Expander)
        with patch('analytics.app.fetch_data', return_value=(pd.DataFrame(), True)):
            app.main()
            mock_st.error.assert_any_call("Database connection failed, showing mock data for reference.")
            mock_st.info.assert_any_call("Displaying feature sample data:")

        # 情況 3: 測試環境切換 (透過 URL 參數)
        mock_st.query_params = {'env': 'test'}
        with patch('analytics.app.fetch_data', return_value=(pd.DataFrame(), False)):
            app.main()
            # 驗證測試模式警告
            mock_st.warning.assert_any_call("Currently in Test Mode. Viewing simulated test data.")

        # 情況 4: 正常載入並切換至中文
        mock_st.sidebar.date_input.return_value = (date(2026, 5, 1), date(2026, 5, 31))
        mock_st.sidebar.multiselect.return_value = ["NORMAL", "WARNING", "DANGER"]
        mock_st.query_params = {'lang': 'zh'}

        mock_st.tabs.return_value = [MagicMock(), MagicMock(), MagicMock()]
        with patch('analytics.app.fetch_data', return_value=(sample_df, False)):
            app.main()
            mock_st.plotly_chart.assert_called()
            # 驗證 Tab 3 中是否有 expander 調用
            mock_st.expander.assert_called()

def test_init_connection(mock_mongo_client):
    """驗證連線初始化是否正確讀取環境變數"""
    with patch.dict('os.environ', {'MONGO_URI': 'mongodb://test'}):
        database.init_connection.__wrapped__()
        mock_mongo_client.assert_called_with('mongodb://test')
