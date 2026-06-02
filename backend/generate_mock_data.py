import os
import random
import logging
from datetime import datetime, timedelta, timezone, time as dt_time
from collections import deque
import numpy as np
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

def get_target_date_range():
    """
    Calculates the first day and last day of the past two full months.
    Example: If today is 2026-06-15, it returns (2026-04-01, 2026-05-31).
    """
    today = datetime.now(timezone.utc)
    # First day of the current month
    first_day_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # End of the target range (Last day of the previous month)
    end_date = first_day_this_month - timedelta(seconds=1)

    # First day of the previous month
    first_day_prev_month = (first_day_this_month - timedelta(days=1)).replace(day=1)

    # First day of the month before that
    start_date = (first_day_prev_month - timedelta(days=1)).replace(day=1)

    return start_date, end_date

def get_status(bpm, spo2):
    """
    Medical Logic:
    DANGER: spo2 <= 90 OR bpm <= 50 OR bpm >= 140
    WARNING: 91 <= spo2 <= 94 OR 51 <= bpm <= 59 OR 101 <= bpm <= 139
    NORMAL: Else
    """
    if spo2 <= 90 or bpm <= 50 or bpm >= 140:
        return "DANGER"
    elif (91 <= spo2 <= 94) or (51 <= bpm <= 59) or (101 <= bpm <= 139):
        return "WARNING"
    else:
        return "NORMAL"

def generate_session_data(start_time):
    """
    Generates 30 samples (1 minute duration, 2s interval) starting from start_time.
    """
    samples = []
    bpm_window = deque(maxlen=15)

    # Randomly decide if this session contains abnormal data (~5% probability)
    is_abnormal_session = random.random() < 0.05

    for i in range(30):
        current_time = start_time + timedelta(seconds=i * 2)

        if is_abnormal_session:
            # Simulate abnormal state
            if random.random() < 0.7: # Higher chance for abnormality in an abnormal session
                bpm = random.uniform(115, 145)
                spo2 = random.uniform(88, 93)
            else:
                bpm = random.uniform(65, 85)
                spo2 = random.uniform(96, 100)
        else:
            # Normal fluctuation
            bpm = random.uniform(65, 85)
            spo2 = random.uniform(96, 100)

        # Calculate sliding window metrics
        prev_xt_bpm = np.mean(bpm_window) if bpm_window else bpm
        bpm_window.append(bpm)
        xt_bpm = np.mean(bpm_window)
        delta_bpm = abs(bpm - prev_xt_bpm)

        status = get_status(bpm, spo2)

        doc = {
            "timestamp": current_time,
            "status": status,
            "avg_bpm": round(xt_bpm, 2),
            "ema_bpm": round(xt_bpm, 2), # Simplified as requested
            "delta_bpm": round(delta_bpm, 2),
            "spo2": round(spo2, 2),
            "avg_spo2": round(spo2, 2) # Simplified for mock purposes
        }
        samples.append(doc)

    return samples

def main():
    if not all([MONGO_URI, MONGO_DB_NAME, MONGO_COL_NAME]):
        logger.error("Missing MongoDB environment variables.")
        return

    start_range, end_range = get_target_date_range()
    logger.info(f"Target Range: {start_range} to {end_range}")

    # Connect to MongoDB
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB_NAME]
        collection = db[MONGO_COL_NAME]
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return

    # Security: Delete existing data in the range
    logger.info("Cleaning up existing data in the target range...")
    result = collection.delete_many({
        "timestamp": {
            "$gte": start_range,
            "$lte": end_range
        }
    })
    logger.info(f"Deleted {result.deleted_count} documents.")

    # Generate Data
    all_data = []
    current_day = start_range.date()
    end_day = end_range.date()

    # 08:00, 12:30, 20:00
    session_times = [dt_time(8, 0), dt_time(12, 30), dt_time(20, 0)]

    logger.info("Generating mock data...")
    while current_day <= end_day:
        for s_time in session_times:
            # Combine current day with session time and make it UTC
            start_time = datetime.combine(current_day, s_time).replace(tzinfo=timezone.utc)
            session_data = generate_session_data(start_time)
            all_data.extend(session_data)

        current_day += timedelta(days=1)

    # Batch Insert
    if all_data:
        logger.info(f"Inserting {len(all_data)} documents...")
        collection.insert_many(all_data)
        logger.info("Data generation complete!")
    else:
        logger.warning("No data generated.")

if __name__ == "__main__":
    main()
