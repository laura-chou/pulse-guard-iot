import os
import json
import time
import logging
import uuid
import threading
from datetime import datetime, timezone
import report_manager
from utils.status_utils import is_valid_bpm, is_valid_spo2, get_status, EMA_ALPHA
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
        "MQTT_TOPIC_PATTERN": "pulseguard/+/+/data",
        "MONGO_URI": os.getenv("MONGO_URI"),
        "MONGO_DB_NAME": os.getenv("MONGO_DB_NAME"),
        "MONGO_COL_NAME": os.getenv("MONGO_COL_NAME")
    }

# --- 多裝置狀態管理 ---
class DeviceState:
    def __init__(self, data_source, device_id):
        self.data_source = data_source
        self.device_id = device_id
        self.bpm_window = deque(maxlen=15)
        self.spo2_window = deque(maxlen=15)
        self.last_ema_bpm = None
        self.last_analysis_status = None
        self.current_session_id = None
        self.first_write_done = False
        self.last_write_time = 0
        self.last_seen = time.time()
        self.lock = threading.Lock()

    def reset_and_delete(self, collection):
        """重置狀態並從資料庫刪除當前 Session 的所有數據"""
        with self.lock:
            if self.current_session_id and collection is not None:
                try:
                    result = collection.delete_many({"session_id": self.current_session_id})
                    logger.info(f"[{self.device_id}] Deleted {result.deleted_count} records for session {self.current_session_id} due to RESET/Timeout")
                except Exception as e:
                    logger.error(f"[{self.device_id}] Failed to delete records for session {self.current_session_id}: {e}")

            self.bpm_window.clear()
            self.spo2_window.clear()
            self.last_ema_bpm = None
            self.last_analysis_status = None
            self.current_session_id = None
            self.first_write_done = False
            self.last_write_time = 0

# 全域裝置狀態字典 (key: (data_source, device_id))
device_states = {}
device_states_lock = threading.Lock()
collection = None

def get_device_state(data_source, device_id):
    key = (data_source, device_id)
    with device_states_lock:
        if key not in device_states:
            device_states[key] = DeviceState(data_source, device_id)
        return device_states[key]

def timeout_monitor():
    """背景執行緒：監測裝置逾時"""
    while True:
        try:
            now = time.time()
            to_delete = []
            with device_states_lock:
                for key, state in device_states.items():
                    # 10 秒未收到資料且目前有 active session，則判定逾時
                    if state.current_session_id and (now - state.last_seen > 10):
                        to_delete.append(state)

            for state in to_delete:
                logger.info(f"[{state.device_id}] Session timeout detected (10s). Cleaning up...")
                state.reset_and_delete(collection)
        except Exception as e:
            logger.error(f"Timeout monitor error: {e}")
        time.sleep(1)

