import os
import json
import requests
import logging
from datetime import datetime, timedelta, timezone
from backend.utils.status_utils import evaluate_session_health
from pymongo import MongoClient
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_COL_NAME = os.getenv("MONGO_COL_NAME")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
LINE_PUSH_API = "https://api.line.me/v2/bot/message/push"

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "report_template.json")

def load_report_template():
    """Loads the LINE Flex Message template from JSON file."""
    if not os.path.exists(TEMPLATE_PATH):
        logger.error(f"Template file not found at {TEMPLATE_PATH}")
        return None
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to parse template JSON: {e}")
        return None

def format_duration(seconds):
    """Formats duration according to rules: <60s -> X sec, multi-60s -> Y min, else Y min X sec."""
    seconds = int(seconds)
    if seconds < 60:
        return f"({seconds} sec)"

    minutes = seconds // 60
    rem_seconds = seconds % 60

    if rem_seconds == 0:
        return f"({minutes} min)"
    else:
        return f"({minutes} min {rem_seconds} sec)"

def generate_and_send_report(session_id, duration_sec):
    """
    Retrieves records from MongoDB for the given session_id,
    calculates statistics, and sends a report via LINE Messaging API (Flex Message).
    """
    if not session_id:
        logger.warning("No session_id provided for report.")
        return

    # 1. Data Retrieval
    try:
        client = MongoClient(MONGO_URI, tz_aware=True)
        db = client[MONGO_DB_NAME]
        collection = db[MONGO_COL_NAME]

        # 同步查詢條件：status -> analysis_status，並限定 production 來源
        query = {
            "session_id": session_id,
            "analysis_status": {"$ne": "RESET"},
            "data_source": "production"
        }
        records = list(collection.find(query).sort("timestamp", 1))
    except Exception as e:
        logger.error(f"Failed to fetch data from MongoDB for session {session_id}: {e}")
        return

    if not records:
        logger.warning(f"No valid records found for session {session_id} for reporting.")
        return

    # 2. Precise Time and Duration Calculation
    start_time_utc = records[0]["timestamp"]
    end_time_utc = records[-1]["timestamp"]

    # Calculate actual duration based on first and last record timestamps
    actual_duration = (end_time_utc - start_time_utc).total_seconds()

    # Pre-calculate localized times (for future template rendering)
    local_tz = timezone(timedelta(hours=8)) # Asia/Taipei
    start_time_local = start_time_utc.astimezone(local_tz)
    end_time_local = end_time_utc.astimezone(local_tz)

    # Format for template (Asia/Taipei)
    measure_date_str = start_time_local.strftime("%Y/%m/%d")

    # Use passed duration_sec for formatted display and end time calculation
    display_duration = int(duration_sec) if duration_sec is not None else int(actual_duration)

    # Calculate displayed end time: start time + duration
    display_end_time_local = start_time_local + timedelta(seconds=display_duration)

    formatted_duration = format_duration(display_duration)
    time_interval_str = f"{start_time_local.strftime('%H:%M:%S')} ~ {display_end_time_local.strftime('%H:%M:%S')} {formatted_duration}"

    logger.info(f"Report for session {session_id}: {measure_date_str} {time_interval_str}")

    # 3. Statistics Calculation
    bpms = [r.get("avg_bpm") or r.get("ema_bpm") for r in records if (r.get("avg_bpm") or r.get("ema_bpm"))]
    spo2s = [r.get("spo2") for r in records if r.get("spo2")]

    if not bpms or not spo2s:
        logger.warning("No physiological data points available for stats.")
        return

    avg_bpm = sum(bpms) / len(bpms)
    avg_spo2 = sum(spo2s) / len(spo2s)

    # 4. Fill Template
    status_text, status_color, remark, highest_risk = evaluate_session_health([r.get("analysis_status", "NORMAL") for r in records])
    template = load_report_template()
    if not template:
        return

    # Mapping logic based on NEW JSON structure
    body_contents = template["body"]["contents"]

    # Body -> Box 0 (Summary Box)
    summary_box_contents = body_contents[0]["contents"]
    # Row 0: Measurement Date
    summary_box_contents[0]["contents"][1]["contents"][0]["text"] = measure_date_str
    # Row 1: Time Interval
    summary_box_contents[1]["contents"][1]["contents"][0]["text"] = time_interval_str
    # Row 2: Status
    summary_box_contents[2]["contents"][1]["contents"][0]["text"] = status_text
    summary_box_contents[2]["contents"][1]["contents"][0]["color"] = status_color

    # Body -> Box 1 (Averages Row)
    stats_row_contents = body_contents[1]["contents"]
    stats_row_contents[0]["contents"][1]["text"] = f"{avg_bpm:.0f}" # BPM
    stats_row_contents[1]["contents"][1]["text"] = f"{avg_spo2:.0f}" # SpO2

    # Body -> Box 2 (Remark Box)
    remark_box_contents = body_contents[2]["contents"]
    remark_box_contents[1]["text"] = remark

    # 5. Send to LINE Messaging API
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        logger.error("LINE credentials not set.")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "flex",
                "altText": f"量測報告: {highest_risk}",
                "contents": template
            }
        ]
    }

    try:
        response = requests.post(LINE_PUSH_API, headers=headers, json=payload)
        if response.status_code == 200:
            logger.info("LINE Flex Message sent successfully.")
        else:
            logger.error(f"Failed to send LINE Flex Message: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error sending LINE Flex Message: {e}")

if __name__ == "__main__":
    pass
