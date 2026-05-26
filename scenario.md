# PulseGuard IoT

## Smart Heart Rate Monitoring and Analysis System

---

# 1. 專題目標

使用 ESP32 與 MAX30102 建立 IoT 智慧心率與血氧監控系統。

系統功能：

* 即時量測 BPM 與 SpO₂
* TFT 顯示即時資訊
* LED 顯示健康狀態
* 蜂鳴器提供心跳提示音
* MQTT 即時傳輸資料
* 自訂 Web Dashboard 即時監控
* MySQL 儲存歷史資料
* Python 進行資料分析與狀態判斷
* Streamlit 顯示分析結果
* LINE 發送每日 / 每月摘要通知
* Railway 雲端部署

---

# 2. 系統整體架構

```text
MAX30102
    ↓
ESP32 (Arduino Framework)
 ├─ TFT 即時顯示
 ├─ LED 狀態燈
 ├─ 蜂鳴器（Heartbeat Beep）
 ├─ Button 控制
 ├─ 狀態機控制
 ├─ Wi-Fi
 └─ MQTT Publish
        ↓
   HiveMQ Broker
      ↙      ↘
 Web Dashboard   Python Analysis
(MQTT.js +        ↓
 Chart.js)     smoothing
    ↓          狀態判斷
即時監控      平均化分析
                 ↓
               MySQL
                 ↓
             Streamlit
                 ↓
           LINE 摘要通知
```

---

# 3. 系統技術棧（Tech Stack）

| 層級                    | 技術                      |
| --------------------- | ----------------------- |
| Edge Device           | ESP32                   |
| Firmware              | Arduino Framework       |
| Sensor                | MAX30102                |
| IoT Protocol          | MQTT                    |
| MQTT Broker           | HiveMQ                  |
| Frontend Dashboard    | HTML / CSS / JavaScript |
| Real-time MQTT Client | MQTT.js                 |
| Chart Visualization   | Chart.js                |
| Backend Analysis      | Python                  |
| Database              | MySQL                   |
| Data Visualization    | Streamlit               |
| Notification          | LINE Messaging API      |
| Cloud Platform        | Railway                 |

---

# 4. 使用硬體

| 元件            | 用途         |
| ------------- | ---------- |
| ESP32 NodeMCU | 主控制器       |
| MAX30102      | 心率 / 血氧感測  |
| TFT 彩色螢幕      | 即時顯示       |
| LED ×3        | 狀態燈        |
| 有源蜂鳴器         | 心跳提示音      |
| Button ×1     | 開始 / Reset |
| 麵包板           | 電路連接       |
| 杜邦線           | 接線         |
| USB供電         | 電源         |

---

# 5. ESP32（Arduino）負責功能

ESP32 使用：

## Arduino Framework

開發。

---

## ESP32 功能

| 功能               | 說明                              |
| ---------------- | ------------------------------- |
| MAX30102 讀取      | BPM / SpO₂                      |
| TFT 控制           | 即時顯示                            |
| LED 控制           | 狀態燈                             |
| 蜂鳴器控制            | heartbeat beep                  |
| Button 控制        | 開始 / Reset                      |
| 狀態機控制            | WAITING / MEASURING / NO_FINGER |
| Wi-Fi 連線         | 網路連線                            |
| MQTT Publish     | 傳送感測資料                          |
| MQTT Reconnect   | Broker 重連                       |
| Finger Detection | 手指離開偵測                          |

---

# 6. Arduino 使用 Library

| Library           | 用途       |
| ----------------- | -------- |
| SparkFun MAX3010x | MAX30102 |
| heartRate.h       | BPM 計算   |
| TFT_eSPI          | TFT 顯示   |
| PubSubClient      | MQTT     |
| WiFi.h            | Wi-Fi    |

---

# 7. Button 設計

僅保留 1 顆按鈕。

| 操作 | 功能       |
| -- | -------- |
| 短按 | 開始量測     |
| 長按 | Reset 系統 |

---

# 8. Reset 功能

長按後：

* 清空 BPM buffer
* 清空 SpO₂ cache
* 停止 MQTT Publish
* 停止 MySQL 寫入
* TFT 回待機畫面
* LED 回初始狀態
* 清空 elapsed time
* 重置狀態機

---

# 9. 系統狀態機（State Machine）

## 狀態

| 狀態             | 說明       |
| -------------- | -------- |
| WAITING        | 等待開始     |
| MEASURING      | 正在量測     |
| NO_FINGER      | 手指離開     |
| WIFI_LOST      | Wi-Fi 中斷 |
| MQTT_RECONNECT | MQTT 重連中 |
| SENSOR_ERROR   | 感測器異常    |

---

## 狀態流程

```text
WAITING
   ↓
短按開始
   ↓
等待手指
   ↓
MEASURING
   ↓
手指移開
   ↓
NO_FINGER
   ↓
重新放手指
   ↓
MEASURING
```

---

# 10. 手指離開偵測

MAX30102 使用 IR value 判斷是否有手指。

---

## 無手指時 TFT 顯示

```text
Finger Removed

Measurement Paused
```

