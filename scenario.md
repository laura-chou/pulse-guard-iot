# PulseGuard IoT

## Smart Heart Rate Monitoring and Analysis System

---

# 1. 專題目標

PulseGuard IoT 是一套結合物聯網（IoT）、雲端平台與資料分析的智慧健康監測系統。

系統利用 MAX30102 感測器量測使用者的心率（BPM）與血氧濃度（SpO₂），透過 MQTT 即時傳輸至雲端，並進行資料分析、長期儲存與視覺化監控。

主要功能：

- 即時量測 BPM 與 SpO₂
- TFT 顯示即時資訊
- LED 顯示健康狀態
- 蜂鳴器提示
- MQTT 即時資料傳輸
- Web Dashboard 即時監控
- MongoDB Atlas 雲端資料庫
- Python 資料分析
- Streamlit Dashboard
- LINE 健康摘要通知
- Railway 雲端部署

---

# 2. 系統整體架構

```text
MAX30102
    ↓
ESP32 (Arduino Framework)
 ├─ BPM / SpO₂ 計算
 ├─ TFT 即時顯示
 ├─ LED 狀態燈
 ├─ 蜂鳴器提示
 ├─ Button 控制
 ├─ Wi-Fi
 └─ MQTT Publish (Every 2 sec)
          ↓
      HiveMQ Broker
          ↓
    ┌──────────────┬──────────────┐
    ↓              ↓
Web Dashboard    Python Service
(MQTT.js +       (Railway)
 Chart.js)           ↓
                  Analysis
                     ↓
              MongoDB Atlas
                     ↓
          Streamlit Dashboard
          (Community Cloud)
                     ↓
               LINE Notify
```

---

# 3. 系統技術棧（Tech Stack）

| 層級 | 技術 |
|--------|--------|
| Edge Device | ESP32 |
| Firmware | Arduino Framework |
| Sensor | MAX30102 |
| IoT Protocol | MQTT |
| MQTT Broker | HiveMQ Cloud |
| Dashboard | MQTT.js + Chart.js |
| Backend Service | Python |
| Database | MongoDB Atlas |
| Data Analysis | Pandas |
| Visualization | Streamlit |
| Notification | LINE Messaging API |
| Cloud Platform | Railway |
| Dashboard Hosting | Streamlit Community Cloud |

---

# 4. 使用硬體

| 元件 | 用途 |
|--------|--------|
| ESP32 NodeMCU | 主控制器 |
| MAX30102 | 心率與血氧感測器 |
| TFT LCD | 即時顯示 |
| LED ×3 | 狀態燈 |
| Active Buzzer | 蜂鳴器 |
| Push Button | 開始 / Reset |
| Breadboard | 電路連接 |
| Jumper Wire | 接線 |
| USB Power | 電源供應 |

---

# 5. ESP32 功能

ESP32 負責：

- BPM 計算
- SpO₂ 計算
- Finger Detection
- TFT 顯示
- LED 狀態顯示
- 蜂鳴器提示
- MQTT Publish
- Wi-Fi 管理
- MQTT Reconnect

---

# 6. 使用 Library

| Library | 用途 |
|----------|----------|
| SparkFun MAX3010x | MAX30102 |
| heartRate.h | BPM 計算 |
| TFT_eSPI | TFT 顯示 |
| PubSubClient | MQTT |
| WiFi.h | Wi-Fi |
| ArduinoJson | JSON 資料封裝 |

---

# 7. Button 與 Reset

| 操作 | 功能 |
|--------|--------|
| 短按 | 開始量測 |
| 長按 | 系統 Reset |

Reset 後：

- 清空 BPM Buffer
- 清空 SpO₂ 資料
- 停止 MQTT Publish
- TFT 回待機畫面
- LED 回初始狀態

---

# 8. 手指偵測

透過 MAX30102 IR 值判斷是否有手指接觸。

無手指時：

```text
Finger Removed

Measurement Paused
```

系統將：

- 暫停 BPM 更新
- 暫停 SpO₂ 更新
- 暫停 MQTT 傳輸
- 停止蜂鳴器

---

# 9. TFT 顯示介面

## 待機畫面

```text
PulseGuard IoT

Press Button
To Start
```

## 等待量測

```text
Place Finger
On Sensor
```

## 即時量測

```text
BPM: 78

SpO₂: 98%

Status: NORMAL
```

---

# 10. LED 與蜂鳴器

## LED 狀態燈

