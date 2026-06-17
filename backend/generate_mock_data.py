import os
import random
import uuid
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

"""
【僅供 開發/測試 環境使用 - 切勿在正式環境執行】

腳本用途:
    生成符合「真實生活行為」的模擬歷史數據，用於測試 Streamlit 儀表板。
    包含：隨機量測時間、量測斷層 (忘記量測日)。

更新內容:
    1. 隨機中止 Session：Session 中有 5% 機率觸發手指移開，導致該次量測提早結束且不產生後續數據。
    2. 隨機量測次數：每天隨機 2~4 次量測。
    3. 隨機量測時間：量測時間在時段內隨機飄移。
    4. 遺漏量測日：10% 機率整天無數據。
"""

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_COL_NAME = os.getenv("MONGO_COL_NAME")

def get_target_date_range():
    """
    計算過去 6 個完整月份的範圍。
    """
    today = datetime.now(timezone.utc)
    first_day_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_date = first_day_this_month - timedelta(seconds=1)

    current_month_first = first_day_this_month
    for _ in range(6):
        current_month_first = (current_month_first - timedelta(days=1)).replace(day=1)

    start_date = current_month_first
    return start_date, end_date

def get_status(bpm, ema_bpm, delta_bpm, spo2):
    """
    同步 stream_processor.py 的階層式醫療狀態邏輯
    """
    if spo2 <= 90 or ema_bpm <= 50 or ema_bpm >= 140 or delta_bpm >= 50:
        return "DANGER"
    if spo2 >= 95 and (60 <= ema_bpm <= 100) and delta_bpm < 15:
        return "NORMAL"
    return "WARNING"

def generate_session_data(start_time):
    """
    為單次 Session 生成 30 筆樣本 (1 分鐘)。
    """
    samples = []
    bpm_window = deque(maxlen=15)
    spo2_window = deque(maxlen=15)
    session_id = str(uuid.uuid4())

    # 隨機決定是否為醫療異常 Session (約 5% 機率)
    is_medical_abnormal = random.random() < 0.05

    # 隨機決定是否觸發手指移開 (約 5% 機率)，若觸發則直接停止 Session 生成
    off_chip_start_index = -1
    if random.random() < 0.05:
        off_chip_start_index = random.randint(5, 25) # 在 Session 中間隨機發生

    for i in range(30):
        # 檢查是否觸發手指移開，若是則停止生成後續資料
        if off_chip_start_index > -1 and i >= off_chip_start_index:
            break

        current_time = start_time + timedelta(seconds=i * 2)

        if is_medical_abnormal:
            if random.random() < 0.7:
                raw_bpm = random.uniform(115, 145)
                raw_spo2 = random.uniform(88, 93)
            else:
                raw_bpm = random.uniform(65, 85)
                raw_spo2 = random.uniform(96, 100)
        else:
            raw_bpm = random.uniform(65, 85)
            raw_spo2 = random.uniform(96, 100)

        # 計算滑動視窗指標
        prev_xt_bpm = np.mean(bpm_window) if bpm_window else raw_bpm
        bpm_window.append(raw_bpm)
        spo2_window.append(raw_spo2)

        xt_bpm = np.mean(bpm_window)
        xt_spo2 = np.mean(spo2_window)
        delta_bpm = abs(raw_bpm - prev_xt_bpm)

        status = get_status(raw_bpm, xt_bpm, delta_bpm, raw_spo2)

        doc = {
            "timestamp": current_time,
            "session_id": session_id,
            "analysis_status": status,
            "avg_bpm": round(xt_bpm, 2),
            "ema_bpm": round(xt_bpm, 2),
            "delta_bpm": round(delta_bpm, 2),
            "spo2": round(xt_spo2, 2),
            "data_source": "test"
        }
        samples.append(doc)

    return samples

def get_random_time_in_window(day, start_hour, end_hour):
    """
    在指定的小時範圍內生成隨機時間戳。
    """
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

    # Security Cleanup
    logger.info("Cleaning up existing data in the target range...")
    result = collection.delete_many({
        "timestamp": {"$gte": start_range, "$lte": end_range},
        "data_source": "production"
    })
    logger.info(f"Deleted {result.deleted_count} documents.")

    # Time Windows
    windows = [
        (7, 10),   # 早上
        (12, 15),  # 中午/下午
        (18, 21),  # 晚上
        (21, 23)   # 深夜
    ]

    all_data = []
    current_day = start_range.date()
    end_day = end_range.date()

    logger.info("Generating realistic mock data...")
    while current_day <= end_day:
        # 1. 模擬「忘記量測日」(10% 機率)
        if random.random() < 0.10:
            current_day += timedelta(days=1)
            continue

        # 2. 隨機決定今天的量測次數 (2~4 次)
        num_sessions = random.randint(2, 4)

        # 3. 隨機挑選時段並生成數據
        selected_windows = random.sample(windows, num_sessions)
        for start_h, end_h in selected_windows:
            start_time = get_random_time_in_window(current_day, start_h, end_h)
            session_data = generate_session_data(start_time)
            all_data.extend(session_data)

        current_day += timedelta(days=1)

    # Batch Insert
    if all_data:
        logger.info(f"Inserting {len(all_data)} documents...")
        collection.insert_many(all_data)
        logger.info("Realistic data generation complete!")
    else:
        logger.warning("No data generated.")

if __name__ == "__main__":
    main()
