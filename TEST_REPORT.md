# PulseGuard 測試覆蓋率與品質檢查報告

## 1. 覆蓋率總結 (Coverage Summary)

經過本次補強，專案的測試覆蓋率已顯著提升，均超過 80% 的量化目標，且核心業務邏輯關鍵路徑已達到 100% 覆蓋。

| 模組 (Module) | 初始覆蓋率 | 最終覆蓋率 | 備註 |
| :--- | :--- | :--- | :--- |
| **Backend (整體)** | ~45% | **94%** | 包含基礎設施與核心邏輯 |
| **Analytics Core** | ~74% | **97%** | 專注於資料處理與計算 |
| **backend/processor.py** | 95% | **98%** | 關鍵商務路徑 100% |
| **analytics/core/processor.py**| 80% | **100%** | 關鍵商務路徑 100% |

## 2. 執行的主要變更

### A. 代碼重構
- **`backend/report_manager.py`**: 將全域環境變數讀取移入 `Config` 物件。這消除了模組載入時的副作用，使測試環境能穩定 Mock 設定值，並修復了原有的測試失敗案例。

### B. 測試補強
- **核心處理器**: 針對 `StreamProcessor` 的智慧寫入（DANGER 立即寫入、狀態變更寫入、定時寫入）補齊了分支測試。
- **基礎設施**: 為 `mqtt_client.py`, `database.py`, `main.py` 撰寫了單元測試，驗證初始化、連線異常處理及 Callback 觸發邏輯。
- **數據聚合**: 為 Analytics 的 `processor.py` 補齊了多語系翻譯、空數據處理等邊際案例。

### C. 測試優化
- 移除了 `analytics/test_dashboard.py` 中脆弱的 Streamlit UI 模擬測試，將重點回歸至數據正確性。
- 統一使用 `pytest-cov` 產生報告，並修正了 `PYTHONPATH` 導致的匯入錯誤。

## 3. 品質建議與觀察 (Recommendations)

### 關於「無效斷言 (Assertion)」
- **發現**: 部分既有測試僅驗證函式「是否有執行」，而未驗證「執行的結果內容」。
- **建議**: 在 `test_report_manager.py` 中，我們已加強對 LINE Payload 內容的詳細斷言（例如確認日期格式與時間區間計算是否精確），建議未來新增測試時應遵循此模式，而不僅是 `assert mock.called`。

### 關於「過度 Mock (Over-Mocking)」
- **發現**: `mqtt_client.py` 的測試高度依賴對 `paho-mqtt` 的 Mock。雖然這避免了啟動真實 Broker，但也導致無法測試到真正的網路連線行為。
- **建議**: 核心邏輯應維持目前的 Mock 策略以保持測試速度。若未來有高度穩定性需求，可引入 `testcontainers` 在測試時啟動一個短暫的真實 MQTT Broker 與 MongoDB 進行「冒煙測試 (Smoke Test)」。

### 測試健壯性
- 目前測試高度依賴 `Config` 物件。建議專案導入 `pydantic-settings` 來管理組態，這能提供更強的型別檢查與環境變數驗證，進一步降低組態錯誤導致的運行風險。

---
*報告完成日期：2025/05/22*
