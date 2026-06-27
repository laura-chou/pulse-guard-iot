"""
健康狀態判定與數值驗證工具模組
"""
from typing import List, Tuple

# 指數移動平均 (EMA) 權重係數
EMA_ALPHA = 0.3

def is_valid_bpm(bpm: float) -> bool:
    """驗證心率數值是否在生物學合理範圍內 (30 ~ 220 BPM)"""
    if bpm is None:
        return False
    return 30 <= bpm <= 220

def is_valid_spo2(spo2: float) -> bool:
    """驗證血氧濃度是否合理 (50% ~ 100%)"""
    if spo2 is None:
        return False
    return 50 <= spo2 <= 100

def get_status_and_codes(raw_bpm: float, ema_t: float, delta_bpm: float, raw_spo2: float) -> Tuple[str, List[str]]:
    """
    核心醫療判定邏輯 (SSoT)：判定健康狀態與異常代碼。

    【設計規格】：
    1. 消除邊界縫隙：使用精確的開閉區間處理浮點數。
    2. 雙軌判定：結合即時值 (SpO2, delta_bpm) 與時序過濾值 (EMA BPM)。

    回傳: (status, reason_codes)
    """
    reason_codes = []

    # --- 1. 異常代碼收集 (由重至輕) ---

    # 血氧判定
    if raw_spo2 <= 90:
        reason_codes.append('crit_low_spo2')
    elif 90 < raw_spo2 < 95:
        reason_codes.append('low_spo2')

    # 心率時序判定 (EMA)
    if ema_t <= 50:
        reason_codes.append('crit_low_hr')
    elif 50 < ema_t < 60:
        reason_codes.append('low_hr')
    elif 100 < ema_t < 140:
        reason_codes.append('high_hr')
    elif ema_t >= 140:
        reason_codes.append('crit_high_hr')

    # 心率突變判定 (delta_bpm 已保證為正數)
    if delta_bpm >= 50:
        reason_codes.append('arrhythmia')
    elif 15 <= delta_bpm < 50:
        reason_codes.append('hr_fluctuation')

    # --- 2. 狀態等級最終決策 ---

    # 危險觸發代碼 (任一符合即 DANGER)
    danger_triggers = {'crit_low_spo2', 'crit_low_hr', 'crit_high_hr', 'arrhythmia'}

    if any(code in danger_triggers for code in reason_codes):
        return "DANGER", reason_codes

    # 若有無危險代碼但有其他異常 code，則為 WARNING
    if reason_codes:
        return "WARNING", reason_codes

    # 以上皆非，則為完美 NORMAL (reason_codes 為空)
    return "NORMAL", []

def get_status(raw_bpm: float, ema_t: float, delta_bpm: float, raw_spo2: float) -> str:
    """相容舊邏輯的包裝函式"""
    status, _ = get_status_and_codes(raw_bpm, ema_t, delta_bpm, raw_spo2)
    return status

def evaluate_session_health(status_list: List[str]) -> Tuple[str, str, str, str]:
    """
    雙軌制判定法：從狀態清單中判定整體健康等級與備註。
    回傳：(status_text, color, remark, status_key)
    """
    if not status_list:
        return ("🟢 NORMAL", "#2B8A3E", "整體生理數據表現良好。", "NORMAL")

    danger_count = status_list.count("DANGER")
    warning_count = status_list.count("WARNING")
    total_count = len(status_list)

    # 情境 A：持續危險 (DANGER)
    if danger_count >= 2:
        return ("🔴 DANGER", "#DC3545", "警告：偵測到持續性嚴重異常", "DANGER")

    # 情境 B：突發性異常 (WARNING)
    if danger_count == 1:
        return ("🟠 WARNING", "#FD7E14", "量測期間整體平均正常，但曾偵測到單次瞬時生理數值異常", "WARNING")

    # 情境 C：狀態不穩定 (WARNING)
    if danger_count == 0 and total_count > 0 and (warning_count / total_count >= 0.3):
        return ("🟡 WARNING", "#FCC419", "異常狀態比例偏高，身體可能正處於勞累或不適狀態。", "WARNING")

    # 情境 D：完全正常 (NORMAL)
    return ("🟢 NORMAL", "#2B8A3E", "整體生理數據表現良好。", "NORMAL")