---

## 無手指時系統行為

| 功能     | 行為  |
| ------ | --- |
| BPM更新  | 停止  |
| SpO₂更新 | 停止  |
| MQTT   | 暫停  |
| MySQL  | 不寫入 |
| 蜂鳴器    | 不響  |

---

# 11. TFT 顯示內容

## 待機畫面

```text
PulseGuard IoT

Press Button
To Start
```

---

## 等待手指

```text
Place Finger
On Sensor
```

---

## 量測畫面

```text
BPM: 78
SpO2: 98%

Status: NORMAL

Time:
01:24
```

---

# 12. 已量測時間（Elapsed Time）

系統：

* 至少量測 1 分鐘
* 超過 1 分鐘後仍可持續量測

TFT 顯示：

```text
Time: 01:24
```

---

# 13. LED 狀態燈

| LED | 狀態      |
| --- | ------- |
| 綠燈  | NORMAL  |
| 黃燈  | WARNING |
| 紅燈  | DANGER  |

---

# 14. 蜂鳴器功能

用途：

Heartbeat Beep

每次偵測到 pulse：

```text
逼… 逼…
```

短響一次。

---

## 蜂鳴器規則

| 狀態           | 行為             |
| ------------ | -------------- |
| WAITING      | 不響             |
| MEASURING    | heartbeat beep |
| NO_FINGER    | 不響             |
| SENSOR_ERROR | 不響             |

---

# 15. MQTT 架構

ESP32 每秒 publish：

```json
{
  "device_id": "pulseguard_01",
  "bpm": 79,
  "spo2": 98,
  "status": "NORMAL",
  "elapsed_time": 84,
  "signal_quality": 92
}
```

---

## MQTT Topic 設計

```text
pulseguard/device01/vitals
pulseguard/device01/status
pulseguard/device01/system
```

---

## MQTT 分工

| 系統            | 功能        |
| ------------- | --------- |
| ESP32         | Publish   |
| Web Dashboard | Subscribe |
| Python        | Subscribe |

---

# 16. HiveMQ Broker

系統使用：

## HiveMQ Cloud

作為 MQTT Broker。

---

## HiveMQ 功能

| 功能                    | 用途        |
| --------------------- | --------- |
| MQTT Broker           | IoT 資料交換  |
| Client Authentication | MQTT 帳號驗證 |
| TLS Encryption        | 加密傳輸      |
| Multi-client Support  | 多裝置連線     |
| Cloud Deployment      | 雲端運行      |

---

## ESP32 連線流程

```text
ESP32
   ↓
Wi-Fi Connect
   ↓
Connect HiveMQ
   ↓
MQTT Authentication
   ↓
Publish Sensor Data
```

---

# 17. Web Dashboard 架構

使用：

* HTML
* CSS
* JavaScript
* MQTT.js
* Chart.js

建立自訂即時監控網頁。

---

## Dashboard 功能

| 功能             | 說明                        |
| -------------- | ------------------------- |
| MQTT Subscribe | 即時接收資料                    |
| BPM 即時顯示       | 心率監控                      |
| SpO₂ 即時顯示      | 血氧監控                      |
| 即時折線圖          | BPM 趨勢                    |
| 狀態顯示           | NORMAL / WARNING / DANGER |
| 時間顯示           | Elapsed Time              |
| 連線狀態           | MQTT 狀態                   |

---

## Dashboard 即時流程

```text
HiveMQ Broker
      ↓
 MQTT.js Subscribe
      ↓
 JavaScript Parse JSON
      ↓
 Chart.js Update
      ↓
 Web Dashboard 即時更新
```

---

# 18. Chart.js 圖表功能

Chart.js 負責：

* BPM 即時折線圖
* SpO₂ 即時折線圖
* 歷史趨勢顯示
* 資料動態更新

---

## 即時折線圖內容

```text
X-axis : Time
Y-axis : BPM / SpO₂
```

---

# 19. 資料處理方式

採用：

* 即時更新
* 20 秒平均儲存
* EMA smoothing
* Outlier filtering

---

## 即時層（1秒）

ESP32：

每秒：

* 更新 TFT
* 發送 MQTT
* 更新 heartbeat beep

---

## 分析層（20秒）

Python：

每 20 秒：

* 收集 BPM 資料
* 計算 EMA 平均
* 移除異常值
* 判斷 Status
* 寫入 MySQL

---

# 20. BPM 平均公式

使用 EMA（Exponential Moving Average）：

[
EMA_t = \alpha x_t + (1-\alpha)EMA_{t-1}
]

---

# 21. BPM 變化量公式

[
\Delta BPM = BPM_{current} - BPM_{previous}
]

---

# 22. 心率與血氧聯合判斷流程

## 狀態分級表

| 狀態      | 心率條件 (ΔBPM)            | 血氧條件 (SpO₂) | 臨床意義                  |
| ------- | ---------------------- | ----------- | --------------------- |
| NORMAL  | |ΔBPM| < 10 且 BPM > 50 | 95% ~ 100%  | 穩定，供氧正常               |
| WARNING | |ΔBPM| ≥ 10 且 < 50     | 90% ~ 94%   | 需注意，可能有供氧不足或心律不整      |
| DANGER  | BPM ≤ 50 或 |ΔBPM| ≥ 50 | < 90%       | 高風險，可能是心臟衰竭、呼吸障礙或急性事件 |

