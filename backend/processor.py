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
    def __init__(self, data_source: str, device_id: str):
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
        self.lock: threading.Lock = threading.Lock()

    def reset_and_delete(self, db_handler: Optional[DatabaseHandler]):
        """重置狀態並從資料庫刪除當前 Session 的所有數據"""
        with self.lock:
            if self.current_session_id and db_handler:
                try:
                    deleted_count = db_handler.delete_many({"session_id": self.current_session_id})
                    logger.info(f"[{self.device_id}] Deleted {deleted_count} records for session {self.current_session_id} due to RESET/Timeout")
                except Exception as e:
                    logger.error(f"[{self.device_id}] Failed to delete records for session {self.current_session_id}: {e}")

            self.bpm_window.clear()
            self.spo2_window.clear()
            self.last_ema_bpm = None
            self.last_analysis_status = None
            self.current_session_id = None
            self.first_write_done = False
            self.last_write_time = 0

class StreamProcessor:
    def __init__(self, db_handler: DatabaseHandler):
        self.db_handler = db_handler
        self.device_states: Dict[Tuple[str, str], DeviceState] = {}
        self.device_states_lock: threading.Lock = threading.Lock()

    def get_device_state(self, data_source: str, device_id: str) -> DeviceState:
        key = (data_source, device_id)
        with self.device_states_lock:
            if key not in self.device_states:
                self.device_states[key] = DeviceState(data_source, device_id)
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
                state.reset_and_delete(self.db_handler)
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

                    if self.db_handler.insert_one(record):
                        state.last_write_time = current_time
                        state.last_analysis_status = analysis_status
                        state.first_write_done = True
                        logger.info(f"[{device_id}] Data saved | Status: {analysis_status}")
        except Exception as e:
            logger.error(f"Processing error for {device_id}: {e}")

    def _handle_completed(self, state: DeviceState, payload: Dict[str, Any]) -> None:
        duration = payload.get("duration_sec", 0)
        logger.info(f"[{state.device_id}] Measurement ended (source: {state.data_source}), duration: {duration}s")

        # 僅正式量測且有有效 Session 時才發送 LINE 報告
        if state.data_source == "prod" and duration > 0 and state.current_session_id:
            report_manager.generate_and_send_report(state.current_session_id, duration)

        # 重置該裝置狀態，但不刪除資料 (因為已完成)
        with state.lock:
            state.bpm_window.clear()
            state.spo2_window.clear()
            state.last_ema_bpm = None
            state.last_analysis_status = None
            state.last_write_time = 0
            state.first_write_done = False
            state.current_session_id = None

    def check_timeouts(self, timeout_sec: float = 10.0) -> None:
        """檢查逾時裝置並清理"""
        now = time.time()
        to_cleanup: List[DeviceState] = []

        with self.device_states_lock:
            for state in self.device_states.values():
                if state.current_session_id and (now - state.last_seen > timeout_sec):
                    to_cleanup.append(state)

        for state in to_cleanup:
            logger.info(f"[{state.device_id}] Session timeout detected ({timeout_sec}s). Cleaning up...")
            state.reset_and_delete(self.db_handler)
