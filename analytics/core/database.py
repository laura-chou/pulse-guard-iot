import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
import os
from core.config import local_tz

@st.cache_resource
def init_connection():
    """初始化 MongoDB 連線"""
    mongo_uri = os.getenv("MONGO_URI")
    return MongoClient(mongo_uri)

@st.cache_data(ttl=600)
def fetch_data(start_date, end_date, env="prod", device_id="MOCK_DEVICE_001"):
    """從 MongoDB 讀取數據並進行預處理，返回 (DataFrame, 是否發生錯誤)"""
    try:
        client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=2000)
        # 測試連線
        client.admin.command('ping')
    except Exception as e:
        # 返回空 DataFrame 與 錯誤標記
        return pd.DataFrame(), True

    db_name = os.getenv("MONGO_DB_NAME")
    col_name = os.getenv("MONGO_COL_NAME")

    # 將日期轉換為 UTC 時間戳進行查詢
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=local_tz).astimezone(pytz.utc)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=local_tz).astimezone(pytz.utc)

    db = client[db_name]
    collection = db[col_name]

    # 執行查詢並按時間排序
    projection = {
        "timestamp": 1,
        "analysis_status": 1,
        "avg_bpm": 1,
        "ema_bpm": 1,
        "delta_bpm": 1,
        "spo2": 1,
        "reason_codes": 1,
        "device_id": 1,
        "_id": 0
    }
    query = {
        "timestamp": {"$gte": start_dt, "$lte": end_dt},
        "analysis_status": {"$nin": ["RESET", "ABORTED"]},
        "data_source": env,
        "device_id": device_id
    }
    cursor = collection.find(query, projection).sort("timestamp", 1)

    df = pd.DataFrame(list(cursor))
    if not df.empty:
        # 處理時區轉換
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = df['timestamp'].dt.tz_localize(pytz.utc)
        df['timestamp'] = df['timestamp'].dt.tz_convert(local_tz)

        # 移除 MongoDB 內部 ID
        if '_id' in df.columns:
            df.drop(columns=['_id'], inplace=True)
    return df, False

def get_mock_data(env, t):
    """建立模擬數據供展示 (僅在資料庫連線失敗時)"""
    if env == "prod":
        mock_records = [
            {
                "timestamp": datetime.now(local_tz).strftime('%Y-%m-%d %H:%M:%S'),
                "analysis_status": "NORMAL",
                "avg_bpm": 72.4,
                "ema_bpm": 71.8,
                "delta_bpm": 0.5,
                "spo2": 98.5,
                "reason_codes": []
            }
        ]
    else:
        mock_records = [
            {
                "timestamp": datetime.now(local_tz).strftime('%Y-%m-%d %H:%M:%S'),
                "analysis_status": "DANGER",
                "avg_bpm": 145.0,
                "ema_bpm": 142.5,
                "delta_bpm": 52.0,
                "spo2": 88.0,
                "reason_codes": ["crit_low_spo2", "crit_high_hr", "arrhythmia"]
            },
            {
                "timestamp": (datetime.now(local_tz) - timedelta(minutes=2)).strftime('%Y-%m-%d %H:%M:%S'),
                "analysis_status": "WARNING",
                "avg_bpm": 105.0,
                "ema_bpm": 102.0,
                "delta_bpm": 10.0,
                "spo2": 94.0,
                "reason_codes": ["low_spo2"]
            }
        ]
    mock_data = pd.DataFrame(mock_records)

    # 轉換為顯示格式
    mock_display = mock_data.copy()

    from core.processor import translate_reason_codes
    mock_display['description'] = mock_display['reason_codes'].apply(lambda codes: translate_reason_codes(codes, t))

    mock_display['analysis_status'] = mock_display['analysis_status'].map(lambda x: t['status_map'].get(x, x))

    # 統一模擬數據的數值精度
    mock_display['avg_bpm'] = mock_display['avg_bpm'].round(1)
    mock_display['ema_bpm'] = mock_display['ema_bpm'].round(1)
    mock_display['spo2'] = mock_display['spo2'].round(0).astype(int)

    # 依照 app.py 中的表格順序進行欄位重新命名
    column_mapping = {
        'timestamp': t['col_time'],
        'analysis_status': t['col_status'],
        'description': t['col_desc'],
        'avg_bpm': t['col_avg_bpm'],
        'ema_bpm': t['col_ema_bpm'],
        'spo2': t['col_spo2']
    }
    mock_display = mock_display.reindex(columns=['timestamp', 'analysis_status', 'description', 'avg_bpm', 'ema_bpm', 'spo2'])
    mock_display.insert(0, t['col_no'], range(1, len(mock_display) + 1))
    mock_display = mock_display.rename(columns=column_mapping)
    return mock_display
