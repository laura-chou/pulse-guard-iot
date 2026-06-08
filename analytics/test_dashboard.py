import pytest
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import pytz
from unittest.mock import MagicMock, patch
import analytics.app as app

@pytest.fixture
def mock_mongo_client():
    with patch('analytics.app.MongoClient') as mock:
        yield mock

@pytest.fixture
def sample_df():
    local_tz = pytz.timezone('Asia/Taipei')
    data = {
        'timestamp': [
            datetime(2026, 5, 1, 10, 0).replace(tzinfo=local_tz),
            datetime(2026, 5, 1, 14, 0).replace(tzinfo=local_tz),
            datetime(2026, 5, 1, 20, 0).replace(tzinfo=local_tz),
            datetime(2026, 5, 2, 10, 0).replace(tzinfo=local_tz),
        ],
        'status': ['NORMAL', 'WARNING', 'DANGER', 'NORMAL'],
        'avg_bpm': [70, 110, 150, 72],
        'ema_bpm': [70.0, 105.0, 140.0, 71.5],
        'spo2': [98, 92, 88, 97]
    }
    return pd.DataFrame(data)

# 1. get_default_range()
def test_get_default_range():
    fixed_now = datetime(2026, 6, 15, 12, 0, 0).replace(tzinfo=pytz.timezone('Asia/Taipei'))
    with patch('analytics.app.datetime') as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        mock_datetime.combine = datetime.combine

        start_date, end_date = app.get_default_range()
        assert start_date == date(2026, 4, 1)
        assert end_date == date(2026, 5, 31)

# 2. fetch_data()
def test_fetch_data_normal(mock_mongo_client):
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_mongo_client.return_value.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_col

    naive_now = datetime(2026, 6, 9, 0, 0, 0)
    mock_cursor = [{'_id': '1', 'timestamp': naive_now, 'status': 'NORMAL'}]
    mock_col.find.return_value.sort.return_value = mock_cursor
    with patch('analytics.app.init_connection', return_value=mock_mongo_client.return_value):
        df = app.fetch_data.__wrapped__(date(2026, 5, 1), date(2026, 5, 31))
    assert df['timestamp'].dt.tz == pytz.timezone('Asia/Taipei')
    assert '_id' not in df.columns

    aware_now = datetime(2026, 6, 9, 0, 0, 0, tzinfo=pytz.utc)
    mock_cursor = [{'timestamp': aware_now, 'status': 'NORMAL'}]
    mock_col.find.return_value.sort.return_value = mock_cursor
    with patch('analytics.app.init_connection', return_value=mock_mongo_client.return_value):
        df = app.fetch_data.__wrapped__(date(2026, 5, 1), date(2026, 5, 31))
    assert df['timestamp'].dt.tz == pytz.timezone('Asia/Taipei')

def test_fetch_data_empty(mock_mongo_client):
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_mongo_client.return_value.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_col
    mock_col.find.return_value.sort.return_value = []
    with patch('analytics.app.init_connection', return_value=mock_mongo_client.return_value):
        df = app.fetch_data.__wrapped__(date(2026, 5, 1), date(2026, 5, 31))
    assert df.empty

# 3. Language selection
def test_language_selection():
    t_en, lang_en = app.get_translations('en')
    assert lang_en == 'en'
    t_zh, lang_zh = app.get_translations('zh')
    assert lang_zh == 'zh'

# 4. KPI calculations
def test_calculate_kpis(sample_df):
    total, danger, warning = app.calculate_kpis(sample_df)
    assert total == 4
    assert danger == 1
    assert warning == 1

# 5. Time-of-day categorization
def test_categorize_hour():
    bins = ["M", "A", "N"]
    assert app.categorize_hour(5, bins) == "M"
    assert app.categorize_hour(12, bins) == "A"
    assert app.categorize_hour(18, bins) == "N"

# 6. Color status logic
def test_color_status():
    t_zh, _ = app.get_translations('zh')
    assert app.color_status("危險", t_zh) == 'background-color: crimson; color: white'
    assert app.color_status("警告", t_zh) == 'background-color: orange; color: black'
    assert app.color_status("正常", t_zh) == ''

# 8. Edge cases
def test_edge_case_malformed_docs(mock_mongo_client):
    mock_db = MagicMock()
    mock_col = MagicMock()
    mock_mongo_client.return_value.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_col
    mock_col.find.return_value.sort.return_value = [{'status': 'NORMAL'}]
    with patch('analytics.app.init_connection', return_value=mock_mongo_client.return_value):
        with pytest.raises(KeyError):
            app.fetch_data.__wrapped__(date(2026, 5, 1), date(2026, 5, 31))

# --- UI Logic Tests ---
def test_main_ui_various_inputs(sample_df):
    with patch('analytics.app.st') as mock_st:
        # Case 1: No data
        mock_st.sidebar.date_input.return_value = (date(2026, 5, 1),)
        mock_st.sidebar.multiselect.return_value = ["NORMAL"]
        mock_st.query_params = {}
        with patch('analytics.app.fetch_data', return_value=pd.DataFrame()):
            app.main()
            mock_st.warning.assert_called()

        # Case 2: With data and zh
        mock_st.sidebar.date_input.return_value = (date(2026, 5, 1), date(2026, 5, 31))
        mock_st.sidebar.multiselect.return_value = ["NORMAL", "WARNING", "DANGER"]
        mock_st.query_params = {'lang': 'zh'}
        mock_st.columns.side_effect = [
            [MagicMock(), MagicMock(), MagicMock()],
            [MagicMock(), MagicMock()],
        ]
        mock_st.tabs.return_value = [MagicMock(), MagicMock(), MagicMock()]
        with patch('analytics.app.fetch_data', return_value=sample_df):
            app.main()
            mock_st.dataframe.assert_called()

def test_main_ui_no_abnormal(sample_df):
    normal_df = sample_df[sample_df['status'] == 'NORMAL'].copy()
    with patch('analytics.app.st') as mock_st:
        mock_st.sidebar.date_input.return_value = (date(2026, 5, 1), date(2026, 5, 31))
        mock_st.sidebar.multiselect.return_value = ["NORMAL"]
        mock_st.columns.side_effect = [[MagicMock()]*3, [MagicMock()]*2]
        mock_st.tabs.return_value = [MagicMock()]*3
        with patch('analytics.app.fetch_data', return_value=normal_df):
            app.main()
            mock_st.info.assert_called()

def test_init_connection(mock_mongo_client):
    with patch.dict('os.environ', {'MONGO_URI': 'mongodb://test'}):
        app.init_connection.__wrapped__()
        mock_mongo_client.assert_called_with('mongodb://test')