| LED | 狀態 |
|--------|--------|
| 綠燈 | NORMAL |
| 黃燈 | WARNING |
| 紅燈 | DANGER |

---

## 蜂鳴器

### Heartbeat Beep

每次偵測到心跳時短響一次。

### Status Alert

| 狀態 | 提示音 |
|--------|--------|
| NORMAL | 1 次 |
| WARNING | 2 次 |
| DANGER | 4 次 |

---

# 11. MQTT 架構

系統採用 MQTT Publish / Subscribe 架構。

使用 HiveMQ Cloud 作為 MQTT Broker。

ESP32 每 2 秒發送一次資料。

---

## MQTT Topic

```text
pulseguard/data
```

---

## MQTT Payload

```json
{
  "bpm": 79,
  "spo2": 98,
  "status": "NORMAL"
}
```

---

## MQTT 分工

| 系統 | 功能 |
|--------|--------|
| ESP32 | Publish |
| Web Dashboard | Subscribe |
| Python Service | Subscribe |

---

# 12. Web Dashboard

使用：

- HTML
- CSS
- JavaScript
- MQTT.js
- Chart.js

功能：

- BPM 即時顯示
- SpO₂ 即時顯示
- Status 顯示
- 即時折線圖
- MQTT 連線狀態

---

## Dashboard 流程

```text
HiveMQ Broker
      ↓
 MQTT.js
      ↓
 JSON Parse
      ↓
 Chart.js
      ↓
 Real-Time Dashboard
```

---

# 13. Python 分析服務

Python 部署於 Railway。

每 20 秒執行一次分析流程：

1. 收集 MQTT 資料
2. 移除異常值
3. 計算 EMA 平均
4. 判斷健康狀態
5. 寫入 MongoDB Atlas

---

## Outlier Filter

移除不合理數值：

```text
BPM < 40
BPM > 180
SpO₂ < 70
SpO₂ > 100
```

---

## EMA 計算

```text
EMA = α × Current + (1 − α) × Previous EMA
```

---

## Status 判斷

### NORMAL

```text
60 ≤ BPM ≤ 100
AND
SpO₂ ≥ 95%
```

### WARNING

```text
50 ≤ BPM < 60
OR
100 < BPM ≤ 120
OR
91 ≤ SpO₂ < 95
```

### DANGER

```text
BPM < 50
OR
BPM > 120
OR
SpO₂ ≤ 90
```

---

# 14. MongoDB Atlas

資料以 Document 形式儲存。

Collection：

```text
heart_rate_data
```

---

## Document 範例

```json
{
  "timestamp": "2026-06-01T20:00:00Z",
  "bpm_avg": 79,
  "spo2": 98,
  "status": "NORMAL"
}
```

---

# 15. Streamlit Dashboard

使用 Streamlit Community Cloud 部署。

功能：

- BPM 趨勢圖
- SpO₂ 趨勢圖
- 狀態統計
- 每日分析
- 每月分析
- 異常事件分析

資料來源：

```text
MongoDB Atlas
```

---

# 16. LINE 健康摘要

系統定期產生健康摘要。

---

## Daily Summary

```text
📊 Daily Health Summary

Average BPM: 78
Highest BPM: 112
Lowest BPM: 61

Average SpO₂: 98%
```

---

## Monthly Summary

```text
📈 Monthly Health Summary

Average BPM: 76
Highest BPM: 128
Lowest BPM: 58

Average SpO₂: 97%
```

---

# 17. 雲端部署架構

| 平台 | 用途 |
|--------|--------|
| HiveMQ Cloud | MQTT Broker |
| Railway | Python Analysis Service |
| MongoDB Atlas | Cloud Database |
| Streamlit Community Cloud | Dashboard |
| LINE Messaging API | 通知服務 |

---

# 18. 系統特色

- ESP32 即時健康監測
- MQTT IoT 架構
- HiveMQ Cloud Broker
- Web Dashboard 即時監控
- MongoDB Atlas 雲端資料庫
- Python 自動分析
- Streamlit 視覺化平台
- LINE 健康摘要通知
- Railway 雲端部署

---

# 19. 專題定位

PulseGuard IoT 為一套結合：

- IoT
- Cloud Computing
- Data Analytics
- Visualization

的智慧健康監控平台。

系統提供：

- 即時生理監測
- 雲端資料儲存
- 健康狀態分析
- 長期趨勢追蹤
- 視覺化 Dashboard
- 自動化健康摘要通知

適合作為智慧醫療與健康照護領域的 IoT 應用展示。