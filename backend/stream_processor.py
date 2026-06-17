import os
import json
import time
import logging
import uuid
from datetime import datetime, timezone
import report_manager
from backend.utils.status_utils import is_valid_bpm, is_valid_spo2, get_status
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
            logger.info(f"Measurement ended (source: {data_source}), duration: {duration}s")

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
            logger.info(f"System reset (source: {data_source}), cleared all states.")
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
                    logger.error(f"MongoDB write failed (RESET): {e}")

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
            logger.info(f"Started new measurement session: {current_session_id}")

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
                logger.info(f"Data saved | Analysis result: {analysis_status}")
            except Exception as e:
                logger.error(f"MongoDB write error: {e}")
    except Exception as e:
        logger.error(f"System error: {e}")

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
        logger.error(f"Database error: {e}")

    client = mqtt.Client()
    client.username_pw_set(config["MQTT_USER"], config["MQTT_PASSWORD"])
    client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(config["MQTT_BROKER"], config["MQTT_PORT"], 60)
    except Exception as e:
        logger.error(f"MQTT error: {e}")
        return
    client.loop_forever()

if __name__ == "__main__":
    main()
