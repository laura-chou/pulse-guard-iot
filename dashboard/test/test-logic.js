import { initLang, calculateStatus, getCSSVar, fetchMQTTConfig } from '../shared.js';

let mqttClient;
let connected = false;
let autoSendInterval = null;
let scenarioInterval = null;
let mqttTopic = "";

// Init language
const currentLang = initLang();
const isZh = currentLang === 'zh';

// UI Elements
const connStatus = document.getElementById('connection-status');

// Localize selects
document.querySelectorAll('select option').forEach(opt => {
    const text = opt.getAttribute(`data-${currentLang}`);
    if (text) opt.textContent = text;
});

const neonGreen = getCSSVar('--neon-green');
const neonRed = getCSSVar('--neon-red');
const neonYellow = getCSSVar('--neon-yellow');
const neonBlue = getCSSVar('--neon-blue');

function log(msg) {
    const logArea = document.getElementById('log');
    const time = new Date().toLocaleTimeString('en-GB', { hour12: false });
    logArea.innerHTML += `[${time}] ${msg}<br>`;
    logArea.scrollTop = logArea.scrollHeight;
}

window.clearLog = function() {
    document.getElementById('log').innerHTML = '';
}

async function autoConnect() {
    try {
        const config = await fetchMQTTConfig();

        const host = config.MQTT_HOST;
        if (!host || typeof host !== 'string') {
            throw new Error("Missing MQTT host configuration");
        }
        const port = parseInt(config.MQTT_PORT);
        const user = config.MQTT_USERNAME;
        const pass = config.MQTT_PASSWORD;
        mqttTopic = config.MQTT_TEST_TOPIC;

        mqttClient = new Paho.MQTT.Client(host, port, "/mqtt", "tester_" + Math.random().toString(16).substr(2, 8));

        const options = {
            onSuccess: () => {
                connected = true;
                connStatus.textContent = isZh ? '🟢 已連線' : '🟢 Connected';
                connStatus.style.borderColor = neonGreen;
                connStatus.style.color = neonGreen;
                log(`<span style="color:${neonGreen}">Secure MQTT Connected</span>`);
            },
            onFailure: (err) => {
                connStatus.textContent = isZh ? '🔴 連線錯誤' : '🔴 Connection Error';
                connStatus.style.borderColor = neonRed;
                connStatus.style.color = neonRed;
                log(`<span style="color:${neonRed}">Connection failed: ${err.errorMessage}</span>`);
            },
            useSSL: true
        };

        if (user) options.userName = user;
        if (pass) options.password = pass;

        mqttClient.onConnectionLost = (err) => {
            connected = false;
            connStatus.textContent = isZh ? '🔴 連線中斷' : '🔴 Connection Lost';
            connStatus.style.borderColor = neonRed;
            connStatus.style.color = neonRed;
            log(`<span style="color:${neonRed}">Connection lost: ${err.errorMessage}</span>`);
        };

        log(`Attempting secure MQTT initialization...`);
        mqttClient.connect(options);

    } catch (err) {
        log(`<span style="color:${neonRed}">Auth Error: ${err.message}</span>`);
    }
}

function publish(bpm, spo2, statusOverride = null) {
    if (!connected) {
        log(`<span style="color:${neonYellow}">Not connected.</span>`);
        return;
    }
    const status = statusOverride || calculateStatus(bpm, spo2);
    const payload = JSON.stringify({
        bpm: parseInt(bpm),
        spo2: parseInt(spo2),
        device_status: status
    });
    const message = new Paho.MQTT.Message(payload);
    message.destinationName = mqttTopic;
    mqttClient.send(message);
    log(`Published: ${payload}`);
}

window.publishManual = function() {
    const bpm = document.getElementById('manual-bpm').value;
    const spo2 = document.getElementById('manual-spo2').value;
    publish(bpm, spo2);
}

window.publishReset = function() {
    if (!connected) {
        log(`<span style="color:${neonYellow}">Not connected.</span>`);
        return;
    }
    const payload = JSON.stringify({ device_status: "RESET" });
    const message = new Paho.MQTT.Message(payload);
    message.destinationName = mqttTopic;
    mqttClient.send(message);
    log(`<span style="color:${neonYellow}">Published Reset: ${payload}</span>`);
}

