def get_translations(lang_code):
    """
    提供多語系支援的字典與處理函式
    """
    translations = {
        'en': {
            'page_title': 'PulseGuard Analytics Dashboard',
            'title': 'PulseGuard | Long-term Trend Analytics Dashboard',
            'sidebar_filters': 'Filters',
            'date_range': 'Date Range',
            'status_filter': 'Status Filter',
            'test_mode_warning': 'Currently in Test Mode. Viewing simulated test data.',
            'expander_title': '🔍 View Status Criteria & Technical Descriptions',
            'expander_left_title': '🩺 Health Status Criteria',
            'expander_right_title': '⚙️ Technical Algorithm Descriptions',
            'kpi_total': 'Total Samples',
            'kpi_danger': 'Danger Events',
            'kpi_warning': 'Warning Events',
            'tab_trends': '📈 Physiological Trends',
            'tab_stats': '📊 Anomaly Count Statistics',
            'tab_logs': '📋 Abnormal Logs & Export',
            'bpm_trend_title': 'Heart Rate Trend (Daily Range & Avg)',
            'spo2_trend_title': 'Oxygen Saturation Trend (Daily Min SpO₂)',
            'status_dist_title': 'Overall Health Status Distribution',
            'weekly_stats_title': 'Weekly Abnormal Event Trends',
            'bpm_range': 'BPM Range',
            'avg_bpm_trace': 'Avg BPM',
            'min_spo2_trace': 'Min SpO₂',
            'event_count': 'Event Count',
            'tt_week': 'Week',
            'tt_status': 'Status',
            'tt_count': 'Event Count',
            'tt_date': 'Date',
            'tt_avg_bpm': 'Avg BPM',
            'tt_min_spo2': 'Min SpO₂',
            'tt_percent': 'Percent',
            'download_csv': 'Download Filtered Data as CSV',
            'week_format': '%G-W%V',
            'status_map': {"NORMAL": "NORMAL", "WARNING": "WARNING", "DANGER": "DANGER"},
            'col_no': '#',
            'col_time': 'Timestamp',
            'col_status': 'Status',
            'col_desc': 'Description',
            'col_avg_bpm': 'Avg HR (BPM)',
            'col_ema_bpm': 'EMA HR (BPM)',
            'col_spo2': 'SpO₂ (%)',
            'help_status_display': """
- 🚨 **DANGER**: Instant SpO₂ ≤ 90%, Heart Rate (EMA) ≥ 140 or ≤ 50, or Heart Rate Variation (|ΔBPM|) ≥ 50.
- ⚠️ **WARNING**: Metrics outside ideal ranges (e.g., Low SpO₂, Heart Rate Fluctuation), but not meeting Danger criteria.
- 💡 **Note**: This dashboard utilizes a 'Real-Time & Time-Series Dual-Track Mechanism,' focusing on dynamic anomaly alerts and risk root-cause tracking. For standard physiological baseline data, please proceed to the 'Physiological Trends' tab.""",
            'help_status_tooltip': """### ℹ️ Dual-Track Decision
- **SpO2 (Real-Time Track)**: Blood oxygen saturation is critical to life safety. The system does not perform time-averaging; as long as a single real-time data point below 90% is received, it will trigger an alert with the highest priority.
- **Heart Rate (Time-Series Track)**: Heart rate is highly prone to interference from body movements. Through Exponential Moving Average (EMA), time-series filtering is applied to remove noise spikes, ensuring that it reflects true health trends rather than hardware false alarms.""",
            'help_avg_bpm': "**Avg HR (MA)**: Calculates the moving average of the last 15 signal data points to smooth out real-time noise and reflect a stable heart rate trend.",
            'help_ema_bpm': "**EMA HR (Exponential Moving Average)**: Utilizes a \"Cascaded Filter Architecture,\" processing the 15-second moving average through a second layer of EMA time-series computation. Featuring dual-denoising capabilities, it maximally suppresses false alarms caused by single-point noise spikes.",
            'help_spo2': "**SpO2 (%)**: Utilizes real-time data for ultra-fast analysis, ensuring early detection of acute hypoxia events; however, data is susceptible to interference from finger movement.",
            'missing_did': "Missing device ID. Unable to load production environment data.",
            # --- Tab 1 & Hardcoded strings in app.py translations ---
            'tab1_guide_title': '📊 Trend Chart Reading Guide',
            'tab1_guide_content': """
- **Light Blue Area**: Represents the daily fluctuation range of heart rate (from maximum to minimum).
- **Dark Blue Solid Line**: Represents the daily average heart rate.
- **Bright Green Solid Line**: Represents the daily "minimum" blood oxygen record (used to monitor extreme hypoxia).
- **Red Dashed Line**: The system's default danger threshold warning line (Heart Rate 140/50, SpO₂ 90%).
""",
            'db_connection_error_mock': "Database connection failed, showing mock data for reference.",
            'no_data_found': "No data found for the selected range.",
            'sample_data_info': "Displaying feature sample data:",
            'no_trend_data': "No valid physiological data available for trends under current filters.",
            'no_weekly_abnormal_data': "No abnormal data for weekly analysis.",
            'no_abnormal_events': "No abnormal events recorded.",
            'root_cause_title': 'Anomaly Classification Statistics',
            'hourly_dist_title': 'Hourly Anomaly Distribution',
            'tt_reason': 'Reason',
            'tt_hour': 'Hour',
            'diag': {
                'crit_low_spo2': "Critically Low SpO₂",
                'low_spo2': "Low SpO₂",
                'crit_low_hr': "Severe Bradycardia",
                'low_hr': "Mild Bradycardia",
                'high_hr': "Mild Tachycardia",
                'crit_high_hr': "Severe Tachycardia",
                'arrhythmia': "Sudden Heart Rate Variation",
                'hr_fluctuation': "Heart Rate Fluctuation"
            }
        },
        'zh': {
            'page_title': 'PulseGuard 分析儀表板',
            'title': 'PulseGuard | 中長期趨勢分析儀表板',
            'sidebar_filters': '篩選條件',
            'date_range': '日期範圍',
            'status_filter': '狀態過濾',
            'test_mode_warning': '目前處於測試模式，檢視的數據為模擬測試資料。',
            'expander_title': '🔍 檢視狀態判定標準與技術說明',
            'expander_left_title': '🩺 狀態判定標準',
            'expander_right_title': '⚙️ 核心演算法說明',
            'kpi_total': '總樣本數',
            'kpi_danger': '危險次數',
            'kpi_warning': '警告次數',
            'tab_trends': '📈 生理趨勢圖',
            'tab_stats': '📊 異常次數統計',
            'tab_logs': '📋 異常日誌與匯出',
            'bpm_trend_title': '心率趨勢（日範圍與平均）',
            'spo2_trend_title': '血氧趨勢（每日最低 SpO₂）',
            'status_dist_title': '整體健康狀態佔比',
            'weekly_stats_title': '每週異常事件趨勢',
            'bpm_range': '心率範圍',
            'avg_bpm_trace': '平均心率',
            'min_spo2_trace': '最低血氧',
            'event_count': '事件次數',
            'tt_week': '週別',
            'tt_status': '警示級別',
            'tt_count': '事件次數',
            'tt_date': '日期',
            'tt_avg_bpm': '平均心率',
            'tt_min_spo2': '最低血氧',
            'tt_percent': '比例',
            'download_csv': '下載篩選後的資料為 CSV',
            'week_format': '%G-週%V',
            'status_map': {"NORMAL": "正常", "WARNING": "警告", "DANGER": "危險"},
            'col_no': '序號',
            'col_time': '時間戳記',
            'col_status': '狀態',
            'col_desc': '異常原因',
            'col_avg_bpm': '平均心率 (BPM)',
            'col_ema_bpm': 'EMA 心率 (BPM)',
            'col_spo2': '血氧飽和度 (%)',
            'help_status_display': """
- 🚨 **DANGER (危險)**：即時血氧極低 (SpO₂ ≤ 90%)、心率過高/過低 (EMA ≥ 140 或 ≤ 50)或心率突變 (|ΔBPM| ≥ 50)。\n
- ⚠️ **WARNING (警告)**：生理指標超出理想範圍（例如血氧微降、心率偏高/偏低、或心率微幅波動），但未達危險標準。\n
- 💡 **說明**：本面板採用「即時-時序雙軌判定」，專注於動態異常示警與風險成因追蹤。常態生理數據請至「生理趨勢」頁籤查閱。""",
            'help_status_tooltip': """### ℹ️ 雙軌判定機制
- **血氧（即時軌）**：血液含氧量攸關生命安全，系統不對其進行時間平均，只要收到一筆低於 90% 的即時數據，便會以最高優先級觸發警報。
- **心率（時序軌）**：心率極易受肢體動作干擾，透過指數加權移動平均(EMA)進行時序濾波，去除毛刺雜訊，確保呈現的是真正的健康趨勢而非硬體誤報。""",
            'help_avg_bpm': "**平均心率 (MA)**：計算最近 15 筆訊號均值，用以平滑即時雜訊，呈現穩定心流趨勢。",
            'help_ema_bpm': " **EMA 心率 (指數移動平均)**：採用「二階串聯濾波架構」，將 15 秒平均值再次進行指數加權（EMA）時序運算，具備雙重去噪能力，可極致壓制單點雜訊引起的誤報。",
            'help_spo2': "**血氧飽和度 (%)**：採用即時數據進行極速分析，確保能第一時間捕捉急性缺氧事件，唯數據較易受手指晃動影響。",
            'missing_did': "缺少裝置編號，無法載入正式環境資料。",
            # --- Tab 1 & App.py 寫死字串翻譯 ---
            'tab1_guide_title': '📊 趨勢圖閱讀指南',
            'tab1_guide_content': """
- **淺藍色區塊**：代表當日心率最高到最低的波動範圍。
- **深藍色實線**：代表當日的平均心率。
- **亮綠色實線**：代表當日「最低」的血氧紀錄（用於關注極端缺氧狀況）。
- **紅色虛線**：系統預設的危險警示線（心率 140/50，血氧 90%）。
""",
            'db_connection_error_mock': "無法連線至資料庫，顯示模擬數據供參考。",
            'no_data_found': "所選範圍內查無數據。",
            'sample_data_info': "展示功能範例數據：",
            'no_trend_data': "所選篩選條件下無有效生理數據可供繪製趨勢圖。",
            'no_weekly_abnormal_data': "查無異常數據可供週統計分析。",
            'no_abnormal_events': "此期間無任何異常事件。",
            'root_cause_title': '異常事件類別統計',
            'hourly_dist_title': '24小時異常時段統計',
            'tt_reason': '異常原因',
            'tt_hour': '小時',
            'diag': {
                'crit_low_spo2': "血氧極低",
                'low_spo2': "血氧偏低",
                'crit_low_hr': "心率過低",
                'low_hr': "心率偏慢",
                'high_hr': "心率偏高",
                'crit_high_hr': "心率過高",
                'arrhythmia': "心率突變異常",
                'hr_fluctuation': "心率微幅波動"
            }
        }
    }
    lang = "zh" if lang_code == "zh" else "en"
    return translations[lang], lang
