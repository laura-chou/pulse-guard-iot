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

# Global variables
bpm_window = deque(maxlen=15)
spo2_window = deque(maxlen=15)

last_ema_bpm = None
last_analysis_status = None # 改名以區分裝置狀態
current_session_id = None
first_write_done = False
last_write_time = 0
collection = None

def is_valid_bpm(bpm):
    return 30 <= bpm <= 220

def is_valid_spo2(spo2):
    return 50 <= spo2 <= 100

def get_status(raw_bpm, ema_t, delta_bpm, raw_spo2):
    """
    階層式醫療狀態邏輯 (Hierarchical Medical Status Logic):
    1. DANGER (最高優先級 - 任何一項符合即觸發)
       - SpO2 <= 90%
       - EMA <= 50 BPM 或 EMA >= 140 BPM
       - |ΔBPM| >= 50
    2. NORMAL (必須滿足所有條件)
       - SpO2 >= 95%
       - 60 <= EMA <= 100
       - |ΔBPM| < 15
    3. WARNING (若非 DANGER 且未達 NORMAL，則歸類為 WARNING)
    """
    # 1. DANGER: 立即危險情況
    if raw_spo2 <= 90 or ema_t <= 50 or ema_t >= 140 or delta_bpm >= 50:
        return "DANGER"

    # 2. NORMAL: 必須所有生理指標均在理想範圍
    if raw_spo2 >= 95 and (60 <= ema_t <= 100) and delta_bpm < 15:
        return "NORMAL"

    # 3. WARNING: 介於危險與正常之間 (Fallback)，處理浮點數邊界
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
    global last_ema_bpm, first_write_done, last_write_time, last_analysis_status, collection, current_session_id

    try:
        config = get_config()
        payload = msg.payload.decode()
        data = json.loads(payload)

        # 判定資料來源 (data_source): 依據 MQTT Topic 區分生產環境與測試環境
        data_source = "production" if msg.topic == config["MQTT_TOPIC"] else "test"

        # 獲取裝置回傳的即時狀態
        device_status = data.get("device_status")

        # 處理結束量測訊號 (COMPLETED)
        if device_status == "COMPLETED":
            duration = data.get("duration_sec", 0)
            logger.info(f"COMPLETED signal received (Source: {data_source}). Duration: {duration}s.")

            # Generate and send report (僅限生產環境且 duration > 0 且 session 存在)
            if data_source == "production" and duration > 0 and current_session_id:
                report_manager.generate_and_send_report(current_session_id, duration)

            # Clear internal buffers and reset session
            bpm_window.clear()
            spo2_window.clear()
            last_ema_bpm = None
            last_analysis_status = None
            last_write_time = 0
            first_write_done = False
            current_session_id = None
            return

        # 處理系統重置訊號 (RESET)
        if device_status == "RESET":
            logger.info(f"RESET signal received (Source: {data_source}). Clearing buffers and session...")
            if collection is not None:
                record = {
                    "timestamp": datetime.fromtimestamp(time.time(), tz=timezone.utc),
                    "device_status": "RESET",
                    "session_id": current_session_id,
                    "data_source": data_source
                }
                try:
                    collection.insert_one(record)
                except Exception as e:
                    logger.error(f"MongoDB Insert Error (RESET): {e}")

            # Clear internal buffers and reset session
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

        if raw_bpm is None or raw_spo2 is None:
            return

        if not is_valid_bpm(raw_bpm) or not is_valid_spo2(raw_spo2):
            analysis_status = "OFF-CHIP"
        else:
            # 一旦收到有效量測資料，立即生成 Session ID (若尚未生成)
            if current_session_id is None:
                current_session_id = str(uuid.uuid4())
                logger.info(f"New session started: {current_session_id}")

            prev_xt_bpm = float(np.mean(bpm_window)) if len(bpm_window) > 0 else float(raw_bpm)
            bpm_window.append(float(raw_bpm))
            spo2_window.append(float(raw_spo2))
            xt_bpm = float(np.mean(bpm_window))
            xt_spo2 = float(np.mean(spo2_window))

            if last_ema_bpm is None:
                ema_bpm = xt_bpm
            else:
                ema_bpm = 0.3 * xt_bpm + 0.7 * last_ema_bpm

            delta_bpm = abs(float(raw_bpm) - prev_xt_bpm)
            analysis_status = get_status(float(raw_bpm), ema_bpm, delta_bpm, float(raw_spo2))
            last_ema_bpm = ema_bpm

        current_time = time.time()
        should_write = False

        # 決定是否寫入資料庫 (依據 Python 分析狀態 analysis_status 判定)
        if not first_write_done and analysis_status != "OFF-CHIP":
            # 首次有效量測，必須寫入
            should_write = True
            first_write_done = True
        elif analysis_status == "DANGER":
            # 危險狀態，立即寫入
            should_write = True
        elif analysis_status != last_analysis_status:
            # 狀態發生變化 (包含變為 OFF-CHIP)，立即寫入
            should_write = True
        elif current_time - last_write_time >= 20:
            # 定時心跳寫入 (Heartbeat)
            should_write = True

        if should_write and collection is not None:
            # 若處於 OFF-CHIP 且無 Session，則不進行寫入 (除非是 RESET)
            if current_session_id is None and analysis_status == "OFF-CHIP":
                return

            record = {
                "timestamp": datetime.fromtimestamp(current_time, tz=timezone.utc),
                "device_status": device_status,
                "analysis_status": analysis_status,
                "session_id": current_session_id,
                "data_source": data_source
            }
            if analysis_status != "OFF-CHIP":
                record.update({
                    "avg_bpm": xt_bpm,
                    "ema_bpm": float(ema_bpm),
                    "delta_bpm": float(delta_bpm),
                    "spo2": xt_spo2 # 存儲 15s 視窗平均值，較具代表性
                })
            else:
                # OFF-CHIP 時僅保留當下數值供診斷
                record.update({
                    "bpm": raw_bpm,
                    "spo2": raw_spo2
                })

            try:
                collection.insert_one(record)
                last_write_time = current_time
                last_analysis_status = analysis_status  # Update last_analysis_status after successful write
                logger.info(f"DB Write | Device: {device_status} | Analysis: {analysis_status}")
            except Exception as e:
                logger.error(f"MongoDB Insert Error: {e}")
    except Exception as e:
        logger.error(f"Error: {e}")

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
