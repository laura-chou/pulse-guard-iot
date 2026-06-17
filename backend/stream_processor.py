import os
import json
import time
import logging
import uuid
from datetime import datetime, timezone
import report_manager
from collections import deque
import numpy as np
import paho.mqtt.client as mqtt
from pymongo import MongoClient
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
def get_config():
    return {
        "MQTT_BROKER": os.getenv("MQTT_BROKER"),
        "MQTT_PORT": int(os.getenv("MQTT_PORT")) if os.getenv("MQTT_PORT") else None,
        "MQTT_USER": os.getenv("MQTT_USER"),
        "MQTT_PASSWORD": os.getenv("MQTT_PASSWORD"),
        "MQTT_TOPIC": os.getenv("MQTT_TOPIC"),
        "MQTT_TEST_TOPIC": os.getenv("MQTT_TEST_TOPIC"),
        "MONGO_URI": os.getenv("MONGO_URI"),
        "MONGO_DB_NAME": os.getenv("MONGO_DB_NAME"),
        "MONGO_COL_NAME": os.getenv("MONGO_COL_NAME")
    }

# 全域變數定義
# 使用 deque (雙向隊列) 實作滑動視窗，自動維持最近 15 筆數據
bpm_window = deque(maxlen=15)
spo2_window = deque(maxlen=15)

last_ema_bpm = None         # 前一次計算的指數移動平均 (EMA) 心率
last_analysis_status = None # 最後一次成功寫入資料庫的分析狀態，用於偵測狀態轉變
current_session_id = None   # 當前量測工作階段的唯一識別碼 (UUID)
first_write_done = False    # 標記該 Session 是否已完成首次資料寫入
last_write_time = 0         # 最後一次寫入資料庫的時間戳記 (UNIX Timestamp)
collection = None           # MongoDB Collection 物件

def is_valid_bpm(bpm):
    """
    驗證心率數值是否在生物學合理範圍內 (30 ~ 220 BPM)。
    排除感測器雜訊導致的極端錯誤值。
    """
    return 30 <= bpm <= 220

def is_valid_spo2(spo2):
    """
    驗證血氧濃度是否合理 (50% ~ 100%)。
    低於 50% 通常視為感測器脫落或無效訊號。
    """
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

