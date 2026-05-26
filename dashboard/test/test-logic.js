import { initLang, calculateStatus, getCSSVar, fetchMQTTConfig } from '../shared.js';

let mqttClient;
let connected = false;
let autoSendInterval = null;
let scenarioInterval = null;
let mqttTopic = "";

// Init language
const currentLang = initLang();

// Localize selects
document.querySelectorAll('select option').forEach(opt => {
    const text = opt.getAttribute(`data-${currentLang}`);
    if (text) opt.textContent = text;
});

const neonGreen = getCSSVar('--neon-green');
const neonRed = getCSSVar('--neon-red');
const neonYellow = getCSSVar('--neon-yellow');

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
        mqttTopic = config.MQTT_TOPIC;

        mqttClient = new Paho.MQTT.Client(host, port, "/mqtt", "tester_" + Math.random().toString(16).substr(2, 8));

        const options = {
            onSuccess: () => {
                connected = true;
                document.getElementById('conn-indicator').className = 'status-dot connected';
                const textEl = document.getElementById('conn-text');
                textEl.querySelector('[data-lang="en"]').textContent = 'Connected';
                textEl.querySelector('[data-lang="zh"]').textContent = '已連線';
                log(`<span style="color:${neonGreen}">Secure MQTT Connected</span>`);
            },
            onFailure: (err) => {
                document.getElementById('conn-indicator').className = 'status-dot disconnected';
                const textEl = document.getElementById('conn-text');
                textEl.querySelector('[data-lang="en"]').textContent = 'Connection Failed';
                textEl.querySelector('[data-lang="zh"]').textContent = '連線失敗';
                log(`<span style="color:${neonRed}">Connection failed: ${err.errorMessage}</span>`);
            },
            useSSL: true
        };

        if (user) options.userName = user;
        if (pass) options.password = pass;

        mqttClient.onConnectionLost = (err) => {
            connected = false;
            document.getElementById('conn-indicator').className = 'status-dot disconnected';
            const textEl = document.getElementById('conn-text');
            textEl.querySelector('[data-lang="en"]').textContent = 'Connection Lost';
            textEl.querySelector('[data-lang="zh"]').textContent = '連線中斷';
            log(`<span style="color:${neonRed}">Connection lost: ${err.errorMessage}</span>`);
        };

        log(`Attempting secure MQTT initialization...`);
        mqttClient.connect(options);

    } catch (err) {
        log(`<span style="color:${neonRed}">Auth Error: ${err.message}</span>`);
    }
}

function publish(bpm, spo2) {
    if (!connected) {
        log(`<span style="color:${neonYellow}">Not connected.</span>`);
        return;
    }
    const status = calculateStatus(bpm, spo2);
    const payload = JSON.stringify({
        bpm: parseInt(bpm),
        spo2: parseInt(spo2),
        status: status
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
    const payload = JSON.stringify({ status: "RESET" });
    const message = new Paho.MQTT.Message(payload);
    message.destinationName = mqttTopic;
    mqttClient.send(message);
    log(`<span style="color:${neonYellow}">Published Reset: ${payload}</span>`);
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
        en: 'Sends a single valid record (72 BPM, 98% SpO2). Used for cold-start write verification.',
        zh: '發送單筆有效記錄 (72 BPM, 98% SpO2)。用於冷啟動寫入驗證。'
    },
    'B': {
        en: '3 normal points → Continuous invalid values (999 BPM, 40% SpO2). Tests sensor detachment filtering logic.',
        zh: '3 筆正常數據 → 持續無效值 (999 BPM, 40% SpO2)。測試感測器脫落過濾邏輯。'
    },
    'C': {
        en: '15 normal points (70 BPM, 98% SpO2) → Sudden SpO2 88%. Tests immediate database write on emergency.',
        zh: '15 筆正常數據 (70 BPM, 98% SpO2) → 突然血氧 88%。測試緊急情況下的立即資料庫寫入。'
    },
    'D': {
        en: '15 stable points (70 BPM, 98% SpO2) → Sudden BPM 125 (ΔBPM=55). Tests change detection logic.',
        zh: '15 筆穩定數據 (70 BPM, 98% SpO2) → 突然心率 125 (ΔBPM=55)。測試變化偵測邏輯。'
    },
    'E': {
        en: '12 normal points (70 BPM, 98% SpO2) sent every 2s. Observes 20-second interval writes.',
        zh: '每 2 秒發送一次正常數據，共 12 筆。觀察 20 秒間隔寫入。'
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

window.toggleAutoSend = function() {
    const btn = document.getElementById('autoSendBtn');
    if (autoSendInterval) {
        clearInterval(autoSendInterval);
        autoSendInterval = null;
        btn.querySelector('[data-lang="en"]').textContent = 'Start Auto (2s)';
        btn.querySelector('[data-lang="zh"]').textContent = '啟動自動發送';
        btn.classList.remove('active');
    } else {
        autoSendInterval = setInterval(window.publishManual, 2000);
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
            publish(72, 98);
            break;
        case 'B':
            let countB = 0;
            scenarioInterval = setInterval(() => {
                countB++;
                if (countB <= 3) publish(72, 98);
                else publish(999, 40);
            }, 2000);
            break;
        case 'C':
            let countC = 0;
            scenarioInterval = setInterval(() => {
                countC++;
                if (countC <= 15) publish(70, 98);
                else if (countC === 16) {
                    publish(70, 88);
                    stopScenarios();
                }
            }, 2000);
            break;
        case 'D':
            let countD = 0;
            scenarioInterval = setInterval(() => {
                countD++;
                if (countD <= 15) publish(70, 98);
                else if (countD === 16) {
                    publish(125, 98);
                    stopScenarios();
                }
            }, 2000);
            break;
        case 'E':
            let countE = 0;
            scenarioInterval = setInterval(() => {
                countE++;
                publish(70, 98);
                if (countE >= 12) stopScenarios();
            }, 2000);
            break;
    }
}

// Attach event listeners
document.getElementById('sendManualBtn').addEventListener('click', window.publishManual);
document.getElementById('sendResetBtn').addEventListener('click', window.publishReset);
document.getElementById('autoSendBtn').addEventListener('click', window.toggleAutoSend);
document.getElementById('executeScenarioBtn').addEventListener('click', window.executeScenario);
document.getElementById('clearLogBtn').addEventListener('click', window.clearLog);

autoConnect();
