import time
import logging
import uuid
import threading
from datetime import datetime, timezone
from collections import deque
from typing import Dict, Optional, Tuple, Any, List
import numpy as np
import report_manager
from utils.status_utils import is_valid_bpm, is_valid_spo2, get_status_and_codes, EMA_ALPHA
from database import DatabaseHandler

logger = logging.getLogger(__name__)

class DeviceState:
    def __init__(self, data_source: str, device_id: str, max_len: int = 100):
        self.data_source = data_source
        self.device_id = device_id
        self.bpm_window: deque = deque(maxlen=15)
        self.spo2_window: deque = deque(maxlen=15)
        self.last_ema_bpm: Optional[float] = None
        self.last_analysis_status: Optional[str] = None
        self.current_session_id: Optional[str] = None
        self.first_write_done: bool = False
        self.last_write_time: float = 0
        self.last_seen: float = time.time()
        self.lock: threading.RLock = threading.RLock()
        self.retry_queue: deque = deque(maxlen=max_len)

    def reset_and_delete(self, db_handler: Optional[DatabaseHandler]):
        """重置狀態並從資料庫刪除當前 Session 的所有數據"""
        with self.lock:
            if self.current_session_id and db_handler:
                try:
                    deleted_count = db_handler.delete_many({"session_id": self.current_session_id})
                    logger.info(f"[{self.device_id}] Deleted {deleted_count} records for session {self.current_session_id} due to RESET")
                except Exception as e:
                    logger.error(f"[{self.device_id}] Failed to delete records for session {self.current_session_id}: {e}")

            self.bpm_window.clear()
            self.spo2_window.clear()
            self.last_ema_bpm = None
            self.last_analysis_status = None
            self.current_session_id = None
            self.first_write_done = False
            self.last_write_time = 0
            self.retry_queue.clear()

    def reset_state_only(self):
        """僅重置狀態，但不從資料庫刪除當前 Session 的任何數據"""
        with self.lock:
            self.bpm_window.clear()
            self.spo2_window.clear()
            self.last_ema_bpm = None
            self.last_analysis_status = None
            self.current_session_id = None
            self.first_write_done = False
            self.last_write_time = 0

