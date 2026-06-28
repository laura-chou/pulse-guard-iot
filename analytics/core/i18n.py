def get_translations(lang_code):
    """
    提供多語系支援的字典與處理函式
    """
    translations = {
        'en': {
            'page_title': 'PulseGuard Analytics',
            'title': 'PulseGuard | Long-term Trend Analytics Dashboard',
            'sidebar_filters': 'Filters',
            'date_range': 'Date Range',
            'status_filter': 'Status Filter',
            'test_mode_warning': 'Currently in Test Mode. Viewing simulated test data.',
            'expander_title': '🔍 View Status Criteria & Technical Descriptions',
            'expander_left_title': '🩺 Health Status Criteria',
            'expander_right_title': '🔬 Technical Algorithm Descriptions',
            'kpi_total': 'Total Samples',
            'kpi_danger': 'Danger Events',
            'kpi_warning': 'Warning Events',
            'tab_trends': '📈 Physiological Trends',
            'tab_stats': '📊 Status Statistics',
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
            'col_avg_bpm': 'Avg BPM',
            'col_ema_bpm': 'EMA BPM',
            'col_spo2': 'SpO₂ (%)',
            'help_status_display': """🚨 **DANGER**: Instant SpO₂ ≤ 90%, Heart Rate (EMA) ≥ 140 or ≤ 50, or Heart Rate Variation (|ΔBPM|) ≥ 50.
⚠️ **WARNING**: Metrics outside ideal ranges (e.g., Low SpO₂, Heart Rate Fluctuation), but not meeting Danger criteria.

💡 Note: This panel uses a **"Real-time & Time-series Dual-track Logic"** to capture acute crises and symptom codes. Normal data can be viewed in the Trends and Statistics tabs.""",
            'help_status_tooltip': """### 🔬 Tech Specs: What is Dual-track Logic?

* **Oxygen (Real-time Track)**: Blood oxygen levels are critical. The system does not time-average SpO₂; a single raw reading ≤ 90% triggers a high-priority alert immediately.
* **Heart Rate (Time-series Track)**: BPM is sensitive to motion artifacts. The backend uses Exponential Moving Average (EMA) filtering to remove noise and ensure true health trends are captured without false positives.""",
            'help_avg_bpm': "15s Moving Average BPM: Mean of the last 15 signals to smooth out instant noise and show stable heart flow.",
            'help_ema_bpm': "Exponential Moving Average (EMA): Uses a time-series algorithm to dynamically weight current and historical data, suppressing outliers.",
            'help_spo2': "Instant Oxygen Saturation (%): Uses raw data for ultra-fast analysis to catch acute hypoxia events, though sensitive to motion.",
            'missing_did': "Missing device ID. Unable to load production environment data.",
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
            'page_title': 'PulseGuard 分析',
            'title': 'PulseGuard | 中長期趨勢分析儀表板',
            'sidebar_filters': '篩選條件',
            'date_range': '日期範圍',
            'status_filter': '狀態過濾',
            'test_mode_warning': '目前處於測試模式，檢視的數據為模擬測試資料。',
            'expander_title': '🔍 檢視狀態判定標準與技術說明',
            'expander_left_title': '🩺 狀態判定標準',
            'expander_right_title': '🔬 核心演算法科普',
            'kpi_total': '總樣本數',
            'kpi_danger': '危險次數',
            'kpi_warning': '警告次數',
            'tab_trends': '📈 生理趨勢圖',
            'tab_stats': '📊 狀態統計',
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
            'col_avg_bpm': '平均心率',
            'col_ema_bpm': 'EMA心率',
            'col_spo2': '血氧飽和度 (%)',
            'help_status_display': """🚨 **DANGER (危險)**：即時血氧極低 (SpO₂ ≤ 90%)、心率過高/過低 (EMA ≥ 140 或 ≤ 50)，或心率突變 (|ΔBPM| ≥ 50)。
⚠️ **WARNING (警告)**：生理指標超出理想範圍（例如血氧微降、心率偏高/偏低、或心率微幅波動），但未達危險標準。

💡 說明：本面板採用**「即時-時序雙軌判定架構」**，專注於捕捉急性危機與病徵代碼標註。常態生理數據請至「趨勢」與「統計」頁籤查閱。""",
            'help_status_tooltip': """### 🔬 技術原理小科普：什麼是雙軌判定？

* **血氧（即時軌）**：血液含氧量攸關生命安全，系統不對其進行時間平均，只要收到一筆低於 90% 的 Raw 即時數據，便會以最高優先級觸發警報，與時間賽跑。
* **心率（時序軌）**：心率極易受肢體動作干擾，後端透過指數加權移動平均（EMA）進行時序濾波，去除毛刺雜訊，確保呈現的是真正的健康趨勢，而非硬體誤報。""",
            'help_avg_bpm': "15秒移動平均心率 (Moving Average)：計算最近 15 筆訊號均值，用以平滑即時雜訊，呈現穩定心流趨勢。",
            'help_ema_bpm': "指數移動平均心率 (EMA)：導入時序濾波演算法，動態加權當前與歷史數據，有效抑制單點雜訊引起的誤報。",
            'help_spo2': "即時血氧飽和度百分比：採用即時數據進行極速分析，確保能第一時間捕捉急性缺氧事件，唯數據較易受手指晃動影響。",
            'missing_did': "缺少裝置編號，無法載入正式環境資料。",
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
