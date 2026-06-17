"""
健康狀態判定與數值驗證工具模組
"""

def is_valid_bpm(bpm):
    """
    驗證心率數值是否在生物學合理範圍內 (30 ~ 220 BPM)。
    排除感測器雜訊導致的極端錯誤值。
    """
    if bpm is None:
        return False
    return 30 <= bpm <= 220

def is_valid_spo2(spo2):
    """
    驗證血氧濃度是否合理 (50% ~ 100%)。
    低於 50% 通常視為感測器脫落或無效訊號。
    """
    if spo2 is None:
        return False
    return 50 <= spo2 <= 100

def get_status(raw_bpm, ema_t, delta_bpm, raw_spo2):
    """
    核心醫療狀態判定邏輯 (階層式判定)：

    1. 危險 (DANGER) - 優先級最高，符合任一即觸發：
        - 血氧濃度 (SpO2) 降至 90% 或以下 (急性缺氧)
        - EMA 心率低於 50 或高於 140 (嚴重心律不整/過速)
        - 即時心率與視窗平均值之差值 (|ΔBPM|) >= 50 (偵測到極端突發狀況)

    2. 正常 (NORMAL) - 必須滿足所有條件：
        - 血氧濃度穩定在 95% 以上
        - EMA 心率維持在 60 ~ 100 的理想靜止範圍
        - 心率波動 (|ΔBPM|) 小於 15 (數據穩定)

    3. 警告 (WARNING) - 次要優先級：
        - 若非危險且未達完全正常標準，則歸類為警告。

    注意：此處 SpO2 判斷使用即時值 (raw_spo2) 以確保對急性缺氧的極速反應。
    """
    # 第一層：危險判定 (任何一項符合即為 DANGER)
    if raw_spo2 <= 90 or ema_t <= 50 or ema_t >= 140 or delta_bpm >= 50:
        return "DANGER"

    # 第二層：正常判定 (需全數符合才為 NORMAL)
    if raw_spo2 >= 95 and (60 <= ema_t <= 100) and delta_bpm < 15:
        return "NORMAL"

    # 第三層：警告判定 (Fallback)
    return "WARNING"

def evaluate_session_health(status_list):
    """
    雙軌制判定法：從狀態清單中判定整體健康等級與備註。

    回傳：(status_text, color, remark, status_key)

    【情境 A：持續危險 (DANGER)】：如果日誌陣列中，"DANGER" 的數量「大於或等於 2 筆」。
    【情境 B：突發性異常 (WARNING)】：如果日誌陣列中，"DANGER" 的數量「剛好只有 1 筆」。
    【情境 C：狀態不穩定 (WARNING)】：如果陣列中沒有 DANGER，但 "WARNING" 的數量佔比「超過或等於 30%」。
    【情境 D：完全正常 (NORMAL)】：以上皆非。
    """
    if not status_list:
        return ("🟢 NORMAL (正常)", "#2B8A3E", "整體生理數據表現良好。", "NORMAL")

    danger_count = status_list.count("DANGER")
    warning_count = status_list.count("WARNING")
    total_count = len(status_list)

    # 情境 A：持續危險 (DANGER)
    if danger_count >= 2:
        return (
            "🔴 DANGER",
            "#DC3545",
            "警告：偵測到持續性嚴重異常",
            "DANGER"
        )

    # 情境 B：突發性異常 (WARNING)
    if danger_count == 1:
        return (
            "🟠 WARNING",
            "#FD7E14",
            "量測期間整體平均正常，但曾偵測到單次瞬時生理數值異常",
            "WARNING"
        )

    # 情境 C：狀態不穩定 (WARNING)
    if danger_count == 0 and total_count > 0 and (warning_count / total_count >= 0.3):
        return (
            "🟡 WARNING",
            "#FCC419",
            "異常狀態比例偏高，身體可能正處於勞累或不適狀態。",
            "WARNING"
        )

    # 情境 D：完全正常 (NORMAL)
    return ("🟢 NORMAL", "#2B8A3E", "整體生理數據表現良好。", "NORMAL")
