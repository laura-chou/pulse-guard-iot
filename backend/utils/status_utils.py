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

def get_highest_status(status_list):
    """
    從狀態清單中判定最高風險等級。
    優先級：DANGER > WARNING > NORMAL
    """
    if not status_list:
        return "NORMAL"

    highest_risk = "NORMAL"
    for status in status_list:
        if status == "DANGER":
            return "DANGER" # 最高優先級，直接返回
        if status == "WARNING":
            highest_risk = "WARNING"

    return highest_risk
