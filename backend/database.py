import logging
from pymongo import MongoClient
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self, uri: str, db_name: str, col_name: str):
        self.uri = uri
        self.db_name = db_name
        self.col_name = col_name
        self.client: Optional[MongoClient] = None
        self.collection: Any = None

    def connect(self, timeout_ms: int = 3000) -> bool:
        """初始化 MongoDB 連線"""
        try:
            # 設定連線、通訊與伺服器選擇超時時間（預設 3000 毫秒 / 3 秒）
            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=timeout_ms,
                socketTimeoutMS=timeout_ms
            )
            db = self.client[self.db_name]
            self.collection = db[self.col_name]
            # 測試連線
            self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            return True
        except Exception as e:
            logger.error(f"MongoDB connection error: {e}")
            return False

    def insert_one(self, record: Dict[str, Any]) -> bool:
        """插入單筆數據"""
        if self.collection is None:
            logger.error("Database not connected. Cannot insert record.")
            return False
        try:
            self.collection.insert_one(record)
            return True
        except Exception as e:
            logger.error(f"MongoDB insert error: {e}")
            return False

    def insert_many(self, records: List[Dict[str, Any]]) -> bool:
        """批次寫入數據 (Bulk Insert)"""
        if self.collection is None:
            logger.error("Database not connected. Cannot insert records.")
            return False
        if not records:
            return True
        try:
            self.collection.insert_many(records)
            return True
        except Exception as e:
            logger.error(f"MongoDB insert_many error: {e}")
            return False

    def delete_many(self, query: Dict[str, Any]) -> int:
        """刪除多筆數據"""
        if self.collection is None:
            logger.error("Database not connected. Cannot delete records.")
            return 0
        try:
            result = self.collection.delete_many(query)
            return result.deleted_count
        except Exception as e:
            logger.error(f"MongoDB delete error: {e}")
            return 0

    def close(self):
        """關閉連線"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
