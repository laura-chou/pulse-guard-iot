import pytest
import json
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from report_manager import generate_and_send_report, load_report_template

@pytest.fixture
def mock_mongo_data():
    local_tz = timezone(timedelta(hours=8))
    start_time = datetime(2026, 6, 10, 8, 30, 15, tzinfo=local_tz).astimezone(timezone.utc)
    end_time = datetime(2026, 6, 10, 8, 30, 45, tzinfo=local_tz).astimezone(timezone.utc)

    return [
        {"timestamp": start_time, "avg_bpm": 80, "spo2": 96, "status": "NORMAL"},
        {"timestamp": end_time, "avg_bpm": 82, "spo2": 95, "status": "NORMAL"}
    ]

@patch("report_manager.MongoClient")
@patch("report_manager.requests.post")
@patch("report_manager.os.getenv")
def test_generate_and_send_report_logic(mock_getenv, mock_post, mock_mongo, mock_mongo_data):
    # 設定 Mock
    mock_getenv.side_effect = lambda k: {
        "MONGO_URI": "mongodb://localhost",
        "MONGO_DB_NAME": "db",
        "MONGO_COL_NAME": "col",
        "LINE_CHANNEL_ACCESS_TOKEN": "token",
        "LINE_USER_ID": "user"
    }.get(k)

    mock_db = mock_mongo.return_value["db"]
    mock_col = mock_db["col"]
    mock_col.find.return_value.sort.return_value = mock_mongo_data

    mock_post.return_value.status_code = 200

    # 執行執行緒/函式
    generate_and_send_report("test_session", 30)

    # 驗證報表內容
    assert mock_post.called
    payload = mock_post.call_args[1]['json']
    template = payload['messages'][0]['contents']

    summary_box_contents = template["body"]["contents"][0]["contents"]

    # 檢查第 0 行：日期
    assert summary_box_contents[0]["contents"][1]["contents"][0]["text"] == "2026/06/10"
    # 檢查第 1 行：時間區間（結束時間應為精確的 開始時間 + 30秒 = 08:30:45）
    assert summary_box_contents[1]["contents"][1]["contents"][0]["text"] == "08:30:15 ~ 08:30:45 (30 sec)"

@patch("report_manager.MongoClient")
@patch("report_manager.requests.post")
@patch("report_manager.os.getenv")
def test_generate_and_send_report_interval_calculation(mock_getenv, mock_post, mock_mongo, mock_mongo_data):
    """驗證時間區間顯示邏輯：結束時間應為開始時間加上 duration_sec，而非最後一筆記錄的時間"""
    mock_getenv.side_effect = lambda k: {
        "MONGO_URI": "mongodb://localhost",
        "MONGO_DB_NAME": "db",
        "MONGO_COL_NAME": "col",
        "LINE_CHANNEL_ACCESS_TOKEN": "token",
        "LINE_USER_ID": "user"
    }.get(k)

    mock_db = mock_mongo.return_value["db"]
    mock_col = mock_db["col"]

    # 模擬數據：開始 08:30:00，最後記錄 08:30:40 (延遲)，但 duration 是 60
    local_tz = timezone(timedelta(hours=8))
    start_time = datetime(2026, 6, 10, 8, 30, 0, tzinfo=local_tz).astimezone(timezone.utc)
    last_record_time = datetime(2026, 6, 10, 8, 30, 40, tzinfo=local_tz).astimezone(timezone.utc)

    records = [
        {"timestamp": start_time, "avg_bpm": 80, "spo2": 96, "analysis_status": "NORMAL", "data_source": "production", "session_id": "test"},
        {"timestamp": last_record_time, "avg_bpm": 82, "spo2": 95, "analysis_status": "NORMAL", "data_source": "production", "session_id": "test"}
    ]
    mock_col.find.return_value.sort.return_value = records
    mock_post.return_value.status_code = 200

    generate_and_send_report("test", 60)

    payload = mock_post.call_args[1]['json']
    template = payload['messages'][0]['contents']
    interval_text = template["body"]["contents"][0]["contents"][1]["contents"][1]["contents"][0]["text"]

    # 開始 08:30:00 + 60s = 08:31:00
    assert "08:30:00 ~ 08:31:00 (1 min)" in interval_text

    # 檢查備註欄（Body 內容索引 2）
    remark_box = template["body"]["contents"][2]
    assert "整體生理數據表現良好" in remark_box["contents"][1]["text"]

@pytest.mark.parametrize("seconds, expected", [
    (30, "(30 sec)"),
    (60, "(1 min)"),
    (90, "(1 min 30 sec)"),
    (120, "(2 min)"),
    (125, "(2 min 5 sec)"),
])
def test_format_duration(seconds, expected):
    from report_manager import format_duration
    assert format_duration(seconds) == expected

def test_load_report_template():
    template = load_report_template()
    assert template is not None
    assert template["type"] == "bubble"
    # 驗證 report_manager.py 中預期的結構是否存在
    assert "body" in template
    summary_box = template["body"]["contents"][0]
    assert len(summary_box["contents"]) == 3 # 日期, 區間, 狀態
