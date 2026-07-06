/**
 * i18n.js - Modular Internationalization for PulseGuard
 */

const translations = {
    en: {
        'status.normal': 'NORMAL',
        'status.warning': 'WARNING',
        'status.danger': 'DANGER',
        'status.waiting': 'WAITING',
        'error.no_device': '❌ Error: No Device ID specified',
        'error.config': '⚠️ Config Error',
        'ui.last_update': 'Last Update',
        'ui.conn_connecting': 'Connecting...',
        'ui.conn_connected': '🟢 Connected',
        'ui.conn_error': '🔴 Connection Error',
        'ui.conn_lost': '🔴 Connection Lost',
        'chart.hr_trend': 'Heart Rate Trend',
        'chart.spo2_trend': 'SpO₂ Trend',

        // Testing Tool UI
        'test.title': 'MQTT Testing Tool',
        'test.manual_send': 'MANUAL SEND',
        'test.device_id': 'Device ID',
        'test.quick_presets': 'Quick Presets',
        'test.preset_placeholder': '-- Select a preset... --',
        'test.preset_normal': 'Normal (70 BPM, 98% SpO₂)',
        'test.preset_low_spo2': 'Low SpO₂ (75 BPM, 92% SpO₂)',
        'test.preset_high_bpm': 'High BPM (110 BPM, 97% SpO₂)',
        'test.preset_severe_low_spo2': 'Severe Low SpO₂ (80 BPM, 85% SpO₂)',
        'test.preset_acute_tachycardia': 'Acute Tachycardia (140 BPM, 96% SpO₂)',
        'test.send_single': 'Send Single',
        'test.start_auto': 'Start Auto (1s)',
        'test.stop_auto': 'Stop Auto',
        'test.duration': 'Duration (sec)',
        'test.send_completed': 'Send Completed',
        'test.send_reset': 'Send Reset',
        'test.scenarios': 'TEST SCENARIOS',
        'test.select_scenario_label': 'Select Scenario',
        'test.scenario_placeholder': '-- Select a scenario... --',
        'test.scenario_a': 'Scenario A: Cold Start Validation',
        'test.scenario_b': 'Scenario B: Anomaly Filtering',
        'test.scenario_c': 'Scenario C: Zero-Latency DANGER Write',
        'test.scenario_d': 'Scenario D: ΔBPM Spike Detection',
        'test.scenario_e': 'Scenario E: Timer Throttling',
        'test.scenario_f': 'Scenario F: Lazy Initialization (Warm-up)',
        'test.select_scenario_help': 'Please select a scenario to see details.',
        'test.execute_scenario': 'Execute Scenario',
        'test.message_log': 'MESSAGE LOG',
        'test.open_monitor': 'Open Monitor',
        'test.clear_log': 'Clear Log',

        // Testing Tool Messages
        'test.scenario_desc.A': '<ul><li>Action: Send a single valid health data payload (72 BPM, 98% SpO₂).</li><li>Expected: System immediately creates a new Session and triggers an insert_one write (bypassing the 20s cooldown).</li></ul>',
        'test.scenario_desc.B': '<ul><li>Action: Send 3 normal payloads, followed by continuous extreme invalid values (999 BPM, 40% SpO₂).</li><li>Expected: System discards the anomalies. No database writes are triggered, and moving average calculations remain unpolluted.</li></ul>',
        'test.scenario_desc.C': '<ul><li>Action: Send 15 normal payloads, followed by a sudden low SpO₂ drop (88% SpO₂).</li><li>Expected: State machine flags as DANGER. Bypassing throttling constraints, the system immediately writes the critical record to the database.</li></ul>',
        'test.scenario_desc.D': '<ul><li>Action: Send 15 stable heart rate payloads (70 BPM), followed by a sudden spike (125 BPM, simulating ΔBPM = 55).</li><li>Expected: System detects the acute ΔBPM change, triggering an analysis_status update and an immediate database write.</li></ul>',
        'test.scenario_desc.E': '<ul><li>Action: Send normal payloads every 2 seconds for a duration exceeding 20 seconds.</li><li>Expected: Throttling engages. The database only records the "1st-second" and "20th-second" data; intermediate payloads only update the memory window.</li></ul>',
        'test.scenario_desc.F': '<ul><li>Action: Keep the system idle for 5 seconds post-connection, sending the first valid payload at the 6th second.</li><li>Expected: Zero Session/DB creation during the first 5 seconds. The Session\'s creation timestamp must perfectly align with the first valid payload at second 6.</li></ul>'
    },
    zh: {
        'status.normal': '正常',
        'status.warning': '警告',
        'status.danger': '危險',
        'status.waiting': '待機中',
        'error.no_device': '❌ 錯誤：未指定裝置 ID',
        'error.config': '⚠️ 設定錯誤',
        'ui.last_update': '最後更新',
        'ui.conn_connecting': '連線中...',
        'ui.conn_connected': '🟢 已連線',
        'ui.conn_error': '🔴 連線錯誤',
        'ui.conn_lost': '🔴 連線中斷',
        'chart.hr_trend': '心率趨勢',
        'chart.spo2_trend': '血氧趨勢',

        // Testing Tool UI
        'test.title': 'MQTT 測試工具',
        'test.manual_send': '手動發送',
        'test.device_id': '裝置 ID',
        'test.quick_presets': '快速預設',
        'test.preset_placeholder': '-- 請選擇預設值... --',
        'test.preset_normal': '正常 (70 BPM, 98% SpO₂)',
        'test.preset_low_spo2': '低血氧 (75 BPM, 92% SpO₂)',
        'test.preset_high_bpm': '高心率 (110 BPM, 97% SpO₂)',
        'test.preset_severe_low_spo2': '嚴重低血氧 (80 BPM, 85% SpO₂)',
        'test.preset_acute_tachycardia': '急性心動過速 (140 BPM, 96% SpO₂)',
        'test.send_single': '單次發送',
        'test.start_auto': '啟動自動發送',
        'test.stop_auto': '停止發送',
        'test.duration': '測量秒數',
        'test.send_completed': '發送完成狀態',
        'test.send_reset': '發送重置狀態',
        'test.scenarios': '測試場景',
        'test.select_scenario_label': '選擇場景',
        'test.scenario_placeholder': '-- 請選擇場景... --',
        'test.scenario_a': '場景 A: 首次有效寫入測試',
        'test.scenario_b': '場景 B: 無效生理數據過濾',
        'test.scenario_c': '場景 C: 血氧下降零延遲寫入',
        'test.scenario_d': '場景 D: 急性心率突增 (ΔBPM)',
        'test.scenario_e': '場景 E: 定時器截斷測試',
        'test.scenario_f': '場景 F: 延遲初始化預熱測試',
        'test.select_scenario_help': '請選擇場景以查看詳情。',
        'test.execute_scenario': '執行場景',
        'test.message_log': '訊息日誌',
        'test.open_monitor': '開啟監控頁面',
        'test.clear_log': '清除日誌',

        // Testing Tool Messages
        'test.scenario_desc.A': '<ul><li>動作：傳送單筆有效數據 (72 BPM, 98% SpO₂)。</li><li>預期結果：系統立即建立新 Session 並觸發 insert_one 寫入 (忽略 20 秒冷卻期)。</li></ul>',
        'test.scenario_desc.B': '<ul><li>動作：傳送 3 筆正常數據後，連續傳送無效極端值 (999 BPM, 40% SpO₂)。</li><li>預期結果：系統將異常值直接丟棄，不觸發資料庫寫入，且不污染移動平均 (MA/EMA) 演算法。</li></ul>',
        'test.scenario_desc.C': '<ul><li>動作：傳送 15 筆正常數據後，突發一筆低血氧數據 (88% SpO₂)。</li><li>預期結果：狀態機判定為 DANGER。無視節流限制，系統立即寫入該危險紀錄至資料庫。</li></ul>',
        'test.scenario_desc.D': '<ul><li>動作：連續傳送 15 筆穩定心率 (70 BPM)，接著傳送突增心率 (125 BPM，模擬 ΔBPM = 55)。</li><li>預期結果：系統偵測出 ΔBPM 劇變，觸發 analysis_status 變更，並立即執行資料庫寫入。</li></ul>',
        'test.scenario_desc.E': '<ul><li>動作：每 2 秒傳送一筆正常數據，持續發送大於 20 秒。</li><li>預期結果：觸發節流機制。資料庫僅會寫入「第 1 秒」與「滿 20 秒」的紀錄，期間數據僅更新記憶體視窗。</li></ul>',
        'test.scenario_desc.F': '<ul><li>動作：系統連線後閒置 5 秒，第 6 秒起才傳送首筆有效數據。</li><li>預期結果：前 5 秒記憶體與資料庫零產出。Session 的建立時間必須與第 6 秒的首筆數據精準吻合。</li></ul>'
    }
};

