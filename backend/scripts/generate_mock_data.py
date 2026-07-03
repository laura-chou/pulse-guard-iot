import os
import random
import uuid
import logging
from datetime import datetime, timedelta, timezone, time as dt_time
from collections import deque
import numpy as np
from pymongo import MongoClient
from dotenv import load_dotenv
from backend.utils.status_utils import get_status_and_codes, EMA_ALPHA

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

"""
【僅供開發／測試環境使用】

用途：
    生成模擬歷史量測資料，用於驗證 Streamlit Dashboard
    與後端分析流程。

資料特性：
    - 模擬使用者日常量測行為
    - 模擬正常與異常生理狀態
    - 套用與正式系統一致的 EMA 平滑計算
    - 套用正式狀態判定邏輯(get_status)
    - 支援 device_id 與 session_id 識別
    - 自動排除非完整量測情境

注意：
    本腳本會清除指定測試裝置的既有測試資料，
    僅限開發與測試環境使用。
"""

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_COL_NAME = os.getenv("MONGO_COL_NAME")

DEVICE_ID = "MOCK_DEVICE_001"

def get_target_date_range():
    """
    計算過去 3 個完整月份的範圍。
    """
    today = datetime.now(timezone.utc)
    first_day_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_date = first_day_this_month - timedelta(seconds=1)

    current_month_first = first_day_this_month
    for _ in range(3):
        current_month_first = (current_month_first - timedelta(days=1)).replace(day=1)

    start_date = current_month_first
    return start_date, end_date

def generate_session_data(start_time):
    """
    為單次 Session 生成 30 筆樣本 (1 分鐘)。
    """
    samples = []
    bpm_window = deque(maxlen=15)
    spo2_window = deque(maxlen=15)
    session_id = str(uuid.uuid4())
    last_ema_bpm = None

    # 隨機決定是否為醫療異常 Session (約 10% 機率)
    is_medical_abnormal = random.random() < 0.10

    for i in range(30):
        current_time = start_time + timedelta(seconds=i * 2)

        if is_medical_abnormal:
            # 模擬異常波段
            if random.random() < 0.7:
                raw_bpm = random.uniform(115, 150)
                raw_spo2 = random.uniform(88, 93)
            else:
                raw_bpm = random.uniform(65, 85)
                raw_spo2 = random.uniform(96, 100)
        else:
            raw_bpm = random.uniform(65, 85)
            raw_spo2 = random.uniform(96, 100)

        # 1. 視窗平均計算 (MA)
        prev_xt_bpm = np.mean(bpm_window) if bpm_window else raw_bpm
        bpm_window.append(raw_bpm)
        spo2_window.append(raw_spo2)

        xt_bpm = float(np.mean(bpm_window))
        xt_spo2 = float(np.mean(spo2_window))

        # 2. 指數移動平均運算 (EMA)
        if last_ema_bpm is None:
            ema_bpm = xt_bpm
        else:
            ema_bpm = EMA_ALPHA * xt_bpm + (1 - EMA_ALPHA) * last_ema_bpm

        delta_bpm = abs(raw_bpm - prev_xt_bpm)
        last_ema_bpm = ema_bpm

        # 3. 獲取判定狀態與代碼 (引用核心 utils)
        status, reason_codes = get_status_and_codes(raw_bpm, ema_bpm, delta_bpm, raw_spo2)

        doc = {
            "timestamp": current_time,
            "session_id": session_id,
            "device_id": DEVICE_ID,
            "analysis_status": status,
            "reason_codes": reason_codes,
            "avg_bpm": round(xt_bpm, 2),
            "ema_bpm": round(ema_bpm, 2),
            "delta_bpm": round(delta_bpm, 2),
            "spo2": round(xt_spo2, 2),
            "data_source": "prod"
        }
        samples.append(doc)

    return samples

def get_random_time_in_window(day, start_hour, end_hour):
    random_hour = random.randint(start_hour, end_hour - 1)
    random_minute = random.randint(0, 59)
    random_second = random.randint(0, 59)
    return datetime.combine(day, dt_time(random_hour, random_minute, random_second)).replace(tzinfo=timezone.utc)

def main():
    if not all([MONGO_URI, MONGO_DB_NAME, MONGO_COL_NAME]):
        logger.error("Missing MongoDB environment variables.")
        return

    start_range, end_range = get_target_date_range()
    logger.info(f"Target Range: {start_range} to {end_range}")

    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB_NAME]
        collection = db[MONGO_COL_NAME]
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return

    # 僅清理自己產生的測試數據
    logger.info(f"Cleaning up existing 'prod' data for {DEVICE_ID}...")
    result = collection.delete_many({
        "data_source": "prod",
        "device_id": DEVICE_ID
    })
    logger.info(f"Deleted {result.deleted_count} documents.")

    # Time Windows
    windows = [(7, 10), (12, 15), (18, 21), (21, 23)]

    all_data = []
    current_day = start_range.date()
    end_day = end_range.date()

    logger.info("Generating realistic mock data with EMA logic...")
    while current_day <= end_day:
        if random.random() < 0.10: # 遺漏日
            current_day += timedelta(days=1)
            continue

        num_sessions = random.randint(2, 4)
        selected_windows = random.sample(windows, num_sessions)
        for start_h, end_h in selected_windows:
            start_time = get_random_time_in_window(current_day, start_h, end_h)
            session_data = generate_session_data(start_time)
            all_data.extend(session_data)

        current_day += timedelta(days=1)

    if all_data:
        logger.info(f"Inserting {len(all_data)} documents...")
        collection.insert_many(all_data)
        logger.info("Mock data generation complete!")
    else:
        logger.warning("No data generated.")

if __name__ == "__main__":
    main()
