import {
    calculateStatus, getCSSVar, fetchMQTTConfig,
    constructTopic, getMQTTBrokerUrl, getMQTTOptions
} from '../shared.js';
import { initLang, translate, applyTranslations } from '../i18n.js';

let mqttClient;
let connected = false;
let autoSendInterval = null;
let scenarioInterval = null;

const DEFAULT_DEVICE_ID = "MOCK_DEVICE_001";

// Init language
const currentLang = initLang();

// Apply translations to the whole document
applyTranslations(currentLang);

// UI Elements
const connStatus = document.getElementById('connection-status');
const deviceIdInput = document.getElementById('device-id');

// Prevent empty device ID
if (deviceIdInput) {
    deviceIdInput.addEventListener('blur', () => {
        if (!deviceIdInput.value.trim()) {
            deviceIdInput.value = DEFAULT_DEVICE_ID;
        }
    });
}

function getActiveDeviceId() {
    return deviceIdInput?.value.trim() || DEFAULT_DEVICE_ID;
}

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

        const brokerUrl = getMQTTBrokerUrl(config);
        const options = getMQTTOptions(config, 'tester_');

        mqttClient = mqtt.connect(brokerUrl, options);

        mqttClient.on('connect', () => {
            connected = true;
            connStatus.textContent = translate('ui.conn_connected', currentLang);
            connStatus.style.borderColor = neonGreen;
            connStatus.style.color = neonGreen;
            log(`<span style="color:${neonGreen}">Secure MQTT Connected</span>`);
        });

        mqttClient.on('error', (err) => {
            connStatus.textContent = translate('ui.conn_error', currentLang);
            connStatus.style.borderColor = neonRed;
            connStatus.style.color = neonRed;
            log(`<span style="color:${neonRed}">Connection failed: ${err.message}</span>`);
        });

        mqttClient.on('close', () => {
            connected = false;
            connStatus.textContent = translate('ui.conn_lost', currentLang);
            connStatus.style.borderColor = neonRed;
            connStatus.style.color = neonRed;
            log(`<span style="color:${neonRed}">Connection lost</span>`);
        });

        log(`Attempting secure MQTT initialization...`);

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

    const topic = constructTopic('test', getActiveDeviceId());
    mqttClient.publish(topic, payload);
    log(`Published to ${topic}: ${payload}`);
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
    const topic = constructTopic('test', getActiveDeviceId());
    mqttClient.publish(topic, payload);
    log(`<span style="color:${neonYellow}">Published Reset to ${topic}: ${payload}</span>`);
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
    const topic = constructTopic('test', getActiveDeviceId());
    mqttClient.publish(topic, payload);
    log(`<span style="color:${neonBlue}">Published Completed to ${topic}: ${payload}</span>`);
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

document.getElementById('scenarioSelect').addEventListener('change', (e) => {
    const val = e.target.value;
    const descText = document.getElementById('desc-text');

    if (val) {
        const translation = translate(`test.scenario_desc.${val}`, currentLang);
        if (translation.includes('<')) {
            descText.innerHTML = translation;
        } else {
            descText.textContent = translation;
        }
    } else {
        descText.textContent = translate('test.select_scenario_help', currentLang);
    }
});

// Initial trigger to show default text correctly if needed
document.getElementById('scenarioSelect').dispatchEvent(new Event('change'));

window.toggleAutoSend = function() {
    const btn = document.getElementById('autoSendBtn');
    if (autoSendInterval) {
        clearInterval(autoSendInterval);
        autoSendInterval = null;
        btn.textContent = translate('test.start_auto', currentLang);
        btn.classList.remove('active');
    } else {
        autoSendInterval = setInterval(window.publishManual, 1000);
        btn.textContent = translate('test.stop_auto', currentLang);
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
        log(`<span style="color:${neonYellow}">${translate('test.select_scenario_help', currentLang)}</span>`);
        return;
    }

    stopScenarios();
    log(`<b>Executing Scenario ${val}</b>`);

    switch(val) {
        case 'A':
            log(`Expected Backend: Create Session & Write DB (NORMAL)`);
            publish(72, 98);
            break;
        case 'B':
            let countB = 0;
            log(`Expected Backend: Filter 999/40 values during out-of-range event.`);
            scenarioInterval = setInterval(() => {
                countB++;
                if (countB <= 3) publish(72, 98);
                else {
                    log(`<span style="color:${neonRed}">Sending invalid values (999/40)...</span>`);
                    publish(999, 40);
                    if (countB >= 6) stopScenarios();
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
            log(`<span style="color:${neonYellow}">Finger placed. Assert: No ghost records for next 10 seconds...</span>`);
            setTimeout(() => {
                log(`<span style="color:${neonGreen}">Warm-up complete. Starting data stream at T=10s.</span>`);
                let countF = 0;
                scenarioInterval = setInterval(() => {
                    countF++;
                    publish(72, 98);
                    if (countF >= 5) stopScenarios();
                }, 1000);
            }, 10000);
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
