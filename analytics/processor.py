import pandas as pd
from datetime import datetime, timedelta
from config import local_tz

def calculate_kpis(df):
    """計算關鍵績效指標 (基於去重後的數據)"""
    # 1. 醫療健康指標
    total_samples = len(df)
    danger_count = len(df[df['analysis_status'] == "DANGER"])
    warning_count = len(df[df['analysis_status'] == "WARNING"])

    return total_samples, danger_count, warning_count

def get_daily_summary(df):
    """將原始數據按日聚合，用於趨勢圖"""
    if df.empty:
        # 返回具有正確結構但為空的 DataFrame，避免後續聚合報錯
        return pd.DataFrame(columns=['date', 'bpm_min', 'bpm_max', 'bpm_mean', 'spo2_min'])

    df_copy = df.copy()
    df_copy['date'] = df_copy['timestamp'].dt.date
    summary = df_copy.groupby('date').agg({
        'avg_bpm': ['min', 'max', 'mean'],
        'spo2': 'min'
    }).reset_index()
    # 扁平化多級索引列名
    summary.columns = ['date', 'bpm_min', 'bpm_max', 'bpm_mean', 'spo2_min']
    return summary

def get_hourly_deduplicated(df):
    """將原始數據按小時去重，僅保留每小時最高優先級的事件"""
    if df.empty:
        return df

    # 定義優先級：DANGER > WARNING > NORMAL
    priority_map = {"DANGER": 2, "WARNING": 1, "NORMAL": 0}
    df_hourly = df.copy()
    df_hourly['priority'] = df_hourly['analysis_status'].map(priority_map)
    df_hourly['hour'] = df_hourly['timestamp'].dt.floor('h')

    # 按小時分組，並找出每組中優先級最高的索引
    # 若優先級相同，則保留最早出現的紀錄
    idx = df_hourly.groupby('hour')['priority'].idxmax()
    return df_hourly.loc[idx].drop(columns=['priority', 'hour'])

def get_default_range():
    """計算過去三個月的範圍 (90天前到今天)"""
    today = datetime.now(local_tz).date()
    start_date = today - timedelta(days=90)
    return start_date, today
