import os
import json
import time
import logging
from datetime import datetime, timezone
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
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "pulseguard/data")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "pulseguard_db")
MONGO_COL_NAME = os.getenv("MONGO_COL_NAME", "health_metrics")

# Global variables
bpm_window = deque(maxlen=15)
spo2_window = deque(maxlen=15)

last_ema_bpm = None
last_xt_bpm = 0.0
last_xt_spo2 = 0.0

first_write_done = False
last_write_time = 0

# MongoDB Setup
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client[MONGO_DB_NAME]
    collection = db[MONGO_COL_NAME]
    logger.info(f"Connected to MongoDB: {MONGO_DB_NAME}.{MONGO_COL_NAME}")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    # We'll try to continue, but writes will fail.
    # In a production script, we might want to exit.

def is_valid_bpm(bpm):
    return 30 <= bpm <= 220

def is_valid_spo2(spo2):
    return 50 <= spo2 <= 100

def get_status(ema_t, delta_bpm, spo2_curr):
    # DANGER: (EMA_t ≤ 50) 或 (|ΔBPM| ≥ 50) 或 (SpO2_current ≤ 90%)
    if ema_t <= 50 or delta_bpm >= 50 or spo2_curr <= 90:
        return "DANGER"
    # WARNING：(10 ≤ |ΔBPM| < 50) 或 (91% ≤ SpO2_current ≤ 94%)
    elif (10 <= delta_bpm < 50) or (91 <= spo2_curr <= 94):
        return "WARNING"
    # NORMAL：(|ΔBPM| < 10) 且 (EMA_t > 50) 且 (SpO2_current ≥ 95%)
    elif delta_bpm < 10 and ema_t > 50 and spo2_curr >= 95:
        return "NORMAL"
    return "NORMAL" # Fallback

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC)
        logger.info(f"Subscribed to topic: {MQTT_TOPIC}")
    else:
        logger.error(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    global last_ema_bpm, last_xt_bpm, last_xt_spo2, first_write_done, last_write_time

    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        raw_bpm = data.get("bpm")
        raw_spo2 = data.get("spo2")

        if raw_bpm is None or raw_spo2 is None:
            return

        # Filtering logic with numpy nan
        # "只要不在BPM、SpO2範圍內的數字，一律轉為 np.nan"
        bpm_val = float(raw_bpm) if is_valid_bpm(raw_bpm) else np.nan
        spo2_val = float(raw_spo2) if is_valid_spo2(raw_spo2) else np.nan

        # Window management for BPM
        if not np.isnan(bpm_val):
            bpm_window.append(bpm_val)
        elif len(bpm_window) == 15:
            # "當收到一筆不合理的數值時... 複製前一筆計算出的平均值（或 EMA 值）塞進隊列"
            bpm_window.append(last_xt_bpm)
        # else: discard if len < 15 and invalid

        # Window management for SpO2
        if not np.isnan(spo2_val):
            spo2_window.append(spo2_val)
        elif len(spo2_window) == 15:
            spo2_window.append(last_xt_spo2)
        # else: discard if len < 15 and invalid

        if len(bpm_window) == 0 or len(spo2_window) == 0:
            return

        # Calculate current arithmetic mean (xt)
        # np.mean on deque is fine. Since we filtered nan out of the queue (or replaced with last average),
        # the queue contains only valid floats.
        xt_bpm = float(np.mean(bpm_window))
        xt_spo2 = float(np.mean(spo2_window))

        # Update last observed values
        last_xt_bpm = xt_bpm
        last_xt_spo2 = xt_spo2

        # EMA Calculation: EMA_t = 0.3 * xt + 0.7 * EMA_{t-1}
        if last_ema_bpm is None:
            # Phase 1: t=1, EMA_1 = x_1
            ema_bpm = xt_bpm
            delta_bpm = 0.0
        else:
            # Phase 2+: standard EMA
            ema_bpm = 0.3 * xt_bpm + 0.7 * last_ema_bpm
            delta_bpm = abs(ema_bpm - last_ema_bpm)

        status = get_status(ema_bpm, delta_bpm, xt_spo2)

        current_time = time.time()

        # Timer logic: Immediate first write, then every 20 seconds
        should_write = False
        if not first_write_done:
            should_write = True
            first_write_done = True
            last_write_time = current_time
        elif current_time - last_write_time >= 20:
            should_write = True
            last_write_time = current_time

        if should_write:
            record = {
                "timestamp": datetime.fromtimestamp(current_time, tz=timezone.utc),
                "avg_bpm": xt_bpm,
                "ema_bpm": float(ema_bpm),
                "delta_bpm": float(delta_bpm),
                "spo2": xt_spo2,
                "status": status
            }
            try:
                collection.insert_one(record)
                logger.info(f"DB Write: {status} | EMA_BPM: {ema_bpm:.2f} | ΔBPM: {delta_bpm:.2f} | SpO2: {xt_spo2:.2f}")
            except Exception as e:
                logger.error(f"MongoDB Insert Error: {e}")

        # Update last_ema_bpm for the next incoming message
        last_ema_bpm = ema_bpm

    except Exception as e:
        logger.error(f"Error processing message: {e}")

def main():
    if not MQTT_BROKER or not MQTT_USER or not MQTT_PASSWORD:
        logger.error("Missing MQTT environment variables.")
        return

    # MQTT Setup
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.tls_set() # Required for HiveMQ Cloud (typically port 8883)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        logger.info(f"Connecting to HiveMQ at {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        logger.error(f"MQTT Connection Error: {e}")
        return

    # Start the 24/7 loop
    client.loop_forever()

if __name__ == "__main__":
    main()
