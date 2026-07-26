import pandas as pd
from datetime import date, datetime, timedelta
from core.config import local_tz

def calculate_kpis(df):
    """計算關鍵績效指標 (基於去重後的數據)"""
    total_samples = len(df)
    danger_count = len(df[df['analysis_status'] == "DANGER"])
    warning_count = len(df[df['analysis_status'] == "WARNING"])
    return total_samples, danger_count, warning_count

def get_daily_summary(df_daily):
    """將 MongoDB 的日聚合數據進行基礎格式與欄位轉換，用於趨勢圖"""
    if df_daily.empty:
        return pd.DataFrame(columns=['date', 'bpm_min', 'bpm_max', 'bpm_mean', 'spo2_min'])

    df_copy = df_daily.copy()
    # 確保 date 欄位轉為 datetime.date 型態
    df_copy['date'] = pd.to_datetime(df_copy['date']).dt.date
    # 確保欄位順序與命名對齊
    summary = df_copy[['date', 'bpm_min', 'bpm_max', 'bpm_mean', 'spo2_min']]
    return summary

def get_hourly_deduplicated(df_hourly):
    """直接回傳已在資料庫端去重的小時資料 (Pass-through)"""
    return df_hourly

def get_default_range(env="prod"):
    """計算過去三個月的範圍 (90天前到今天)；若為測試環境，則預設為 2026/04/02~2026/07/01"""
    if env == "test":
        return date(2026, 4, 2), date(2026, 7, 1)
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

    # 透過 t.get('tt_min_spo2') == "最低血氧" 判斷是否為中文語系
    separator = "、" if t.get('tt_min_spo2') == "最低血氧" else ", "
    return separator.join(reasons)
