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
def get_config():
    return {
        "MQTT_BROKER": os.getenv("MQTT_BROKER"),
        "MQTT_PORT": int(os.getenv("MQTT_PORT")) if os.getenv("MQTT_PORT") else None,
        "MQTT_USER": os.getenv("MQTT_USER"),
        "MQTT_PASSWORD": os.getenv("MQTT_PASSWORD"),
        "MQTT_TOPIC": os.getenv("MQTT_TOPIC"),
        "MONGO_URI": os.getenv("MONGO_URI"),
        "MONGO_DB_NAME": os.getenv("MONGO_DB_NAME"),
        "MONGO_COL_NAME": os.getenv("MONGO_COL_NAME")
    }

# Global variables
bpm_window = deque(maxlen=15)
spo2_window = deque(maxlen=15)

last_ema_bpm = None
last_status = None
first_write_done = False
last_write_time = 0
collection = None

def is_valid_bpm(bpm):
    return 30 <= bpm <= 220

def is_valid_spo2(spo2):
    return 50 <= spo2 <= 100

def get_status(raw_bpm, ema_t, delta_bpm, raw_spo2):
    if ema_t <= 50 or delta_bpm >= 50 or raw_spo2 <= 90:
        return "DANGER"
    elif (10 <= delta_bpm < 50) or (91 <= raw_spo2 <= 94):
        return "WARNING"
    elif delta_bpm < 10 and ema_t > 50 and raw_spo2 >= 95:
        return "NORMAL"
    return "NORMAL"

def on_connect(client, userdata, flags, rc):
    config = get_config()
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
        client.subscribe(config["MQTT_TOPIC"])
    else:
        logger.error(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    global last_ema_bpm, first_write_done, last_write_time, last_status, collection

    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        raw_bpm = data.get("bpm")
        raw_spo2 = data.get("spo2")

        if raw_bpm is None or raw_spo2 is None:
            return

        if not is_valid_bpm(raw_bpm) or not is_valid_spo2(raw_spo2):
            status = "OFF-CHIP"
        else:
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
            status = get_status(float(raw_bpm), ema_bpm, delta_bpm, float(raw_spo2))
            last_ema_bpm = ema_bpm

        current_time = time.time()
        should_write = False

        if not first_write_done and status != "OFF-CHIP":
            should_write = True
            first_write_done = True
        elif status == "DANGER":
            should_write = True
        elif current_time - last_write_time >= 20:
            should_write = True

        if should_write and collection is not None:
            record = {
                "timestamp": datetime.fromtimestamp(current_time, tz=timezone.utc),
                "status": status
            }
            if status != "OFF-CHIP":
                record.update({
                    "avg_bpm": xt_bpm,
                    "ema_bpm": float(ema_bpm),
                    "delta_bpm": float(delta_bpm),
                    "spo2": float(raw_spo2),
                    "avg_spo2": xt_spo2
                })
            else:
                record.update({"raw_bpm": raw_bpm, "raw_spo2": raw_spo2})

            try:
                collection.insert_one(record)
                last_write_time = current_time
                logger.info(f"DB Write | Status: {status}")
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
