const translations = {
    en: {
        nav_arch: "Architecture",
        nav_quick: "Quick Start",
        nav_tech: "Core Tech",
        nav_hw: "Hardware",
        nav_portals: "Portals",
        nav_lang: "繁中",
        hero_title: "PulseGuard IoT",
        hero_desc: "A professional-grade remote health monitoring solution integrating ESP32, Python, and Streamlit. Features dual-core real-time scheduling, EMA stream noise reduction, and automated report generation with active push notifications.",
        arch_title: "System Architecture",
        topology_title: "Topology & Data Flow",
        mermaid_graph: `graph TD
    subgraph Edge ["Edge Layer (ESP32)"]
        S[MAX30102 Sensor] -->|I2C| ESP[ESP32 Controller]
        ESP -->|MQTT| MQ((MQTT Broker))
    end

    subgraph Cloud ["Cloud Layer (Python)"]
        MQ -->|Subscribe| SP[Stream Processor]
        SP -->|Analyze| DB[(MongoDB Atlas)]
        SP -->|Trigger| NT[Line Notify API]
    end

    subgraph Analytics ["Analytics Layer (Streamlit)"]
        DB -->|Query| ST[Analytics Dashboard]
        ST -->|Visualize| USR((End User))
    end

    style Edge fill:#f9f,stroke:#333,stroke-width:2px
    style Cloud fill:#bbf,stroke:#333,stroke-width:2px
    style Analytics fill:#dfd,stroke:#333,stroke-width:2px`,
        quick_start_title: "Quick Start",
        step_1_title: "1. Firmware Deployment",
        step_1_desc: "Flash <code>firmware.ino</code> to ESP32. Configuration is handled via WiFiManager on first boot.",
        step_2_title: "2. Backend Setup",
        step_2_desc: "Run <code>backend/main.py</code> to start the MQTT stream processor and health logic engine.",
        step_3_title: "3. Visualization",
        step_3_desc: "Launch <code>analytics/app.py</code> for long-term health trend analysis and reporting.",
        tech_title: "Core Technology Stack",
        tech_firmware: "Firmware: Real-time Scheduling",
        tech_firmware_desc: "C++ / FreeRTOS dual-core task management. Core 1 handles 100Hz sensor sampling and local UI, while Core 0 manages WiFi/MQTT communication to ensure zero-jitter data capture.",
        tech_backend: "Backend: Stream Processing",
        tech_backend_desc: "Python-based engine with EMA (Exponential Moving Average) noise filtering. Implements 'Single Source of Truth' medical logic for consistent status evaluation across all platforms.",
        tech_analytics: "Analytics: Data Insights",
        tech_analytics_desc: "Streamlit dashboard with automated health report generation. Features Plotly-powered physiological trend charts and multi-environment (prod/test) data isolation.",
        hw_title: "Hardware Configuration",
        hw_esp32_title: "ESP32 DevKit V1",
        hw_esp32_desc: "Dual-core 240MHz, WiFi/BT integrated.",
        hw_sensor_title: "MAX30102 Sensor",
        hw_sensor_desc: "High-sensitivity pulse oximeter and heart-rate sensor.",
        hw_display_title: "ST7735 TFT",
        hw_display_desc: "1.44 inch color display for real-time local monitoring.",
        portal_title: "System Portals",
        portal_monitor: "Real-time Monitor",
        portal_monitor_desc: "Live stream of heart rate and SpO2 data with instant alerts. Low-latency monitoring via MQTT.js.",
        portal_analytics: "Health Analytics",
        portal_analytics_desc: "Long-term trend analysis and historical health report generation. Powered by Streamlit.",
        portal_btn_prod: "Launch Production",
        portal_btn_test: "Enter Test Environment",
        footer_rights: "© 2024 PulseGuard IoT Project. All rights reserved."
    },
    zh: {
        nav_arch: "系統架構",
        nav_quick: "快速上手",
        nav_tech: "核心技術",
        nav_hw: "硬體配置",
        nav_portals: "系統入口",
        nav_lang: "EN",
        hero_title: "PulseGuard IoT",
        hero_desc: "整合 ESP32、Python 與 Streamlit 的專業級遠端健康監控解決方案。具備雙核即時調度、EMA 串流降噪與自動化報告主動推播系統。",
        arch_title: "系統整體架構",
        topology_title: "系統拓撲與數據流",
        mermaid_graph: `graph TD
    subgraph Edge ["邊緣層 (ESP32)"]
        S[MAX30102 感測器] -->|I2C| ESP[ESP32 控制器]
        ESP -->|MQTT| MQ((MQTT Broker))
    end

    subgraph Cloud ["雲端處理層 (Python)"]
        MQ -->|訂閱| SP[串流處理器]
        SP -->|分析| DB[(MongoDB Atlas)]
        SP -->|觸發| NT[Line Notify API]
    end

    subgraph Analytics ["數據分析層 (Streamlit)"]
        DB -->|查詢| ST[數據分析儀表板]
        ST -->|視覺化| USR((最終用戶))
    end

    style Edge fill:#f9f,stroke:#333,stroke-width:2px
    style Cloud fill:#bbf,stroke:#333,stroke-width:2px
    style Analytics fill:#dfd,stroke:#333,stroke-width:2px`,
        quick_start_title: "快速上手指南",
        step_1_title: "1. 韌體部署",
        step_1_desc: "將 <code>firmware.ino</code> 燒錄至 ESP32。首次啟動可透過 WiFiManager 進行簡易配網。",
        step_2_title: "2. 後端啟動",
        step_2_desc: "執行 <code>backend/main.py</code> 啟動 MQTT 串流處理器與健康狀態判斷邏輯引擎。",
        step_3_title: "3. 視覺化分析",
        step_3_desc: "啟動 <code>analytics/app.py</code> 查看中長期健康趨勢分析與自動化醫療報告。",
        tech_title: "核心技術深度解析",
        tech_firmware: "嵌入式韌體：即時任務調度",
        tech_firmware_desc: "基於 C++ / FreeRTOS 的雙核架構。Core 1 負責 100Hz 高頻採樣與 UI 刷新，Core 0 專職處理網路通訊，確保生理訊號捕捉零抖動。",
        tech_backend: "後端引擎：串流處理與降噪",
        tech_backend_desc: "整合 EMA 指數移動平均濾波技術，並導入「單一事實來源」診斷邏輯，確保所有端點（Web/App/LINE）的健康判定結果完全一致。",
        tech_analytics: "分析平台：數據洞察與報告",
        tech_analytics_desc: "基於 Streamlit 的數據中心，支援自動化報告產出、Plotly 互動式圖表，以及完善的正式/測試環境數據隔離。",
        hw_title: "硬體腳位配置清單",
        hw_esp32_title: "ESP32 DevKit V1",
        hw_esp32_desc: "雙核心 240MHz，整合 WiFi 與藍牙通訊功能。",
        hw_sensor_title: "MAX30102 感測器",
        hw_sensor_desc: "高靈敏度心率與血氧飽和度感測模組。",
        hw_display_title: "ST7735 TFT 螢幕",
        hw_display_desc: "1.44 吋彩色螢幕，用於顯示本地端即時生理數據監控。",
        portal_title: "系統快速入口",
        portal_monitor: "即時監控儀表板",
        portal_monitor_desc: "透過 MQTT.js 與 WebSocket 技術，提供秒級延遲的心率與血氧監控，支援即時異常告警。",
        portal_analytics: "趨勢分析中心",
        portal_analytics_desc: "利用 Streamlit 深入分析歷史 EMA 趨勢，並產出臨床級 KPI 健康分析報告。",
        portal_btn_prod: "啟動正式環境",
        portal_btn_test: "進入測試環境",
        footer_rights: "© 2024 PulseGuard IoT Project. 保留所有權利。"
    }
};
