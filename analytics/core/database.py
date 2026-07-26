import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
import os
from core.config import local_tz

@st.cache_data(ttl=600)
def fetch_data(start_date, end_date, env="prod", device_id="MOCK_DEVICE_001"):
    """從 MongoDB 讀取數據並進行降採樣，返回 (df_hourly, df_daily, 是否發生錯誤)"""
    try:
        client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=2000)
        # 測試連線
        client.admin.command('ping')
    except Exception as e:
        # 返回空 DataFrame 與 錯誤標記
        return pd.DataFrame(), pd.DataFrame(), True

    db_name = os.getenv("MONGO_DB_NAME")
    col_name = os.getenv("MONGO_COL_NAME")

    # 將日期轉換為 UTC 時間戳進行查詢
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=local_tz).astimezone(pytz.utc)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=local_tz).astimezone(pytz.utc)

    db = client[db_name]
    collection = db[col_name]

    # 1. 找出時間範圍內，所有包含 COMPLETED 標記的 session_id（時間序列唯讀集合之事件標記模式）
    completed_sessions_query = {
        "timestamp": {"$gte": start_dt, "$lte": end_dt},
        "analysis_status": "COMPLETED",
        "data_source": env,
        "device_id": device_id
    }
    completed_sessions = collection.distinct("session_id", completed_sessions_query)

    if not completed_sessions:
        return pd.DataFrame(), pd.DataFrame(), False

    # 2. 定義基本過濾條件，排除 COMPLETED/TIMEOUT 等事件紀錄
    query = {
        "timestamp": {"$gte": start_dt, "$lte": end_dt},
        "analysis_status": {"$nin": ["RESET", "ABORTED", "COMPLETED", "TIMEOUT"]},
        "data_source": env,
        "device_id": device_id,
        "session_id": {"$in": completed_sessions}
    }

    # 3. 執行「日聚合 (Daily Summary)」Aggregation Pipeline
    pipeline_daily = [
        {"$match": query},
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$timestamp",
                        "timezone": "Asia/Taipei"
                    }
                },
                "bpm_min": {"$min": "$avg_bpm"},
                "bpm_max": {"$max": "$avg_bpm"},
                "bpm_mean": {"$avg": "$avg_bpm"},
                "spo2_min": {"$min": "$spo2"}
            }
        },
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "_id": 0,
                "date": "$_id",
                "bpm_min": 1,
                "bpm_max": 1,
                "bpm_mean": 1,
                "spo2_min": 1
            }
        }
    ]
    cursor_daily = collection.aggregate(pipeline_daily)
    df_daily = pd.DataFrame(list(cursor_daily))
    if df_daily.empty:
        df_daily = pd.DataFrame(columns=['date', 'bpm_min', 'bpm_max', 'bpm_mean', 'spo2_min'])

    # 4. 執行「小時去重 (Hourly Deduplicated)」Aggregation Pipeline
    pipeline_hourly = [
        {"$match": query},
        {
            "$addFields": {
                "priority": {
                    "$switch": {
                        "branches": [
                            {"case": {"$eq": ["$analysis_status", "DANGER"]}, "then": 2},
                            {"case": {"$eq": ["$analysis_status", "WARNING"]}, "then": 1},
                            {"case": {"$eq": ["$analysis_status", "NORMAL"]}, "then": 0}
                        ],
                        "default": 0
                    }
                },
                "hour": {
                    "$dateToString": {
                        "format": "%Y-%m-%d %H:00:00",
                        "date": "$timestamp",
                        "timezone": "Asia/Taipei"
                    }
                }
            }
        },
        {"$sort": {"priority": -1, "timestamp": 1}},
        {
            "$group": {
                "_id": "$hour",
                "timestamp": {"$first": "$timestamp"},
                "analysis_status": {"$first": "$analysis_status"},
                "avg_bpm": {"$first": "$avg_bpm"},
                "ema_bpm": {"$first": "$ema_bpm"},
                "delta_bpm": {"$first": "$delta_bpm"},
                "spo2": {"$first": "$spo2"},
                "reason_codes": {"$first": "$reason_codes"},
                "device_id": {"$first": "$device_id"}
            }
        },
        {"$sort": {"timestamp": 1}}
    ]
    cursor_hourly = collection.aggregate(pipeline_hourly)
    df_hourly = pd.DataFrame(list(cursor_hourly))

    if not df_hourly.empty:
        # 處理時區轉換
        df_hourly['timestamp'] = pd.to_datetime(df_hourly['timestamp'])
        if df_hourly['timestamp'].dt.tz is None:
            df_hourly['timestamp'] = df_hourly['timestamp'].dt.tz_localize(pytz.utc)
        df_hourly['timestamp'] = df_hourly['timestamp'].dt.tz_convert(local_tz)

        # 移除 MongoDB 內部 ID
        if '_id' in df_hourly.columns:
            df_hourly.drop(columns=['_id'], inplace=True)
    else:
        df_hourly = pd.DataFrame(columns=['timestamp', 'analysis_status', 'avg_bpm', 'ema_bpm', 'delta_bpm', 'spo2', 'reason_codes', 'device_id'])

    return df_hourly, df_daily, False

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
