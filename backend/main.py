import logging
from pydantic import ValidationError
from config import Config
from database import DatabaseHandler
from processor import StreamProcessor
from mqtt_client import MQTTManager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # 1. 載入組態
    try:
        config = Config()
    except ValidationError as e:
        logger.error(f"Configuration error: {e}")
        return

    # 2. 初始化處理器（注入資料庫配置）
    processor = StreamProcessor(db_configs=config.MONGO_DB_CONFIG)

    # 3. 初始化 MQTT 管理器
    mqtt_manager = MQTTManager(config=config, processor=processor)

    # 4. 啟動主迴圈
    logger.info("PulseGuard Stream Processor started successfully.")
    try:
        mqtt_manager.run()
    except KeyboardInterrupt:
        logger.info("PulseGuard Stream Processor shutting down...")
    finally:
        # 優雅關閉所有資料庫連線
        processor.close_all_dbs()
        logger.info("Resources cleaned up. Goodbye.")

if __name__ == "__main__":
    main()
