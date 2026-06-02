import os
import json
import time
import logging
import paho.mqtt.client as mqtt
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

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT Broker (Publisher)!")
    else:
        logger.error(f"Failed to connect, return code {rc}")

def main():
    if not MQTT_BROKER or not MQTT_USER or not MQTT_PASSWORD:
        logger.error("Missing MQTT environment variables.")
        return

    # MQTT Setup
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.tls_set() # Required for HiveMQ Cloud

    client.on_connect = on_connect

    try:
        logger.info(f"Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        logger.error(f"MQTT Connection Error: {e}")
        return

    # Start loop in a background thread
    client.loop_start()

    # Test data scenarios
    test_scenarios = [
        # 1. Normal data
        {"bpm": 72, "spo2": 98},
        {"bpm": 75, "spo2": 97},
        {"bpm": 70, "spo2": 99},

        # 2. Outlier filtering data (should be ignored or replaced in subscriber)
        {"bpm": 999, "spo2": 40},
        {"bpm": 20, "spo2": 110},

        # 3. Warning data (SpO2 91-94%)
        {"bpm": 80, "spo2": 93},
        {"bpm": 82, "spo2": 92},
        {"bpm": 85, "spo2": 91},

        # 4. Danger data (SpO2 <= 90% or BPM <= 50)
        {"bpm": 45, "spo2": 95},
        {"bpm": 80, "spo2": 88},
        {"bpm": 120, "spo2": 85}
    ]

    # Total 30 messages (approx 90 seconds) to trigger the 20s DB write multiple times
    total_messages = 30

    for i in range(total_messages):
        # Pick scenario in a loop
        data = test_scenarios[i % len(test_scenarios)]
        payload = json.dumps(data)

        result = client.publish(MQTT_TOPIC, payload)
        status = result[0]
        if status == 0:
            logger.info(f"[{i+1}/{total_messages}] Sent: {payload}")
        else:
            logger.error(f"Failed to send message to topic {MQTT_TOPIC}")

        time.sleep(3)

    logger.info("Finished sending test data.")
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    main()
