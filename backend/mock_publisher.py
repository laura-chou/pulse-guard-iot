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

# Configuration (Removed default values)
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TOPIC = os.getenv("MQTT_TOPIC")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT Broker (Publisher)!")
    else:
        logger.error(f"Failed to connect, return code {rc}")

def main():
    if not all([MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, MQTT_TOPIC]):
        logger.error("Missing one or more MQTT environment variables.")
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

    # Detailed test cases for logic verification
    test_cases = [
        # === 區段一：0 ~ 20 秒（第 1~10 筆）===
        # 目標：驗證正常狀態與異常值過濾。第 20 秒寫入時應為 NORMAL。
        {"bpm": 72, "spo2": 98},    # 1. 正常
        {"bpm": 75, "spo2": 97},    # 2. 正常
        {"bpm": 70, "spo2": 99},    # 3. 正常
        {"bpm": 999, "spo2": 40},   # 4. 異常 (會被 subscriber 轉為 nan 並忽略)
        {"bpm": 20, "spo2": 110},   # 5. 異常 (會被 subscriber 轉為 nan 並忽略)
        {"bpm": 72, "spo2": 98},    # 6. 正常
        {"bpm": 75, "spo2": 97},    # 7. 正常
        {"bpm": 70, "spo2": 99},    # 8. 正常
        {"bpm": 72, "spo2": 98},    # 9. 正常
        {"bpm": 75, "spo2": 97},    # 10. 正常 ->【此時抵達第 20 秒，DB 寫入：NORMAL】

        # === 區段二：20 ~ 40 秒（第 11~20 筆）===
        # 目標：連續轟炸警告數據，強迫滑動視窗的平均血氧降至 91~94%。第 40 秒寫入時應為 WARNING。
        {"bpm": 80, "spo2": 93},    # 11. 警告
        {"bpm": 82, "spo2": 92},    # 12. 警告
        {"bpm": 85, "spo2": 91},    # 13. 警告
        {"bpm": 80, "spo2": 93},    # 14. 警告
        {"bpm": 82, "spo2": 92},    # 15. 警告 (此時視窗滿 15 筆，開始完全由新數據主導)
        {"bpm": 85, "spo2": 91},    # 16. 警告
        {"bpm": 999, "spo2": 40},   # 17. 異常 (視窗滿了，此時會複製前一筆平均值塞入隊列)
        {"bpm": 80, "spo2": 93},    # 18. 警告
        {"bpm": 82, "spo2": 92},    # 19. 警告
        {"bpm": 85, "spo2": 91},    # 20. 警告 ->【此時抵達第 40 秒，DB 寫入：WARNING】

        # === 區段三：40 ~ 60 秒（第 21~30 筆）===
        # 目標：連續轟炸危險數據，將舊的正常/警告值擠出視窗，強迫平均血氧跌破 90%。第 60 秒應為 DANGER。
        {"bpm": 80, "spo2": 88},    # 21. 嚴重低血氧 (合法危險值)
        {"bpm": 120, "spo2": 85},   # 22. 嚴重低血氧 (合法危險值)
        {"bpm": 80, "spo2": 88},    # 23. 嚴重低血氧 (合法危險值)
        {"bpm": 120, "spo2": 85},   # 24. 嚴重低血氧 (合法危險值)
        {"bpm": 45, "spo2": 95},    # 25. 心率過低 (BPM <= 50)
        {"bpm": 80, "spo2": 88},    # 26. 嚴重低血氧
        {"bpm": 120, "spo2": 85},   # 27. 嚴重低血氧
        {"bpm": 45, "spo2": 95},    # 28. 心率過低
        {"bpm": 80, "spo2": 88},    # 29. 嚴重低血氧
        {"bpm": 120, "spo2": 85}    # 30. 嚴重低血氧 ->【此時抵達第 60 秒，DB 寫入：DANGER】
    ]

    total_messages = len(test_cases)

    for i, data in enumerate(test_cases):
        payload = json.dumps(data)

        result = client.publish(MQTT_TOPIC, payload)
        status = result[0]
        if status == 0:
            logger.info(f"[{i+1}/{total_messages}] Sent: {payload}")
        else:
            logger.error(f"Failed to send message to topic {MQTT_TOPIC}")

        # Changed from 3s to 2s
        time.sleep(2)

    logger.info("Finished sending test data.")
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    main()
