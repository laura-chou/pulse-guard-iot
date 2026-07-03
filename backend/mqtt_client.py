import json
import logging
import time
import threading
from typing import Optional, Dict, Any
import paho.mqtt.client as mqtt
from config import Config
from processor import StreamProcessor

logger = logging.getLogger(__name__)

class MQTTManager:
    def __init__(self, config: Config, processor: StreamProcessor):
        self.config = config
        self.processor = processor
        self.client: mqtt.Client = mqtt.Client()
        self._setup_client()

    def _setup_client(self) -> None:
        if self.config.MQTT_USER is not None and self.config.MQTT_PASSWORD is not None:
            self.client.username_pw_set(self.config.MQTT_USER, self.config.MQTT_PASSWORD)

        # 預設使用 TLS，與原程式碼一致
        self.client.tls_set()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, int], rc: int) -> None:
        if rc == 0:
            logger.info("Connected to MQTT Broker!")
            client.subscribe(self.config.MQTT_TOPIC_PATTERN)
        else:
            logger.error(f"Failed to connect to MQTT, return code {rc}")

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        try:
            topic_parts = msg.topic.split('/')
            # 預期格式: pulseguard/<env>/<device_id>/data
            if len(topic_parts) == 4 and topic_parts[0] == "pulseguard" and topic_parts[3] == "data":
                data_source = topic_parts[1]
                device_id = topic_parts[2]
            else:
                logger.warning(f"Message received on unexpected topic: {msg.topic}")
                return

            payload_str = msg.payload.decode()
            payload = json.loads(payload_str)

            self.processor.process_message(data_source, device_id, payload)

        except Exception as e:
            logger.error(f"MQTT message processing error: {e}")

    def start_timeout_monitor(self) -> None:
        """啟動背景逾時監控執行緒"""
        def monitor_loop():
            while True:
                try:
                    self.processor.check_timeouts(timeout_sec=10.0)
                except Exception as e:
                    logger.error(f"Timeout monitor loop error: {e}")
                time.sleep(1)

        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info("Timeout monitor thread started.")

    def run(self) -> None:
        """連線並進入無限迴圈"""
        try:
            port = self.config.MQTT_PORT or 8883
            self.client.connect(self.config.MQTT_BROKER, port, 60)
            self.client.loop_forever()
        except Exception as e:
            logger.error(f"MQTT connection loop error: {e}")