class StreamProcessor:
    def __init__(self, db_configs: Dict[str, Dict[str, Any]], retry_queue_max_len: int = 100):
        self.db_configs = db_configs
        self.retry_queue_max_len = retry_queue_max_len
        self.db_handlers: Dict[str, DatabaseHandler] = {}
        self.db_lock = threading.Lock()
        self.device_states: Dict[Tuple[str, str], DeviceState] = {}
        self.device_states_lock: threading.Lock = threading.Lock()

    def _write_or_queue_record(self, state: DeviceState, record: Dict[str, Any]) -> bool:
        """
        將記錄寫入資料庫或放入 retry_queue。
        此方法預期在 state.lock 的保護下呼叫。
        """
        device_id = state.device_id
        db_handler = self._get_db_handler(device_id)

        # 1. 檢查連線
        if db_handler:
            # 如果 queue 裡有累積的資料，嘗試批次寫入
            if state.retry_queue:
                queued_records = list(state.retry_queue)
                logger.info(f"[{device_id}] Found {len(queued_records)} items in retry queue. Attempting bulk insert.")
                if db_handler.insert_many(queued_records):
                    state.retry_queue.clear()
                    logger.info(f"[{device_id}] Bulk insert of {len(queued_records)} cached items succeeded.")

                    # 批次寫入成功後，接著寫入當前最新的這筆資料
                    if db_handler.insert_one(record):
                        logger.info(f"[{device_id}] Current record saved successfully after resolving queue.")
                        return True
                    else:
                        # 批次寫入成功，但最新資料寫入失敗：將最新資料放入剛清空的 queue 中
                        state.retry_queue.append(record)
                        logger.error(f"[{device_id}] Bulk insert succeeded but current record failed. Current record queued.")
                        return False
                else:
                    # 批次寫入失敗：歷史資料繼續保留在佇列中，最新資料也直接放入佇列 (依 FIFO 淘汰)
                    state.retry_queue.append(record)
                    logger.error(f"[{device_id}] Bulk insert failed. Current record appended to queue.")
                    return False
            else:
                # Queue 為空，直接寫入最新資料
                if db_handler.insert_one(record):
                    return True
                else:
                    state.retry_queue.append(record)
                    logger.error(f"[{device_id}] Insert failed. Record queued.")
                    return False
        else:
            # 無法獲取 db_handler 或無法連線，直接放進佇列 (依 FIFO 淘汰)
            state.retry_queue.append(record)
            logger.error(f"[{device_id}] Database handler not available. Record queued.")
            return False

    def _get_db_handler(self, device_id: str) -> Optional[DatabaseHandler]:
        """延遲載入連線池：根據 device_id 獲取資料庫處理器"""
        with self.db_lock:
            # 1. 檢查是否已存在
            if device_id in self.db_handlers:
                return self.db_handlers[device_id]

            # 2. 決定使用的配置（降級至 DEFAULT）
            target_config = self.db_configs.get(device_id)
            if not target_config:
                logger.info(f"[{device_id}] No specific DB config found, falling back to DEFAULT")
                if "DEFAULT" in self.db_handlers:
                    return self.db_handlers["DEFAULT"]
                target_config = self.db_configs["DEFAULT"]
                actual_key = "DEFAULT"
            else:
                actual_key = device_id

            # 3. 初始化連線
            try:
                handler = DatabaseHandler(
                    uri=target_config["uri"],
                    db_name=target_config["db_name"],
                    col_name=target_config["col_name"]
                )
                if handler.connect():
                    self.db_handlers[actual_key] = handler
                    return handler
                else:
                    logger.error(f"Failed to connect to MongoDB for {actual_key}")
                    return None
            except Exception as e:
                logger.error(f"Error initializing DatabaseHandler for {device_id}: {e}")
                return None

    def get_device_state(self, data_source: str, device_id: str) -> DeviceState:
        key = (data_source, device_id)
        with self.device_states_lock:
            if key not in self.device_states:
                self.device_states[key] = DeviceState(data_source, device_id, max_len=self.retry_queue_max_len)
            return self.device_states[key]

    def process_message(self, data_source: str, device_id: str, payload: Dict[str, Any]) -> None:
        """核心訊息處理邏輯"""
        try:
            state = self.get_device_state(data_source, device_id)
            state.last_seen = time.time()

            device_status = payload.get("device_status")

            # 1. 處理量測結束 (COMPLETED)
            if device_status == "COMPLETED":
                self._handle_completed(state, payload)
                return

            # 2. 處理系統重置 (RESET)
            if device_status == "RESET":
                logger.info(f"[{device_id}] System reset (source: {data_source}). Deleting current session data.")
                db_handler = self._get_db_handler(device_id)
                state.reset_and_delete(db_handler)
                return

            raw_bpm = payload.get("bpm")
            raw_spo2 = payload.get("spo2")

            # 3. 資料完整性與有效性檢查
            if raw_bpm is None or raw_spo2 is None:
                return

            if not is_valid_bpm(raw_bpm) or not is_valid_spo2(raw_spo2):
                logger.warning(f"[{device_id}] Invalid health data ({raw_bpm} BPM, {raw_spo2}% SpO2). Filtering.")
                return

            # 4. 工作階段 (Session) 管理
            with state.lock:
                if state.current_session_id is None:
                    state.current_session_id = str(uuid.uuid4())
                    logger.info(f"[{device_id}] Started new session: {state.current_session_id}")

                # 5. 生理指標運算 (MA & EMA)
                raw_bpm_f = float(raw_bpm)
                raw_spo2_f = float(raw_spo2)

                prev_xt_bpm = float(np.mean(state.bpm_window)) if len(state.bpm_window) > 0 else raw_bpm_f
                state.bpm_window.append(raw_bpm_f)
                state.spo2_window.append(raw_spo2_f)
                xt_bpm = float(np.mean(state.bpm_window))
                xt_spo2 = float(np.mean(state.spo2_window))

                if state.last_ema_bpm is None:
                    ema_bpm = xt_bpm
                else:
                    ema_bpm = EMA_ALPHA * xt_bpm + (1 - EMA_ALPHA) * state.last_ema_bpm

                delta_bpm = abs(raw_bpm_f - prev_xt_bpm)

                # 6. 狀態分析判斷 (SSoT)
                analysis_status, reason_codes = get_status_and_codes(raw_bpm_f, ema_bpm, delta_bpm, raw_spo2_f)
                state.last_ema_bpm = ema_bpm

                # 7. 智慧寫入機制
                current_time = time.time()
                should_write = False

                if not state.first_write_done:
                    should_write = True
                elif analysis_status == "DANGER":
                    should_write = True
                elif analysis_status != state.last_analysis_status:
                    should_write = True
                elif current_time - state.last_write_time >= 20:
                    should_write = True

                # 8. 執行資料庫寫入
                if should_write:
                    record = {
                        "timestamp": datetime.fromtimestamp(current_time, tz=timezone.utc),
                        "analysis_status": analysis_status,
                        "reason_codes": reason_codes,
                        "session_id": state.current_session_id,
                        "data_source": data_source,
                        "device_id": device_id,
                        "avg_bpm": xt_bpm,
                        "ema_bpm": float(ema_bpm),
                        "delta_bpm": float(delta_bpm),
                        "spo2": xt_spo2
                    }

                    self._write_or_queue_record(state, record)
                    # 無論寫入成功與否，皆更新狀態控制，代表本周期數據已被寫入/快取
                    state.last_write_time = current_time
                    state.last_analysis_status = analysis_status
                    state.first_write_done = True
        except Exception as e:
            logger.error(f"Processing error for {device_id}: {e}")

    def _handle_completed(self, state: DeviceState, payload: Dict[str, Any]) -> None:
        duration = payload.get("duration_sec", 0)
        logger.info(f"[{state.device_id}] Measurement ended (source: {state.data_source}), duration: {duration}s")

        # 僅正式量測且有有效 Session 時才發送 LINE 報告
        if state.data_source == "prod" and duration > 0 and state.current_session_id:
            report_manager.generate_and_send_report(state.current_session_id, duration, state.device_id)

        with state.lock:
            # 在 Time-series Collection 中，直接插入一筆特定的 COMPLETED 事件紀錄代表量測順利結束
            if state.current_session_id:
                record = {
                    "timestamp": datetime.fromtimestamp(time.time(), tz=timezone.utc),
                    "analysis_status": "COMPLETED",
                    "session_id": state.current_session_id,
                    "data_source": state.data_source,
                    "device_id": state.device_id,
                    "duration_sec": duration
                }
                self._write_or_queue_record(state, record)
                logger.info(f"[{state.device_id}] Handled COMPLETED event record for session {state.current_session_id}")

            # 重置該裝置狀態，但不刪除資料 (因為已完成)
            state.bpm_window.clear()
            state.spo2_window.clear()
            state.last_ema_bpm = None
            state.last_analysis_status = None
            state.last_write_time = 0
            state.first_write_done = False
            state.current_session_id = None

    def check_timeouts(self, timeout_sec: float = 30.0) -> None:
        """檢查逾時裝置並清理"""
        now = time.time()
        to_cleanup: List[DeviceState] = []

        with self.device_states_lock:
            for state in self.device_states.values():
                if state.current_session_id and (now - state.last_seen > timeout_sec):
                    to_cleanup.append(state)

        for state in to_cleanup:
            logger.info(f"[{state.device_id}] Session timeout detected ({timeout_sec}s). Soft-ending session...")
            with state.lock:
                if state.current_session_id:
                    record = {
                        "timestamp": datetime.fromtimestamp(time.time(), tz=timezone.utc),
                        "analysis_status": "TIMEOUT",
                        "session_id": state.current_session_id,
                        "data_source": state.data_source,
                        "device_id": state.device_id
                    }
                    self._write_or_queue_record(state, record)
                    logger.info(f"[{state.device_id}] Handled TIMEOUT event record for session {state.current_session_id}")

                state.reset_state_only()

    def flush_all_queues(self) -> None:
        """優雅關閉時的 Best-effort 歷史緩存寫入 (Flush)"""
        logger.info("Starting best-effort flush of all device retry queues...")
        with self.device_states_lock:
            states_to_flush = list(self.device_states.values())

        for state in states_to_flush:
            with state.lock:
                if state.retry_queue:
                    device_id = state.device_id
                    queued_records = list(state.retry_queue)
                    logger.info(f"[{device_id}] Flushing {len(queued_records)} remaining cached items during shutdown.")
                    db_handler = self._get_db_handler(device_id)
                    if db_handler:
                        # 嘗試寫入。連線超時時間已被 MongoClient (serverSelectionTimeoutMS) 限制在 3s 內
                        if db_handler.insert_many(queued_records):
                            state.retry_queue.clear()
                            logger.info(f"[{device_id}] Successfully flushed {len(queued_records)} cached items during shutdown.")
                        else:
                            logger.error(f"[{device_id}] Failed to flush cached items during shutdown (database offline).")
                    else:
                        logger.error(f"[{device_id}] Failed to flush cached items during shutdown (database handler unavailable).")

    def close_all_dbs(self) -> None:
        """優雅關閉機制：關閉所有已開啟的 MongoDB 連線"""
        with self.db_lock:
            for device_id, handler in self.db_handlers.items():
                try:
                    handler.close()
                    logger.info(f"Closed database connection for {device_id}")
                except Exception as e:
                    logger.error(f"Error closing database for {device_id}: {e}")
            self.db_handlers.clear()
