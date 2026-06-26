import { getCSSVar, initLang, getTranslatedStatus, fetchMQTTConfig } from './shared.js';

// UI Elements
const connStatus = document.getElementById('connection-status');
const lastUpdateEl = document.getElementById('last-update');
const bpmEl = document.getElementById('bpm');
const spo2El = document.getElementById('spo2');
const statusEl = document.getElementById('status');

// Execute Lang Init immediately
const lang = initLang();

// Background Color Plugin for Chart.js
const chartBackgroundPlugin = {
    id: 'chartBackgroundPlugin',
    beforeDraw: (chart) => {
        const { ctx, chartArea, scales: { y } } = chart;
        if (!chartArea || !chart.options.plugins.backgroundZones) return;

        const zones = chart.options.plugins.backgroundZones;

        zones.forEach(zone => {
            const yMin = y.getPixelForValue(zone.min);
            const yMax = y.getPixelForValue(zone.max);

            ctx.fillStyle = zone.color;
            ctx.fillRect(
                chartArea.left,
                Math.min(yMin, yMax),
                chartArea.width,
                Math.abs(yMin - yMax)
            );
        });
    }
};

// Chart.js Configuration
const MAX_DATA_POINTS = 30;

function createChart(ctxId, label, color, bgColor, yMin, yMax, zones, unit) {
    const ctx = document.getElementById(ctxId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        plugins: [chartBackgroundPlugin],
        data: {
            labels: [],
            datasets: [{
                label: label,
                data: [],
                borderColor: color,
                backgroundColor: bgColor,
                borderWidth: 2,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    display: true,
                    grid: { color: 'rgba(148, 163, 184, 0.1)' },
                    ticks: {
                        color: '#94a3b8',
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 10
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    min: yMin,
                    max: yMax,
                    grid: { color: 'rgba(148, 163, 184, 0.1)' },
                    ticks: { color: '#94a3b8' }
                }
            },
            plugins: {
                tooltip: {
                    displayColors: false,
                    callbacks: {
                        title: function(context) {
                            const index = context[0].dataIndex;
                            return context[0].chart.data.fullTimestamps[index];
                        },
                        label: function(context) {
                            return `${context.parsed.y}${unit === '%' ? '%' : ' ' + unit}`;
                        }
                    }
                },
                legend: {
                    labels: { color: '#f8fafc' },
                    onClick: () => null // Disable hiding dataset on legend click
                },
                backgroundZones: zones
            }
        }
    });
}

// Get colors from CSS
const colorRed = getCSSVar('--neon-red');
const colorBlue = getCSSVar('--neon-blue');
const colorGreen = getCSSVar('--neon-green');
const colorYellow = getCSSVar('--neon-yellow');

// BPM Chart zones
const bpmZones = [
    { min: 40, max: 50, color: `${colorRed}2e` },    // DANGER
    { min: 50, max: 60, color: `${colorYellow}26` },   // WARNING
    { min: 60, max: 101, color: `${colorGreen}3b` },  // NORMAL (High visibility)
    { min: 101, max: 121, color: `${colorYellow}26` }, // WARNING
    { min: 121, max: 180, color: `${colorRed}2e` }  // DANGER
];

// SpO₂ Chart zones
const spo2Zones = [
    { min: 80, max: 90, color: `${colorRed}2e` },   // DANGER
    { min: 90, max: 95, color: `${colorYellow}26` },   // WARNING
    { min: 95, max: 100, color: `${colorGreen}3b` }  // NORMAL (High visibility)
];

const isZh = lang === 'zh';
const bpmChart = createChart('bpmChart', isZh ? '心率趨勢' : 'Heart Rate Trend', colorRed, `${colorRed}1a`, 40, 180, bpmZones, 'BPM');
const spo2Chart = createChart('spo2Chart', isZh ? '血氧趨勢' : 'SpO₂ Trend', colorBlue, `${colorBlue}1a`, 80, 100, spo2Zones, '%');

// Initialize custom storage for full timestamps
bpmChart.data.fullTimestamps = [];
spo2Chart.data.fullTimestamps = [];