def on_connect(client, userdata, flags, rc):
    config = get_config()
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
        # 訂閱萬用主題格式: pulseguard/<env>/<device_id>/data
        client.subscribe(config["MQTT_TOPIC_PATTERN"])
        # 同時保留舊主題相容性 (如果有需要)
        if os.getenv("MQTT_TOPIC"):
            client.subscribe(os.getenv("MQTT_TOPIC"))
        if os.getenv("MQTT_TEST_TOPIC"):
            client.subscribe(os.getenv("MQTT_TEST_TOPIC"))
    else:
        logger.error(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    """
    MQTT 訊息處理回呼函式：支援多裝置、Session 管理與逾時刪除。
    """
    global collection

    try:
        topic_parts = msg.topic.split('/')

        # 解析 Topic 獲取 env 與 device_id
        # 預期格式: pulseguard/<env>/<device_id>/data
        if len(topic_parts) == 4 and topic_parts[0] == "pulseguard" and topic_parts[3] == "data":
            data_source = topic_parts[1]
            device_id = topic_parts[2]
        else:
            # 舊版 Topic 相容邏輯
            config = get_config()
            data_source = "production" if msg.topic == os.getenv("MQTT_TOPIC") else "test"
            device_id = "legacy_device"

        state = get_device_state(data_source, device_id)
        state.last_seen = time.time()

        payload = msg.payload.decode()
        data = json.loads(payload)
        device_status = data.get("device_status")

        # 1. 處理量測結束 (COMPLETED)
        if device_status == "COMPLETED":
            duration = data.get("duration_sec", 0)
            logger.info(f"[{device_id}] Measurement ended (source: {data_source}), duration: {duration}s")

            # 僅正式量測且有有效 Session 時才發送 LINE 報告
            if data_source == "production" and duration > 0 and state.current_session_id:
                report_manager.generate_and_send_report(state.current_session_id, duration)

            # 重置該裝置狀態，但不刪除資料 (因為已完成)
            with state.lock:
                state.bpm_window.clear()
                state.spo2_window.clear()
                state.last_ema_bpm = None
                state.last_analysis_status = None
                state.last_write_time = 0
                state.first_write_done = False
                state.current_session_id = None
            return

        # 2. 處理系統重置 (RESET)
        if device_status == "RESET":
            logger.info(f"[{device_id}] System reset (source: {data_source}). Deleting current session data.")
            state.reset_and_delete(collection)
            return

        raw_bpm = data.get("bpm")
        raw_spo2 = data.get("spo2")

        # 3. 資料完整性與有效性檢查
        if raw_bpm is None or raw_spo2 is None:
            return

        # 移除原有的 OFF-CHIP 邏輯，改由計時器自動處理逾時

        if not is_valid_bpm(raw_bpm) or not is_valid_spo2(raw_spo2):
            logger.warning(f"[{device_id}] Invalid health data ({raw_bpm} BPM, {raw_spo2}% SpO2). Filtering.")
            return

        # 4. 工作階段 (Session) 管理
        with state.lock:
            if state.current_session_id is None:
                state.current_session_id = str(uuid.uuid4())
                logger.info(f"[{device_id}] Started new session: {state.current_session_id}")

            # 5. 生理指標運算 (MA & EMA)
            prev_xt_bpm = float(np.mean(state.bpm_window)) if len(state.bpm_window) > 0 else float(raw_bpm)
            state.bpm_window.append(float(raw_bpm))
            state.spo2_window.append(float(raw_spo2))
            xt_bpm = float(np.mean(state.bpm_window))
            xt_spo2 = float(np.mean(state.spo2_window))

            if state.last_ema_bpm is None:
                ema_bpm = xt_bpm
            else:
                ema_bpm = EMA_ALPHA * xt_bpm + (1 - EMA_ALPHA) * state.last_ema_bpm

            delta_bpm = abs(float(raw_bpm) - prev_xt_bpm)

            # 6. 狀態分析判斷
            analysis_status = get_status(float(raw_bpm), ema_bpm, delta_bpm, float(raw_spo2))
            state.last_ema_bpm = ema_bpm

            # 7. 智慧寫入機制
            current_time = time.time()
            should_write = False

            if not state.first_write_done:
                should_write = True
            elif analysis_status == "DANGER":
                should_write = True
            elif analysis_status != state.last_analysis_status:
                should_write = True
            elif current_time - state.last_write_time >= 20:
                should_write = True

            # 8. 執行資料庫寫入
            if should_write and collection is not None:
                record = {
                    "timestamp": datetime.fromtimestamp(current_time, tz=timezone.utc),
                    "analysis_status": analysis_status,
                    "session_id": state.current_session_id,
                    "data_source": data_source,
                    "device_id": device_id,
                    "avg_bpm": xt_bpm,
                    "ema_bpm": float(ema_bpm),
                    "delta_bpm": float(delta_bpm),
                    "spo2": xt_spo2
                }

                try:
                    collection.insert_one(record)
                    state.last_write_time = current_time
                    state.last_analysis_status = analysis_status
                    state.first_write_done = True
                    logger.info(f"[{device_id}] Data saved | Status: {analysis_status}")
                except Exception as e:
                    logger.error(f"[{device_id}] MongoDB write error: {e}")
    except Exception as e:
        logger.error(f"System error: {e}")

def main():
    global collection
    config = get_config()

    # 檢查必要連線資訊
    if not config["MONGO_URI"] or not config["MQTT_BROKER"]:
        logger.error("Missing critical config (MONGO_URI or MQTT_BROKER).")
        return

    try:
        mongo_client = MongoClient(config["MONGO_URI"])
        db = mongo_client[config["MONGO_DB_NAME"]]
        collection = db[config["MONGO_COL_NAME"]]
    except Exception as e:
        logger.error(f"Database error: {e}")

    # 啟動逾時監控執行緒
    monitor_thread = threading.Thread(target=timeout_monitor, daemon=True)
    monitor_thread.start()

    client = mqtt.Client()
    if config["MQTT_USER"]:
        client.username_pw_set(config["MQTT_USER"], config["MQTT_PASSWORD"])
    client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(config["MQTT_BROKER"], config["MQTT_PORT"] or 8883, 60)
    except Exception as e:
        logger.error(f"MQTT connection error: {e}")
        return

    client.loop_forever()

if __name__ == "__main__":
    main()
