import os
import json
import requests
import logging
from datetime import datetime, timedelta, timezone
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

def generate_and_send_report(duration_sec):
    """
    Retrieves records from MongoDB for the measured duration,
    calculates statistics, and sends a report via LINE Messaging API (Flex Message).
    """
    if not duration_sec or duration_sec <= 0:
        logger.warning("Invalid duration provided for report.")
        return

    # 1. Time range calculation
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(seconds=duration_sec)

    # 2. Data Retrieval
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB_NAME]
        collection = db[MONGO_COL_NAME]

        query = {
            "timestamp": {"$gte": start_time, "$lte": end_time},
            "status": {"$nin": ["OFF-CHIP", "RESET"]}
        }
        records = list(collection.find(query).sort("timestamp", 1))
    except Exception as e:
        logger.error(f"Failed to fetch data from MongoDB for report: {e}")
        return

    if not records:
        logger.warning(f"No records found between {start_time} and {end_time} for reporting.")
        return

    # 3. Statistics Calculation
    bpms = [r.get("avg_bpm") or r.get("ema_bpm") for r in records if (r.get("avg_bpm") or r.get("ema_bpm"))]
    spo2s = [r.get("spo2") for r in records if r.get("spo2")]

    if not bpms or not spo2s:
        logger.warning("No physiological data points available for stats.")
        return

    avg_bpm = sum(bpms) / len(bpms)
    avg_spo2 = sum(spo2s) / len(spo2s)

    warning_count = 0
    danger_count = 0
    highest_risk = "NORMAL"
    prev_status = None

    for r in records:
        status = r.get("status", "NORMAL")
        if status == "DANGER":
            highest_risk = "DANGER"
        elif status == "WARNING" and highest_risk == "NORMAL":
            highest_risk = "WARNING"

        if status != prev_status:
            if status == "WARNING":
                warning_count += 1
            elif status == "DANGER":
                danger_count += 1
        prev_status = status

    # 4. Fill Template
    template = load_report_template()
    if not template:
        return

    m, s = divmod(int(duration_sec), 60)
    duration_zh = f"{m}分{s}秒"
    duration_en = f"{duration_sec} seconds" if m == 0 else f"{m} min {s} sec"

    # Define dynamic translations and colors
    # DANGER: #DC3545, WARNING: #FD7E14, NORMAL: #28A745
    status_config = {
        "DANGER":  {"zh": "🚨 危險", "en": "DANGER",  "color": "#DC3545"},
        "WARNING": {"zh": "⚠️ 警告", "en": "WARNING", "color": "#FD7E14"},
        "NORMAL":  {"zh": "✅ 正常", "en": "NORMAL",  "color": "#28A745"}
    }
    config = status_config.get(highest_risk, status_config["NORMAL"])

    # Mapping logic based on NEW JSON structure
    body_contents = template["body"]["contents"]

    # Body -> Box 0 (Summary Box)
    info_box = body_contents[0]["contents"]
    # Row 0: Duration
    info_box[0]["contents"][1]["contents"][0]["text"] = duration_zh
    info_box[0]["contents"][1]["contents"][1]["text"] = duration_en
    # Row 1: Status
    info_box[1]["contents"][1]["contents"][0]["text"] = config["zh"]
    info_box[1]["contents"][1]["contents"][0]["color"] = config["color"]
    info_box[1]["contents"][1]["contents"][1]["text"] = config["en"]
    info_box[1]["contents"][1]["contents"][1]["color"] = config["color"]

    # Body -> Box 2 (Averages Row)
    stats_row = body_contents[2]["contents"]
    stats_row[0]["contents"][1]["text"] = f"{avg_bpm:.0f}" # BPM
    stats_row[1]["contents"][1]["text"] = f"{avg_spo2:.0f}" # SpO2

    # Body -> Box 3 (Counts Column)
    counts_box = body_contents[3]["contents"]
    # Row 0: Warning
    counts_box[0]["contents"][1]["contents"][0]["text"] = f"{warning_count} 次"
    counts_box[0]["contents"][1]["contents"][1]["text"] = f"{warning_count} {'time' if warning_count <= 1 else 'times'}"
    # Row 1: Danger
    counts_box[1]["contents"][1]["contents"][0]["text"] = f"{danger_count} 次"
    counts_box[1]["contents"][1]["contents"][1]["text"] = f"{danger_count} {'time' if danger_count <= 1 else 'times'}"

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
                "altText": f"PulseGuard 量測報告: {highest_risk}",
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
