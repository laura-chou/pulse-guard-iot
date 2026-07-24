const locales = {
    en: {
        nav: {
            hero: "Home",
            architecture: "Architecture",
            features: "Core Tech",
            hardware: "Hardware",
            portals: "Portals",
            lang: "繁中"
        },
        hero: {
            title: "PulseGuard IoT",
            subtitle: "A professional-grade remote health monitoring solution integrating ESP32, Python, and Streamlit. Features dual-core real-time scheduling, EMA stream noise reduction, and automated report generation with active push notifications."
        },
        architecture: {
            title: "System Architecture"
        },
        features: {
            title: "Technical Deep Dive",
            firmware: {
                title: "Firmware: Dual-Core Real-time Scheduling & Power Optimization",
                subtitle: "Based on the ESP32 and FreeRTOS real-time operating system, the firmware adopts a dual-core thread isolation architecture to ensure physiological signal capture is free from network communication and peripheral latency.",
                tasks_title: "Dual-Core Task Scheduling:",
                tasks_desc: "Core 1 is dedicated to high-frequency physiological signal sampling, dual filtering (DC/MA), dynamic TFT screen refresh, and button detection. Core 0 is independently responsible for Wi-Fi maintenance and TLS/SSL encrypted communication, utilizing thread-safe queues for inter-core data transmission.",
                alarm_title: "Intelligent Measurement & Alarm Logic:",
                alarm_desc: "Features a built-in 60-second measurement cycle with the first 5 seconds as the signal stabilization period. SpO2 is calculated using an empirical formula based on the R/IR ratio. The system implements a \"Three-Level Dynamic Alarm\" (Danger/Warning/Normal) based on SpO2 and heart rate, using non-blocking time-difference control for the buzzer throughout the system to prevent traditional delay-induced sampling stalls.",
                power_title: "Power Saving & Robustness:",
                power_desc: "Includes \"Finger-off Detection\" that resets the timer when no signal is detected. If the sensor remains idle for too long, the system automatically enters Deep Sleep to conserve power, supporting wake-up via button interrupt. The button also supports long-press reset, clearing system queues and sending a reset notification to the cloud via MQTT."
            },
            backend: {
                title: "Backend: Stream Processing & Intelligent Analysis",
                subtitle: "The Python backend serves as the system brain, responsible for receiving MQTT physiological data streams, performing real-time noise reduction, measurement lifecycle management, and multi-dimensional health assessment:",
                cleaning_title: "Data Cleaning & Source Isolation:",
                cleaning_desc: "Automatically distinguishes and labels Production and Test data via MQTT topics, filtering out invalid physiological values.",
                ema_title: "EMA Noise Reduction & Analytics:",
                ema_desc: "Combines MA and EMA for dual smoothing, maintaining a 15-point time window to capture long-term physiological trends.",
                evaluation_title: "Dual-Track Health Evaluation:",
                evaluation_desc: "Integrates single-point thresholds and interval trends to determine health risk levels and dynamically generate medical advice.",
                automated_title: "Automated Report & Template Injection:",
                automated_desc: "Extracts valid metrics to compute full-session averages, utilizing dictionary-mapping techniques to precisely inject data into a JSON template.",
                push_title: "Active Push & Time Localization:",
                push_desc: "Calibrates raw UTC timestamps to local Taipei time, and actively pushes structured Flex Message reports via the LINE Messaging API upon session completion.",
                persistence_title: "Intelligent DB Persistence Strategy:",
                persistence_desc: "Executes MongoDB data writes based on event-driven rules and timers, featuring built-in automatic disconnection fault tolerance and retry mechanisms.",
                session_title: "Dynamic Session Management:",
                session_desc: "Dynamically generates a unique UUID upon initialization, resetting all system states and memory caches during a COMPLETED end or hardware RESET."
            },
            analytics: {
                title: "Analytics: Data Visualization & Insights",
                subtitle: "The Streamlit-based dashboard provides a powerful interface for reviewing historical trends and system performance:",
                i18n_title: "Multi-Environment & i18n Support:",
                i18n_desc: "Supports dynamic environment switching (?env=test) and full i18n support for Traditional Chinese and English via URL parameters.",
                db_title: "High-Availability DB Integration:",
                db_desc: "Features built-in automatic degradation; redirects to Mock Data if MongoDB is unreachable, ensuring UI availability.",
                aggregation_title: "Multi-Dimensional Aggregation:",
                aggregation_desc: "Implements dual logic: daily summaries (capturing heart rate range, average, and minimum SpO2) for long-term trends, and hourly deduplication prioritizing critical events (DANGER > WARNING > NORMAL).",
                charts_title: "Interactive Time-Series Charts:",
                charts_desc: "Leverages Plotly for multi-axis physiological trend charts, including 90% SpO2 danger baselines. Also features vertical layout charts for Anomaly Classification Statistics and Hourly Anomaly Distribution to analyze risk factors.",
                log_title: "Advanced Log Rendering:",
                log_desc: "Utilizes st_aggrid with dynamic conditional rendering via JavaScript to highlight high-risk events (DANGER/WARNING)."
            },
            line_report_caption: "Actual LINE Flex Message measurement report preview"
        },
        hardware: {
            title: "Hardware Configuration",
            tabs: {
                tft: "TFT ST7735 Configuration",
                oled: "OLED SSD1306 Configuration"
            },
            tft: {
                title: "TFT Display",
                pin_header: "TFT Pin",
                esp_header: "ESP32 Pin"
            },
            oled: {
                title: "OLED Display",
                pin_header: "OLED Pin",
                esp_header: "ESP32 Pin"
            },
            segment: {
                title: "7-Segment Display",
                pin_header: "Segment Pin",
                esp_header: "ESP32 Pin"
            },
            sensor: {
                title: "MAX30102 Sensor",
                pin_header: "Sensor Pin",
                esp_header: "ESP32 Pin"
            },
            button: {
                title: "Control Button",
                pin_header: "Button Pin",
                esp_header: "ESP32 Pin",
                pin_a: "Pin A",
                pin_b: "Pin B"
            },
            buzzer: {
                title: "Buzzer",
                pin_header: "Buzzer Pin",
                esp_header: "ESP32 Pin",
                positive: "+ (Positive)",
                negative: "- (Negative)"
            }
        },
        portals: {
            title: "System Portals",
            realtime: {
                title: "Real-time Dashboard",
                desc: "Experience low-latency physiological data monitoring via WebSocket and MQTT.js.",
                prod: "Launch Production",
                test: "Enter Test Environment"
            },
            analytics: {
                title: "Analytics Dashboard",
                desc: "Deep dive into historical EMA trends and clinical KPI reports powered by Streamlit.",
                prod: "Launch Production",
                test: "Enter Test Environment"
            }
        },
        footer: {
            copy: "&copy; 2026 PulseGuard IoT. All rights reserved."
        }
    },
    zh: {
        nav: {
            hero: "首頁",
            architecture: "系統架構",
            features: "核心技術",
            hardware: "硬體配置",
            portals: "系統入口",
            lang: "EN"
        },
        hero: {
            title: "PulseGuard IoT",
            subtitle: "整合 ESP32、Python 與 Streamlit 的專業級遠端健康監控解決方案。具備雙核即時調度、EMA 串流降噪與自動化報告主動推播系統。"
        },
        architecture: {
            title: "系統整體架構"
        },
        features: {
            title: "核心技術深度解析",
            firmware: {
                title: "韌體端：雙核即時調度與功耗優化",
                subtitle: "基於 ESP32 與 FreeRTOS 即時作業系統，採行雙核執行緒隔離架構，確保生理訊號捕捉不受網路通訊與周邊延遲干擾：",
                tasks_title: "雙核任務調度：",
                tasks_desc: "Core 1 專職執行高頻生理訊號採樣、雙重濾波（DC/MA）、TFT 螢幕動態刷新與按鍵偵測；Core 0 則獨立負責 Wi-Fi 連線維護與 TLS/SSL 加密通訊，並透過執行緒安全的佇列（Queue）進行雙核間的數據傳輸。",
                alarm_title: "智慧量測與警報邏輯：",
                alarm_desc: "系統內建 60 秒量測機制，前 5 秒為信號穩定收斂期。血氧採紅光與紅外光比值之經驗公式計算。系統依據血氧與心率指標實施「三級動態警報」（危險/警告/正常），並全機採用非阻塞式時間差控制蜂鳴器，避免傳統延遲卡死採樣。",
                power_title: "省電與防呆機制：",
                power_desc: "具備「離手偵測」功能，當感測器無訊號時重置計時；若維持離手狀態過久，系統自動進入深層睡眠（Deep Sleep）以節省功耗，並支援按鍵中斷喚醒。此外，按鍵亦支援長按重置功能，同步清空系統佇列並對雲端 MQTT 發送重置通知。"
            },
            backend: {
                title: "後端：串流處理與智慧分析",
                subtitle: "Python 後端作為系統大腦，負責接收 MQTT 生理數據串流，進行即時降噪、量測生命週期管理與多維度健康狀態判定：",
                cleaning_title: "資料清洗與來源隔離：",
                cleaning_desc: "透過 MQTT Topic 自動區分並標記正式（Production）與測試（Test）數據，過濾不合法數值。",
                ema_title: "時序指標運算與 EMA 降噪：",
                ema_desc: "結合 MA 與 EMA 進行雙重平滑，計算 15 筆時序視窗平均值以捕捉長期趨勢。",
                evaluation_title: "雙軌制多維度健康評估：",
                evaluation_desc: "結合單點閾值與區間趨勢判定健康層級（如正常/注意/危險），動態產出客製化醫囑。",
                automated_title: "自動化報告生成與樣板注入：",
                automated_desc: "提取有效心率與血氧流計算全階段平均數值，並利用字典尋址技術將結果精準注入 JSON 樣板。",
                push_title: "主動式遠端告警與時區校正：",
                push_desc: "校正 UTC 為台北時間。量測結束時透過 LINE Messaging API 將結構化報告圖卡主動推播至手機。",
                persistence_title: "智慧型資料庫持久化策略：",
                persistence_desc: "採事件驅動結合定時心跳策略執行 MongoDB 寫入，並具備斷線自動容錯與重試機制。",
                session_title: "動態生命週期（Session）管理：",
                session_desc: "動態生成 UUID 唯一識別碼，並於 COMPLETED 正常結束或 RESET 異常中斷時精確重置狀態與快取。"
            },
            analytics: {
                title: "分析端：數據視覺化與洞察",
                subtitle: "基於 Streamlit 的分析看板提供了強大的介面，用於回溯歷史趨勢與系統表現：",
                i18n_title: "多環境與雙語系切換：",
                i18n_desc: "支援 URL 動態參數解析，可透過 ?env=test 無縫切換資料庫來源以隔離測試數據；同步整合 i18n 模組，支援經由 ?lang= 參數動態切換介面。",
                db_title: "高可用資料庫整合與容錯：",
                db_desc: "透過 pymongo 連接 MongoDB 叢集。內建自動降級與容錯機制，若遇資料庫連線失敗，系統將導向「模擬測試數據（Mock Data）」，確保前端 UI 高可用性。",
                aggregation_title: "多維度資料預處理與聚合：",
                aggregation_desc: "設計雙重聚合邏輯：按日統計心率波動範圍、平均值與血氧最低值走勢，用以呈現長期生理趨勢；並按小時去重，依嚴重程度優先級（DANGER > WARNING > NORMAL）保留關鍵事件。",
                charts_title: "時序指標監控與雙軸圖表：",
                charts_desc: "整合 Plotly 繪製多軸生理趨勢圖，將心率區間以填充色呈現，並標記 90% 血氧危險紅線；另提供「異常事件類別統計」與「24小時異常時段統計」橫向條狀圖，直觀分析健康風險。",
                log_title: "進階異常日誌檢索與渲染：",
                log_desc: "導入 st_aggrid 元件。透過注入 JavaScript 實作動態條件渲染，根據健康狀態（DANGER / WARNING）即時改變背景顏色。"
            },
            line_report_caption: "LINE Flex Message 量測報告實際推送畫面"
        },
        hardware: {
            title: "硬體腳位配置",
            tabs: {
                tft: "TFT ST7735 配置",
                oled: "OLED SSD1306 配置"
            },
            tft: {
                title: "TFT 腳位",
                pin_header: "TFT 腳位",
                esp_header: "ESP32 腳位"
            },
            oled: {
                title: "OLED 腳位",
                pin_header: "OLED 腳位",
                esp_header: "ESP32 腳位"
            },
            segment: {
                title: "七段顯示器腳位",
                pin_header: "顯示器腳位",
                esp_header: "ESP32 腳位"
            },
            sensor: {
                title: "MAX30102 腳位",
                pin_header: "MAX30102 腳位",
                esp_header: "ESP32 腳位"
            },
            button: {
                title: "BUTTON 腳位",
                pin_header: "BUTTON 腳位",
                esp_header: "ESP32 腳位",
                pin_a: "Pin A",
                pin_b: "Pin B"
            },
            buzzer: {
                title: "BUZZER 腳位",
                pin_header: "BUZZER 腳位",
                esp_header: "ESP32 腳位",
                positive: "+ (Positive)",
                negative: "- (Negative)"
            }
        },
        portals: {
            title: "系統入口",
            realtime: {
                title: "即時監控儀表板",
                desc: "透過 MQTT.js 與 WebSocket 技術，體驗秒級延遲的生理數據即時監控。",
                prod: "啟動正式環境",
                test: "進入測試環境"
            },
            analytics: {
                title: "數據分析儀表板",
                desc: "利用 Streamlit 深入分析歷史 EMA 趨勢與臨床 KPI 健康報告。",
                prod: "啟動正式環境",
                test: "進入測試環境"
            }
        },
        footer: {
            copy: "&copy; 2026 PulseGuard. 版權所有"
        }
    }
};