/**
 * Initializes language based on URL parameter
 * @returns {string} lang ('en' or 'zh')
 */
export function initLang() {
    const params = new URLSearchParams(window.location.search);
    const lang = params.get('lang') || 'en';
    if (lang === 'zh') {
        document.body.className = 'lang-zh';
    } else {
        document.body.className = 'lang-en';
    }
    return lang;
}

/**
 * Translates a key to the specified language
 * @param {string} key - Translation key
 * @param {string} lang - Language code
 * @returns {string} Translated text
 */
export function translate(key, lang = 'en') {
    const dict = translations[lang] || translations['en'];
    return dict[key] || key;
}

/**
 * Scans the container for elements with data-i18n and applies translations
 * @param {string} lang - Language code
 * @param {HTMLElement} container - The container to scan (default: document)
 */
export function applyTranslations(lang, container = document) {
    const elements = container.querySelectorAll('[data-i18n]');
    elements.forEach(el => {
        const key = el.getAttribute('data-i18n');
        const translation = translate(key, lang);
        if (translation !== key) {
            // Check if it looks like HTML
            if (translation.includes('<')) {
                el.innerHTML = translation;
            } else {
                el.textContent = translation;
            }
        }
    });
}

/**
 * Helper for status translations to maintain compatibility
 */
export function getTranslatedStatus(status, lang) {
    const key = `status.${status.toLowerCase()}`;
    return translate(key, lang);
}
