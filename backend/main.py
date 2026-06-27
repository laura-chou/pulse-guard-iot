import logging
from config import Config
from database import DatabaseHandler
from processor import StreamProcessor
from mqtt_client import MQTTManager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # 1. 載入組態
    config = Config()
    if not config.validate():
        logger.error("Missing critical configuration (MONGO_URI or MQTT_BROKER). Please check your .env file.")
        return

    # 2. 初始化資料庫
    db_handler = DatabaseHandler(
        uri=config.MONGO_URI,
        db_name=config.MONGO_DB_NAME,
        col_name=config.MONGO_COL_NAME
    )
    if not db_handler.connect():
        logger.error("Failed to connect to database. Exiting.")
        return

    # 3. 初始化處理器
    processor = StreamProcessor(db_handler=db_handler)

    # 4. 初始化 MQTT 管理器
    mqtt_manager = MQTTManager(config=config, processor=processor)

    # 5. 啟動背景監測
    mqtt_manager.start_timeout_monitor()

    # 6. 啟動主迴圈
    logger.info("PulseGuard Stream Processor started successfully.")
    try:
        mqtt_manager.run()
    except KeyboardInterrupt:
        logger.info("PulseGuard Stream Processor shutting down...")
    finally:
        db_handler.close()

if __name__ == "__main__":
    main()