def on_connect(client, userdata, flags, rc):
    config = get_config()
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
        # 訂閱生產與測試 Topic
        if config["MQTT_TOPIC"]:
            client.subscribe(config["MQTT_TOPIC"])
        if config["MQTT_TEST_TOPIC"]:
            client.subscribe(config["MQTT_TEST_TOPIC"])
    else:
        logger.error(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    """
    MQTT 訊息處理回呼函式：
    負責資料清洗、時序運算 (EMA/MA)、狀態分析與資料庫持久化。
    """
    global last_ema_bpm, first_write_done, last_write_time, last_analysis_status, collection, current_session_id

    try:
        config = get_config()
        payload = msg.payload.decode()
        data = json.loads(payload)

        # 1. 判定資料來源 (data_source)
        # 正式環境與測試環境數據在同一資料庫隔離存儲
        data_source = "production" if msg.topic == config["MQTT_TOPIC"] else "test"

        device_status = data.get("device_status")

        # 2. 處理量測結束 (COMPLETED)
        if device_status == "COMPLETED":
            duration = data.get("duration_sec", 0)
            logger.info(f"量測結束 (來源: {data_source})，時長: {duration}秒")

            # 僅正式量測且有有效 Session 時才發送 LINE 報告
            if data_source == "production" and duration > 0 and current_session_id:
                report_manager.generate_and_send_report(current_session_id, duration)

            # 重置所有生理緩衝區與會話狀態
            bpm_window.clear()
            spo2_window.clear()
            last_ema_bpm = None
            last_analysis_status = None
            last_write_time = 0
            first_write_done = False
            current_session_id = None
            return

        # 3. 處理系統重置 (RESET)
        if device_status == "RESET":
            logger.info(f"系統重置 (來源: {data_source})，清空所有狀態。")
            if collection is not None:
                # 寫入一筆特殊的 RESET 紀錄，標記 Session 中斷
                record = {
                    "timestamp": datetime.fromtimestamp(time.time(), tz=timezone.utc),
                    "analysis_status": "RESET",
                    "session_id": current_session_id,
                    "data_source": data_source
                }
                try:
                    collection.insert_one(record)
                except Exception as e:
                    logger.error(f"MongoDB 寫入失敗 (RESET): {e}")

            # 清空狀態
            bpm_window.clear()
            spo2_window.clear()
            last_ema_bpm = None
            last_analysis_status = None
            last_write_time = 0
            first_write_done = False
            current_session_id = None
            return

        raw_bpm = data.get("bpm")
        raw_spo2 = data.get("spo2")

        # 4. 資料完整性與有效性檢查
        if raw_bpm is None or raw_spo2 is None:
            return

        # 核心防護邏輯：若感測器脫落 (OFF-CHIP) 或數值異常，直接忽略，不汙染 EMA 趨勢與資料庫
        if not is_valid_bpm(raw_bpm) or not is_valid_spo2(raw_spo2) or device_status == "OFF-CHIP":
            return

        # 5. 工作階段 (Session) 管理
        # 收到第一筆有效數據時才開啟 Session，避免資料庫充斥空 Session
        if current_session_id is None:
            current_session_id = str(uuid.uuid4())
            logger.info(f"開啟新量測工作階段: {current_session_id}")

        # 6. 生理指標運算 (MA & EMA)
        # 計算 15 秒移動平均 (Moving Average)
        prev_xt_bpm = float(np.mean(bpm_window)) if len(bpm_window) > 0 else float(raw_bpm)
        bpm_window.append(float(raw_bpm))
        spo2_window.append(float(raw_spo2))
        xt_bpm = float(np.mean(bpm_window))
        xt_spo2 = float(np.mean(spo2_window))

        # 指數移動平均 (EMA) 運算：降低單點雜訊權重
        # 公式: EMA = α * current_avg + (1-α) * last_ema, 此處 α=0.3
        if last_ema_bpm is None:
            ema_bpm = xt_bpm
        else:
            ema_bpm = 0.3 * xt_bpm + 0.7 * last_ema_bpm

        # 運算心率變異差值
        delta_bpm = abs(float(raw_bpm) - prev_xt_bpm)

        # 7. 狀態分析判斷
        analysis_status = get_status(float(raw_bpm), ema_bpm, delta_bpm, float(raw_spo2))
        last_ema_bpm = ema_bpm

        # 8. 智慧寫入機制 (Smart DB Persistence Strategy)
        # 為了平衡「即時警報」與「資料庫壓力」，採用事件驅動與定時心跳相結合的策略。
        current_time = time.time()
        should_write = False

        if not first_write_done:
            should_write = True # 首次有效量測點必須紀錄，確保 Session 起頭完整
        elif analysis_status == "DANGER":
            should_write = True # 危險狀態必須即時紀錄
        elif analysis_status != last_analysis_status:
            should_write = True # 狀態發生變化必須紀錄
        elif current_time - last_write_time >= 20:
            should_write = True # 定時心跳紀錄 (每 20 秒一次)

        # 9. 執行資料庫寫入
        if should_write and collection is not None:
            record = {
                "timestamp": datetime.fromtimestamp(current_time, tz=timezone.utc),
                "analysis_status": analysis_status,
                "session_id": current_session_id,
                "data_source": data_source,
                "avg_bpm": xt_bpm,
                "ema_bpm": float(ema_bpm),
                "delta_bpm": float(delta_bpm),
                "spo2": xt_spo2 # 儲存視窗平均血氧，優於即時抖動值
            }

            try:
                collection.insert_one(record)
                # 僅在寫入成功後才更新狀態、計時器與首次寫入標記
                # 這樣若 MongoDB 暫時斷線，系統會在下一秒嘗試重試，直到成功為止
                last_write_time = current_time
                last_analysis_status = analysis_status
                first_write_done = True
                logger.info(f"資料存檔 | 分析結果: {analysis_status}")
            except Exception as e:
                logger.error(f"MongoDB 寫入異常: {e}")
    except Exception as e:
        logger.error(f"系統錯誤: {e}")

def main():
    global collection
    config = get_config()
    if not all(config.values()):
        logger.error("Missing config.")
        return

    try:
        mongo_client = MongoClient(config["MONGO_URI"])
        db = mongo_client[config["MONGO_DB_NAME"]]
        collection = db[config["MONGO_COL_NAME"]]
    except Exception as e:
        logger.error(f"DB Error: {e}")

    client = mqtt.Client()
    client.username_pw_set(config["MQTT_USER"], config["MQTT_PASSWORD"])
    client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(config["MQTT_BROKER"], config["MQTT_PORT"], 60)
    except Exception as e:
        logger.error(f"MQTT Error: {e}")
        return
    client.loop_forever()

if __name__ == "__main__":
    main()
