import sys
import logging
import signal
from pydantic import ValidationError
from config import Config
from database import DatabaseHandler
from processor import StreamProcessor
from mqtt_client import MQTTManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger(__name__)

def sigterm_handler(signum, frame):
    logger.info(f"Received signal {signum}. Raising KeyboardInterrupt for graceful shutdown...")
    raise KeyboardInterrupt

def main():
    # 註冊信號處理器
    signal.signal(signal.SIGINT, sigterm_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)

    # 1. 載入組態
    try:
        config = Config()
    except ValidationError as e:
        logger.error(f"Configuration error: {e}")
        return

    # 2. 初始化處理器（注入資料庫配置及 retry_queue_max_len）
    processor = StreamProcessor(
        db_configs=config.MONGO_DB_CONFIG,
        retry_queue_max_len=config.RETRY_QUEUE_MAX_LEN
    )

    # 3. 初始化 MQTT 管理器
    mqtt_manager = MQTTManager(config=config, processor=processor)

    # 4. 啟動主迴圈
    logger.info("PulseGuard Stream Processor started successfully.")
    try:
        mqtt_manager.run()
    except KeyboardInterrupt:
        logger.info("PulseGuard Stream Processor shutting down...")
    finally:
        # 在關閉連線前，執行最佳努力 (Best-effort) 的 Flush 機制將 retry queue 的內容寫入資料庫
        try:
            processor.flush_all_queues()
        except Exception as e:
            logger.error(f"Error flushing queues during shutdown: {e}")

        # 優雅關閉所有資料庫連線
        processor.close_all_dbs()
        logger.info("Resources cleaned up. Goodbye.")

if __name__ == "__main__":
    main()
