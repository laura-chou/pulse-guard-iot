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
    生成「過去 6 個完整月份」的模擬歷史數據，用於測試 Streamlit 儀表板。
    （例如：若在 2026 年 6 月執行，將自動生成 2025 年 12 月 1 日至 2026 年 5 月 31 日的數據）

警告事項:
    本腳本具備【自動清理機制】。
    執行時，會先自動「刪除」該 6 個月範圍內所有由本腳本產生的模擬數據（篩選條件為 data_source="production"），
    接著才寫入新數據，以避免資料重複累積！
"""

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_COL_NAME = os.getenv("MONGO_COL_NAME")

def get_target_date_range():
    """
    計算過去 6 個完整月份的範圍。
    例如：若今天是 2026-06-15，則返回 (2025-12-01, 2026-05-31)。
    """
    today = datetime.now(timezone.utc)
    # 本月第一天
    first_day_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 目標範圍結束日 (上個月最後一天)
    end_date = first_day_this_month - timedelta(seconds=1)

    # 目標範圍起始日 (往前推 6 個月的第一天)
    # 邏輯：先找到上個月的第一天，再往回推 5 個月
    current_month_first = first_day_this_month
    for _ in range(6):
        current_month_first = (current_month_first - timedelta(days=1)).replace(day=1)

    start_date = current_month_first

    return start_date, end_date

def get_status(bpm, ema_bpm, delta_bpm, spo2):
    """
    同步 stream_processor.py 的階層式醫療狀態邏輯
    """
    # 1. DANGER
    if spo2 <= 90 or ema_bpm <= 50 or ema_bpm >= 140 or delta_bpm >= 50:
        return "DANGER"

    # 2. NORMAL
    if spo2 >= 95 and (60 <= ema_bpm <= 100) and delta_bpm < 15:
        return "NORMAL"

    # 3. WARNING
    return "WARNING"

def generate_session_data(start_time):
    """
    為單次 Session 生成 30 筆樣本 (持續 1 分鐘，每 2 秒一筆)。
    """
    samples = []
    bpm_window = deque(maxlen=15)
    spo2_window = deque(maxlen=15)
    session_id = str(uuid.uuid4())

    # 隨機決定是否為異常 Session (約 5% 機率)
    is_abnormal_session = random.random() < 0.05

    for i in range(30):
        current_time = start_time + timedelta(seconds=i * 2)

        if is_abnormal_session:
            # 模擬異常狀態
            if random.random() < 0.7:
                raw_bpm = random.uniform(115, 145)
                raw_spo2 = random.uniform(88, 93)
            else:
                raw_bpm = random.uniform(65, 85)
                raw_spo2 = random.uniform(96, 100)
        else:
            # 正常波動
            raw_bpm = random.uniform(65, 85)
            raw_spo2 = random.uniform(96, 100)

        # 計算滑動視窗指標
        prev_xt_bpm = np.mean(bpm_window) if bpm_window else raw_bpm
        bpm_window.append(raw_bpm)
        spo2_window.append(raw_spo2)

        xt_bpm = np.mean(bpm_window)
        xt_spo2 = np.mean(spo2_window)
        delta_bpm = abs(raw_bpm - prev_xt_bpm)

        # 模擬狀態
        status = get_status(raw_bpm, xt_bpm, delta_bpm, raw_spo2)

        doc = {
            "timestamp": current_time,
            "session_id": session_id,
            "analysis_status": status,
            "avg_bpm": round(xt_bpm, 2),
            "ema_bpm": round(xt_bpm, 2),
            "delta_bpm": round(delta_bpm, 2),
            "spo2": round(xt_spo2, 2), # 存儲視窗平均值以支援報表
            "data_source": "production"
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
        },
        "data_source": "production"
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