window.publishCompleted = function() {
    if (!connected) {
        log(`<span style="color:${neonYellow}">Not connected.</span>`);
        return;
    }

    const durationInput = document.getElementById('manual-duration');
    if (!durationInput) {
        log(`<span style="color:${neonYellow}">Duration input not found.</span>`);
        return;
    }

    const duration = parseInt(durationInput.value, 10);
    if (!Number.isFinite(duration) || duration <= 0) {
        log(`<span style="color:${neonYellow}">Invalid duration value.</span>`);
        return;
    }

    const payload = JSON.stringify({ device_status: "COMPLETED", duration_sec: duration });
    const message = new Paho.MQTT.Message(payload);
    message.destinationName = mqttTopic;
    mqttClient.send(message);
    log(`<span style="color:${neonBlue}">Published Completed: ${payload}</span>`);
}

// Preset logic
document.getElementById('presetSelect').addEventListener('change', (e) => {
    const preset = e.target.value;
    const bpmInput = document.getElementById('manual-bpm');
    const spo2Input = document.getElementById('manual-spo2');

    switch (preset) {
        case 'normal':
            bpmInput.value = 70;
            spo2Input.value = 98;
            break;
        case 'low_spo2':
            bpmInput.value = 75;
            spo2Input.value = 92;
            break;
        case 'high_bpm':
            bpmInput.value = 110;
            spo2Input.value = 97;
            break;
        case 'severe_low_spo2':
            bpmInput.value = 80;
            spo2Input.value = 85;
            break;
        case 'acute_tachycardia':
            bpmInput.value = 140;
            spo2Input.value = 96;
            break;
    }
});

// Scenario descriptions
const scenarios = {
    'A': {
        en: 'Sends a single valid record (72 BPM, 98% SpO2). Assert: Cold-start session creation and first DB write.',
        zh: '發送單筆有效記錄 (72 BPM, 98% SpO2)。斷言：冷啟動 Session 建立與首次資料庫寫入。'
    },
    'B1': {
        en: '3 normal points → 999 BPM / 40% SpO2. Assert: Backend filters invalid values and stops DB writes.',
        zh: '3 筆正常數據 → 999 BPM / 40% SpO2。斷言：後端過濾無效數值且停止寫入資料庫。'
    },
    'B2': {
        en: '3 normal points → device_status: "OFF-CHIP". Assert: Backend detects hardware detachment and logs event.',
        zh: '3 筆正常數據 → 狀態設為 "OFF-CHIP"。斷言：後端偵測到硬體脫離並記錄事件。'
    },
    'C': {
        en: '15 normal points (70 BPM, 98% SpO2) → SpO2 88%. Assert: Immediate DB write due to DANGER status.',
        zh: '15 筆正常數據 (70 BPM, 98% SpO2) → 血氧 88%。斷言：觸發 DANGER 狀態並立即寫入資料庫。'
    },
    'D': {
        en: '15 stable points (70 BPM, 98% SpO2) → BPM 125. Assert: Edge sends WARNING, but Cloud asserts DANGER (ΔBPM=55).',
        zh: '15 筆穩定數據 (70 BPM, 98% SpO2) → 心率 125。斷言：前端發送 WARNING，但雲端判定為 DANGER (ΔBPM=55)。'
    },
    'E': {
        en: 'Constant 75 BPM / 98% SpO2 sent every 2s. Assert: DB writes only at 0s and 20s (Heartbeat mechanism).',
        zh: '全程固定 75 BPM / 98% SpO2 每 2 秒發送。斷言：僅在 0s 與 20s 執行寫入（心跳機制）。'
    },
    'F': {
        en: 'Wait 5s then start stream. Assert: No ghost records before 5s; Session start_time matches first valid point.',
        zh: '等待 5 秒才開始串流。斷言：5s 前無任何記錄；Session 開始時間與首筆有效數據吻合。'
    }
};


document.getElementById('scenarioSelect').addEventListener('change', (e) => {
    const val = e.target.value;
    const descEn = document.getElementById('desc-en');
    const descZh = document.getElementById('desc-zh');

    if (val && scenarios[val]) {
        descEn.textContent = scenarios[val].en;
        descZh.textContent = scenarios[val].zh;
    } else {
        descEn.textContent = 'Please select a scenario to see details.';
        descZh.textContent = '請選擇場景以查看詳情。';
    }
});

// Initial trigger to show default text correctly if needed
document.getElementById('scenarioSelect').dispatchEvent(new Event('change'));