// MQTT Initialization
async function initMQTT() {
    try {
        const config = await fetchMQTTConfig();

        const host     = config.MQTT_HOST;
        const port     = config.MQTT_PORT;
        const topic    = config.MQTT_TOPIC_PATTERN;
        const username = config.MQTT_USERNAME;
        const password = config.MQTT_PASSWORD;

        if (!host || !topic) {
            throw new Error("Missing MQTT configuration");
        }

        const brokerUrl = `wss://${host}:${port}/mqtt`;

        const options = {
            clean: true,
            connectTimeout: 4000,
            clientId: 'pulseguard_web_' + Math.random().toString(16).substr(2, 8),
            username: username,
            password: password,
        };

        const client = mqtt.connect(brokerUrl, options);

        client.on('connect', () => {
            connStatus.textContent = isZh ? '🟢 已連線' : '🟢 Connected';
            connStatus.style.borderColor = colorGreen;
            connStatus.style.color = colorGreen;
            client.subscribe(topic);
        });

        client.on('error', (err) => {
            connStatus.textContent = isZh ? '🔴 連線錯誤' : '🔴 Connection Error';
            connStatus.style.borderColor = colorRed;
            connStatus.style.color = colorRed;
        });

        client.on('message', (receivedTopic, message) => {
            try {
                const data = JSON.parse(message.toString());

                // Status-based reset
                const deviceStatus = (data.device_status || data.status)?.toUpperCase();
                if (deviceStatus === 'RESET') {
                    resetDashboard();
                    return;
                }

                // Ignore COMPLETED status
                if (deviceStatus === 'COMPLETED') {
                    return;
                }

                const now = new Date();
                const fullTime = now.toLocaleTimeString('en-GB', { hour12: false });
                const axisTime = fullTime.split(':').slice(1).join(':'); // mm:ss

                // Update cards
                if (data.bpm !== undefined) bpmEl.textContent = data.bpm;
                if (data.spo2 !== undefined) spo2El.textContent = data.spo2;
                if (deviceStatus !== undefined) {
                    statusEl.textContent = getTranslatedStatus(deviceStatus, isZh ? 'zh' : 'en');
                    updateStatusColor(deviceStatus);
                }

                // Update "Last Update"
                lastUpdateEl.textContent = `${isZh ? '最後更新' : 'Last Update'}: ${fullTime}`;

                // Update Charts
                addData(bpmChart, axisTime, fullTime, data.bpm);
                addData(spo2Chart, axisTime, fullTime, data.spo2);

            } catch (e) {
                console.error('Error parsing MQTT message:', e);
            }
        });

    } catch (error) {
        connStatus.textContent = isZh ? '⚠️ 設定錯誤' : '⚠️ Config Error';
        connStatus.style.borderColor = colorRed;
        connStatus.style.color = colorRed;
    }
}

function updateStatusColor(status) {
    const statusCard = document.getElementById('status-card');
    if (!status) return;

    switch (status.toUpperCase()) {
        case 'NORMAL':
            statusCard.style.borderLeftColor = colorGreen;
            statusEl.style.color = colorGreen;
            break;
        case 'WARNING':
            statusCard.style.borderLeftColor = colorYellow;
            statusEl.style.color = colorYellow;
            break;
        case 'DANGER':
            statusCard.style.borderLeftColor = colorRed;
            statusEl.style.color = colorRed;
            break;
        default:
            statusCard.style.borderLeftColor = '#94a3b8';
            statusEl.style.color = '#f8fafc';
    }
}

function addData(chart, axisLabel, fullTimestamp, value) {
    chart.data.labels.push(axisLabel);
    chart.data.fullTimestamps.push(fullTimestamp);
    chart.data.datasets[0].data.push(value);

    if (chart.data.labels.length > MAX_DATA_POINTS) {
        chart.data.labels.shift();
        chart.data.fullTimestamps.shift();
        chart.data.datasets[0].data.shift();
    }
    chart.update('none');
}

function resetDashboard() {
    // Reset cards
    bpmEl.textContent = '--';
    spo2El.textContent = '--';

    // Restore bilingual initial state
    statusEl.innerHTML = `
        <span data-lang="en">WAITING</span>
        <span data-lang="zh">待機中</span>
    `;

    lastUpdateEl.textContent = '';
    updateStatusColor('DEFAULT');

    // Reset charts
    [bpmChart, spo2Chart].forEach(chart => {
        chart.data.labels = [];
        chart.data.fullTimestamps = [];
        chart.data.datasets[0].data = [];
        chart.update();
    });

    console.log('Dashboard Reset Triggered');
}

// Expose for integration/testing
window.resetDashboard = resetDashboard;

initMQTT();