---

# 23. 判斷邏輯

## NORMAL

```text
|ΔBPM| < 10
SpO₂ ≥ 95%
BPM > 50
```

---

## WARNING

```text
|ΔBPM| ≥ 10 且 < 50
SpO₂ = 91~94%
```

---

## DANGER

```text
BPM ≤ 50
或
|ΔBPM| ≥ 50
或
SpO₂ ≤ 90%
```

---

# 24. Status 同步顯示

Python 判斷完成後：

Status 同步至：

* TFT
* LED
* Web Dashboard
* MySQL
* Streamlit

---

# 25. MySQL 資料表

## heart_rate_data

| 欄位             | 用途                        |
| -------------- | ------------------------- |
| id             | Primary Key               |
| timestamp      | 時間                        |
| device_id      | 裝置 ID                     |
| raw_bpm        | 原始 BPM                    |
| bpm_avg        | EMA BPM                   |
| spo2           | 血氧                        |
| delta_bpm      | BPM 變化量                   |
| signal_quality | 訊號品質                      |
| status         | NORMAL / WARNING / DANGER |
| elapsed_time   | 已量測秒數                     |

---

# 26. Python 功能

Python 負責：

* MQTT Subscribe
* smoothing
* EMA 計算
* outlier filtering
* ΔBPM 計算
* Status 判斷
* MySQL 寫入
* 長期分析
* 趨勢分析
* 統計分析
* 異常事件分析

---

# 27. Streamlit 功能

Streamlit 負責：

* 視覺化分析
* 歷史趨勢
* 每日分析
* 每月分析
* 危險事件統計
* BPM 趨勢圖
* SpO₂ 趨勢圖

---

# 28. LINE 通知功能

LINE 僅負責摘要通知。

---

## 每日摘要

```text
📊 Daily Health Summary

Average BPM: 78
Highest BPM: 112
Lowest BPM: 61

Average SpO₂: 98%
```

---

## 每月摘要

```text
📈 Monthly Health Summary

Average BPM: 76
Highest BPM: 128
Lowest BPM: 58

Average SpO₂: 97%
```

---

# 29. Cloud 架構

使用 Railway 部署：

| 服務            | 用途          |
| ------------- | ----------- |
| HiveMQ        | MQTT Broker |
| MySQL         | 資料庫         |
| Python        | 分析服務        |
| Streamlit     | 視覺化平台       |
| Web Dashboard | 即時監控頁面      |

---

# 30. 系統安全性

## MQTT 安全機制

| 功能                  | 用途      |
| ------------------- | ------- |
| Username / Password | MQTT 驗證 |
| TLS                 | 加密傳輸    |
| Device ID           | 裝置識別    |

---

## Database 安全性

* 使用環境變數保存帳號密碼
* 不公開 MySQL Port
* Railway Private Network

---

# 31. 錯誤處理機制

| 問題                | 系統行為            |
| ----------------- | --------------- |
| Wi-Fi 中斷          | 自動重新連線          |
| MQTT 中斷           | 自動 reconnect    |
| MAX30102 無回應      | 進入 SENSOR_ERROR |
| 手指移開              | 停止量測            |
| MQTT Publish Fail | Retry publish   |

---

# 32. 系統資料流

```text
MAX30102
   ↓
ESP32
   ↓ MQTT Publish
HiveMQ Broker
   ↓
Python Subscribe
   ↓
EMA + Analysis
   ↓
MySQL
   ↓
Streamlit Analytics
   ↓
LINE Summary
```

---

# 33. Web Dashboard 資料流

```text
HiveMQ Broker
      ↓
 MQTT.js
      ↓
 JSON Parsing
      ↓
 Chart.js Update
      ↓
 Web Real-time Dashboard
```

---

# 34. 專題定位

PulseGuard IoT 屬於：

# IoT 智慧健康監控與資料分析平台

具備：

* 即時生理監測
* IoT 即時傳輸
* Web Dashboard
* 雲端 MQTT 架構
* 即時資料視覺化
* 長期資料分析
* 異常狀態判斷
* 健康摘要通知
* 雲端部署
* 可擴充 IoT 架構

---

# 35. 專題特色

## Embedded System

* ESP32 State Machine
* Real-time Sensor Reading
* TFT UI
* Heartbeat Beep

---

## IoT Architecture

* MQTT Protocol
* HiveMQ Cloud Broker
* Multi-client Subscription
* Real-time Streaming

---

## Web Technology

* MQTT.js
* Chart.js
* JavaScript Real-time Update
* Web Dashboard

---

## Data Analysis

* EMA smoothing
* Outlier Filtering
* Status Classification
* Trend Analysis

---

## Cloud Platform

* Railway Deployment
* Cloud Database
* Streamlit Analytics
* LINE Notification