window.toggleAutoSend = function() {
    const btn = document.getElementById('autoSendBtn');
    if (autoSendInterval) {
        clearInterval(autoSendInterval);
        autoSendInterval = null;
        btn.querySelector('[data-lang="en"]').textContent = 'Start Auto (1s)';
        btn.querySelector('[data-lang="zh"]').textContent = '啟動自動發送';
        btn.classList.remove('active');
    } else {
        autoSendInterval = setInterval(window.publishManual, 1000);
        btn.querySelector('[data-lang="en"]').textContent = 'Stop Auto';
        btn.querySelector('[data-lang="zh"]').textContent = '停止發送';
        btn.classList.add('active');
        window.publishManual();
    }
}

function stopScenarios() {
    if (scenarioInterval) {
        clearInterval(scenarioInterval);
        scenarioInterval = null;
    }
}

window.executeScenario = function() {
    const val = document.getElementById('scenarioSelect').value;
    if (!val) {
        log(`<span style="color:${neonYellow}">Please select a scenario first.</span>`);
        return;
    }

    stopScenarios();
    log(`<b>Executing Scenario ${val}</b>`);

    switch(val) {
        case 'A':
            log(`Expected Backend: Create Session & Write DB (NORMAL)`);
            publish(72, 98);
            break;
        case 'B1':
            let countB1 = 0;
            log(`Expected Backend: Filter 999/40 values.`);
            scenarioInterval = setInterval(() => {
                countB1++;
                if (countB1 <= 3) publish(72, 98);
                else {
                    log(`<span style="color:${neonRed}">Sending invalid values (999/40)...</span>`);
                    publish(999, 40);
                    if (countB1 >= 6) stopScenarios();
                }
            }, 2000);
            break;
        case 'B2':
            let countB2 = 0;
            log(`Expected Backend: Detect OFF-CHIP detachment.`);
            scenarioInterval = setInterval(() => {
                countB2++;
                if (countB2 <= 3) publish(72, 98);
                else {
                    log(`<span style="color:${neonRed}">Sending OFF-CHIP status...</span>`);
                    publish(72, 98, "OFF-CHIP");
                    stopScenarios();
                }
            }, 2000);
            break;
        case 'C':
            let countC = 0;
            log(`Expected Backend: Immediate write at point 16 (SpO2=88 -> DANGER)`);
            scenarioInterval = setInterval(() => {
                countC++;
                if (countC <= 15) publish(70, 98);
                else if (countC === 16) {
                    publish(70, 88);
                    stopScenarios();
                }
            }, 1000);
            break;
        case 'D':
            let countD = 0;
            log(`Expected Backend: DANGER at point 16 (ΔBPM=55) though Edge sends WARNING (125 BPM)`);
            scenarioInterval = setInterval(() => {
                countD++;
                if (countD <= 15) publish(70, 98);
                else if (countD === 16) {
                    publish(125, 98);
                    stopScenarios();
                }
            }, 1000);
            break;
        case 'E':
            let countE = 0;
            log(`Expected Backend: Write at 0s and 20s (Heartbeat) with stable 75/98`);
            scenarioInterval = setInterval(() => {
                countE++;
                publish(75, 98);
                if (countE >= 12) stopScenarios();
            }, 2000);
            break;
        case 'F':
            log(`<span style="color:${neonYellow}">Finger placed. Assert: No ghost records for next 5 seconds...</span>`);
            setTimeout(() => {
                log(`<span style="color:${neonGreen}">Warm-up complete. Starting data stream at T=5s.</span>`);
                let countF = 0;
                scenarioInterval = setInterval(() => {
                    countF++;
                    publish(72, 98);
                    if (countF >= 5) stopScenarios();
                }, 1000);
            }, 5000);
            break;
    }
}

// Attach event listeners
document.getElementById('sendManualBtn').addEventListener('click', window.publishManual);
document.getElementById('sendResetBtn').addEventListener('click', window.publishReset);
document.getElementById('sendCompletedBtn').addEventListener('click', window.publishCompleted);
document.getElementById('autoSendBtn').addEventListener('click', window.toggleAutoSend);
document.getElementById('executeScenarioBtn').addEventListener('click', window.executeScenario);
document.getElementById('clearLogBtn').addEventListener('click', window.clearLog);

// Sync language to monitor link
const monitorLink = document.getElementById('monitorLink');
if (monitorLink) {
    const urlParams = new URLSearchParams(window.location.search);
    const lang = urlParams.get('lang');
    if (lang) {
        monitorLink.href = `monitor.html?lang=${lang}`;
    }
}

autoConnect();
