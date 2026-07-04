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
        self.clients: Dict[str, mqtt.Client] = {}
        self._setup_clients()

    def _setup_clients(self) -> None:
        for name, broker_config in self.config.MQTT_BROKERS_CONFIG.items():
            try:
                client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

                user = broker_config.get("user")
                password = broker_config.get("password")
                if user and password:
                    client.username_pw_set(user, password)

                client.tls_set()
                client.on_connect = self._on_connect
                client.on_message = self._on_message

                # 將 broker 名稱存入 userdata 以便在 callback 中識別
                client.user_data_set(name)

                self.clients[name] = client
                logger.info(f"MQTT Client for {name} initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize MQTT client for {name}: {e}")

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], reason_code: mqtt.ReasonCode, properties: Optional[mqtt.Properties] = None) -> None:
        name = userdata
        if reason_code == 0:
            logger.info(f"[{name}] Connected to MQTT Broker!")
            client.subscribe(self.config.MQTT_TOPIC_PATTERN)
        else:
            logger.error(f"[{name}] Failed to connect to MQTT, reason code: {reason_code}")

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

    def run(self) -> None:
        """啟動所有 Client 並進入主迴圈執行監控"""
        for name, client in self.clients.items():
            broker_config = self.config.MQTT_BROKERS_CONFIG[name]
            host = broker_config.get("host")
            port = broker_config.get("port", 8883)
            try:
                client.connect(host, port, 60)
                client.loop_start()
                logger.info(f"[{name}] MQTT loop started for {host}:{port}")
            except Exception as e:
                logger.error(f"[{name}] Failed to start MQTT loop for {host}: {e}")

        logger.info("PulseGuard MQTT Manager is running. Starting timeout monitor.")
        try:
            while True:
                try:
                    self.processor.check_timeouts(timeout_sec=10.0)
                except Exception as e:
                    logger.error(f"Error during timeout check: {e}")
                time.sleep(1)
        except Exception as e:
            logger.error(f"Main run loop encountered an error: {e}")
        finally:
            for client in self.clients.values():
                client.loop_stop()
