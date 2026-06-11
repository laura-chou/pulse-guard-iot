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
    # Setup mocks
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

    # Run function
    generate_and_send_report("test_session", 30)

    # Verify report content
    assert mock_post.called
    payload = mock_post.call_args[1]['json']
    template = payload['messages'][0]['contents']

    summary_box_contents = template["body"]["contents"][0]["contents"]

    # Check Row 0: Date
    assert summary_box_contents[0]["contents"][1]["contents"][0]["text"] == "2026/06/10"
    # Check Row 1: Time Interval
    assert summary_box_contents[1]["contents"][1]["contents"][0]["text"] == "08:30:15 ~ 08:30:45 (共 30 秒)"
    # Check Row 2: Status
    assert "NORMAL" in summary_box_contents[2]["contents"][1]["contents"][0]["text"]

def test_load_report_template():
    template = load_report_template()
    assert template is not None
    assert template["type"] == "bubble"
    # Verify the structure we expect in report_manager.py exists
    assert "body" in template
    summary_box = template["body"]["contents"][0]
    assert len(summary_box["contents"]) == 3 # Date, Interval, Status
