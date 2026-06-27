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

def get_diagnosis_description(row, t):
    """
    根據生理指標判定異常原因 (Description)
    """
    reasons = []
    spo2 = row.get('spo2', 100)
    ema_bpm = row.get('ema_bpm', 75)
    delta_bpm = abs(row.get('delta_bpm', 0))

    # SpO2 判定
    if spo2 <= 90:
        reasons.append(t['diag']['crit_low_spo2'])
    elif 91 <= spo2 <= 94:
        reasons.append(t['diag']['low_spo2'])

    # 心率判定 (EMA)
    if ema_bpm <= 50:
        reasons.append(t['diag']['crit_low_hr'])
    elif 50 < ema_bpm < 60:
        reasons.append(t['diag']['low_hr'])
    elif 100 < ema_bpm < 140:
        reasons.append(t['diag']['high_hr'])
    elif ema_bpm >= 140:
        reasons.append(t['diag']['crit_high_hr'])

    # 心率突變判定
    if delta_bpm >= 50:
        reasons.append(t['diag']['arrhythmia'])

    # 透過 t['title'] 或特定欄位名稱來判斷語系較為可靠
    separator = "、" if t['tt_week'] == "週別" else ", "
    return separator.join(reasons)
