# PulseGuard IoT
## Smart Heart Rate Monitoring and Analysis System

---

# 1. 專題目標

使用 ESP32 與 MAX30102 建立 IoT 智慧心率與血氧監控系統。

系統功能：

- 即時量測 BPM 與 SpO₂
- TFT 顯示即時資訊
- LED 顯示健康狀態
- 蜂鳴器提供心跳提示音
- MQTT 即時傳輸資料
- Node-RED 即時監控
- MySQL 儲存歷史資料
- Python 進行資料分析與狀態判斷
- Streamlit 顯示分析結果
- LINE 發送每日 / 每月摘要通知

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
   MQTT Broker
      ↙      ↘
 Node-RED   Python
    ↓          ↓
Dashboard   smoothing
即時監控      狀態判斷
             平均化分析
                 ↓
               MySQL
                 ↓
             Streamlit
                 ↓
           LINE 摘要通知
```

---

# 3. 系統技術棧（Tech Stack）

| 層級 | 技術 |
|---|---|
| Edge Device | ESP32 |
| Firmware | Arduino Framework |
| Sensor | MAX30102 |
| IoT Protocol | MQTT |
| Dashboard | Node-RED |
| Backend Analysis | Python |
| Database | MySQL |
| Visualization | Streamlit |
| Notification | LINE |
| Cloud Platform | Railway |

---

# 4. 使用硬體

| 元件 | 用途 |
|---|---|
| ESP32 NodeMCU | 主控制器 |
| MAX30102 | 心率 / 血氧感測 |
| TFT 彩色螢幕 | 即時顯示 |
| LED ×3 | 狀態燈 |
| 有源蜂鳴器 | 心跳提示音 |
| Button ×1 | 開始 / Reset |
| 麵包板 | 電路連接 |
| 杜邦線 | 接線 |
| USB供電 | 電源 |

---

# 5. ESP32（Arduino）負責功能

ESP32 使用：

## Arduino Framework

開發。

---

## ESP32 功能

| 功能 | 說明 |
|---|---|
| MAX30102 讀取 | BPM / SpO₂ |
| TFT 控制 | 即時顯示 |
| LED 控制 | 狀態燈 |
| 蜂鳴器控制 | heartbeat beep |
| Button 控制 | 開始 / Reset |
| 狀態機控制 | WAITING / MEASURING / NO_FINGER |
| Wi-Fi 連線 | 網路連線 |
| MQTT Publish | 傳送感測資料 |

---

# 6. Arduino 使用 Library

| Library | 用途 |
|---|---|
| SparkFun MAX3010x | MAX30102 |
| TFT_eSPI | TFT 顯示 |
| PubSubClient | MQTT |
| WiFi.h | Wi-Fi |

---

# 7. Button 設計

僅保留 1 顆按鈕。

| 操作 | 功能 |
|---|---|
| 短按 | 開始量測 |
| 長按 | Reset 系統 |

---

# 8. Reset 功能

長按後：

- 清空 BPM buffer
- 清空 SpO₂ cache
- 停止 MQTT Publish
- 停止 MySQL 寫入
- TFT 回待機畫面
- LED 回初始狀態

---

# 9. 系統狀態機（State Machine）

## 狀態

| 狀態 | 說明 |
|---|---|
| WAITING | 等待開始 |
| MEASURING | 正在量測 |
| NO_FINGER | 手指離開 |

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

| 功能 | 行為 |
|---|---|
| BPM更新 | 停止 |
| SpO₂更新 | 停止 |
| MQTT | 暫停 |
| MySQL | 不寫入 |
| 蜂鳴器 | 不響 |

---

# 11. TFT 顯示內容

---

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

- 至少量測 1 分鐘
- 超過 1 分鐘後仍可持續量測

TFT 顯示：

```text
Time: 01:24
```

---

# 13. LED 狀態燈

| LED | 狀態 |
|---|---|
| 綠燈 | NORMAL |
| 黃燈 | WARNING |
| 紅燈 | DANGER |

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

| 狀態 | 行為 |
|---|---|
| WAITING | 不響 |
| MEASURING | heartbeat beep |
| NO_FINGER | 不響 |

---

# 15. MQTT 架構

ESP32 每秒 publish：

```json
{
  "bpm": 79,
  "spo2": 98,
  "status": "NORMAL",
  "elapsed_time": 84
}
```

---

## MQTT 分工

| 系統 | 功能 |
|---|---|
| ESP32 | Publish |
| Node-RED | Subscribe |
| Python | Subscribe |

---

# 16. Node-RED 功能

Node-RED 負責：

- MQTT 訂閱
- 即時 Dashboard
- BPM Gauge
- 即時折線圖
- SpO₂ 顯示
- 狀態顯示

---

# 17. 資料處理方式

採用：

- 即時更新
- 20 秒平均儲存

---

## 即時層（1秒）

ESP32：

每秒：

- 更新 TFT
- 發送 MQTT

---

## 分析層（20秒）

Python：

每 20 秒：

- 收集 BPM 資料
- 計算平均值
- 判斷 Status
- 寫入 MySQL

---

# 18. BPM 平均公式

\[
\bar{x}=\frac{x_1+x_2+x_3+\cdots+x_{20}}{20}
\]

---

# 19. 心率與血氧聯合判斷流程

## BPM 變化量公式

\[
\Delta BPM = BPM_{current} - BPM_{previous}
\]

---

## 狀態分級表

| 狀態 | 心率條件 (ΔBPM) | 血氧條件 (SpO₂) | 臨床意義 |
|---|---|---|---|
| NORMAL | \|ΔBPM\| < 10 且 BPM > 50 | ≥ 95% | 穩定，供氧正常 |
| WARNING | \|ΔBPM\| ≥ 10 且 < 50 | 91–94% | 需注意，可能有供氧不足或心律不整 |
| DANGER | BPM ≤ 50 或 \|ΔBPM\| ≥ 50 | ≤ 90% | 高風險，可能是心臟衰竭、呼吸障礙或急性事件 |

---

# 20. 判斷邏輯

---

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

# 21. Status 同步顯示

Python 判斷完成後：

Status 同步至：

- TFT
- LED
- Node-RED Dashboard
- MySQL
- Streamlit

---

# 22. MySQL 資料表

## heart_rate_data

| 欄位 | 用途 |
|---|---|
| timestamp | 時間 |
| bpm_avg | 20秒平均 BPM |
| spo2 | 血氧 |
| status | NORMAL / WARNING / DANGER |

---

# 23. Python 功能

Python 負責：

- smoothing
- 平均化
- ΔBPM 計算
- Status 判斷
- MySQL 寫入
- 長期分析
- 趨勢分析
- 統計分析

---

# 24. Streamlit 功能

Streamlit 負責：

- 視覺化分析
- 歷史趨勢
- 每日分析
- 每月分析

---

# 25. LINE 通知功能

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

# 26. Cloud 架構

使用 Railway 部署：

| 服務 | 用途 |
|---|---|
| MySQL | 資料庫 |
| Node-RED | Dashboard |
| Python | 分析服務 |
| Streamlit | 視覺化平台 |

---

# 27. 專題定位

PulseGuard IoT 屬於：

## IoT 智慧健康監控與資料分析平台

具備：

- 即時監測
- IoT傳輸
- 長期資料分析
- 視覺化 Dashboard
- 雲端部署
- 健康摘要通知
- 心率與血氧聯合判斷