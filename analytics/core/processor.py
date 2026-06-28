import pandas as pd
from datetime import datetime, timedelta
from core.config import local_tz

def calculate_kpis(df):
    """計算關鍵績效指標 (基於去重後的數據)"""
    total_samples = len(df)
    danger_count = len(df[df['analysis_status'] == "DANGER"])
    warning_count = len(df[df['analysis_status'] == "WARNING"])
    return total_samples, danger_count, warning_count

def get_daily_summary(df):
    """將原始數據按日聚合，用於趨勢圖"""
    if df.empty:
        return pd.DataFrame(columns=['date', 'bpm_min', 'bpm_max', 'bpm_mean', 'spo2_min'])

    df_copy = df.copy()
    df_copy['date'] = df_copy['timestamp'].dt.date
    summary = df_copy.groupby('date').agg({
        'avg_bpm': ['min', 'max', 'mean'],
        'spo2': 'min'
    }).reset_index()
    summary.columns = ['date', 'bpm_min', 'bpm_max', 'bpm_mean', 'spo2_min']
    return summary

def get_hourly_deduplicated(df):
    """將原始數據按小時去重，僅保留每小時最高優先級的事件"""
    if df.empty:
        return df

    priority_map = {"DANGER": 2, "WARNING": 1, "NORMAL": 0}
    df_hourly = df.copy()
    df_hourly['priority'] = df_hourly['analysis_status'].map(priority_map)
    df_hourly['hour'] = df_hourly['timestamp'].dt.floor('h')

    idx = df_hourly.groupby('hour')['priority'].idxmax()
    return df_hourly.loc[idx].drop(columns=['priority', 'hour'])

def get_default_range():
    """計算過去三個月的範圍 (90天前到今天)"""
    today = datetime.now(local_tz).date()
    start_date = today - timedelta(days=90)
    return start_date, today

def translate_reason_codes(reason_codes, t):
    """
    將資料庫中的 reason_codes 翻譯為對應語系的文字描述。
    落實 SSoT 原則：此處不再包含任何數值判定。
    """
    if not reason_codes or not isinstance(reason_codes, list):
        return ""

    # 從 t['diag'] 字典中取出對應的翻譯
    reasons = [t['diag'].get(code, code) for code in reason_codes]

    # 透過 t['tt_week'] == "週別" 判斷是否為中文語系
    separator = "、" if t['tt_week'] == "週別" else ", "
    return separator.join(reasons)
