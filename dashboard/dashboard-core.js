import {
    getCSSVar, fetchMQTTConfig, getMQTTBrokerUrl, getMQTTOptions, constructTopic
} from './shared.js';
import { initLang, translate, getTranslatedStatus } from './i18n.js';
import { renderHeader, renderDashboardBody } from './components.js';

// Global Chart variables
let bpmChart, spo2Chart;
const MAX_DATA_POINTS = 30;

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

/**
 * Creates a Chart.js instance
 */
function createChart(ctxId, label, color, bgColor, yMin, yMax, zones, unit) {
    const canvas = document.getElementById(ctxId);
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');

    const chart = new Chart(ctx, {
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
    chart.data.fullTimestamps = [];
    return chart;
}

/**
 * Adds data to a chart
 */
function addData(chart, axisLabel, fullTimestamp, value) {
    if (!chart) return;
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

/**
 * Updates UI status colors
 */
function updateStatusColor(status) {
    const statusCard = document.getElementById('status-card');
    const statusEl = document.getElementById('status');
    if (!statusCard || !statusEl) return;

    const colorRed = getCSSVar('--neon-red');
    const colorGreen = getCSSVar('--neon-green');
    const colorYellow = getCSSVar('--neon-yellow');

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
            statusCard.style.borderLeftColor = 'rgba(255, 255, 255, 0.1)';
            statusEl.style.color = '#f8fafc';
    }
}

/**
 * Resets the dashboard UI and charts
 */
export function resetDashboard() {
    const bpmEl = document.getElementById('bpm');
    const spo2El = document.getElementById('spo2');
    const statusEl = document.getElementById('status');
    const statusMessageEl = document.getElementById('status-message');

    if (bpmEl) bpmEl.textContent = '--';
    if (spo2El) spo2El.textContent = '--';

    if (statusEl) {
        statusEl.innerHTML = `
            <span data-lang="en">WAITING</span>
            <span data-lang="zh">待機中</span>
        `;
    }

    if (statusMessageEl) statusMessageEl.textContent = '';
    updateStatusColor('DEFAULT');

    [bpmChart, spo2Chart].forEach(chart => {
        if (!chart) return;
        chart.data.labels = [];
        chart.data.fullTimestamps = [];
        chart.data.datasets[0].data = [];
        chart.update();
    });

    console.log('Dashboard Reset Triggered');
}

// Expose resetDashboard to window for testing
window.resetDashboard = resetDashboard;

/**
 * Initializes the dashboard
 * @param {Object} config - { env, clientIdPrefix, uiConfig }
 */
export async function initDashboard(config) {
    const { clientIdPrefix, uiConfig } = config;

    // 1. Render UI
    renderHeader(uiConfig);
    renderDashboardBody();

    // 2. Initialize Language & Params
    const lang = initLang();
    const params = new URLSearchParams(window.location.search);

    // Environment strictly from config
    const currentEnv = config.env || 'prod';

    // Device ID Logic: prioritize URL parameter 'did'
    let targetDeviceId = params.get('did');
    if (!targetDeviceId && currentEnv === 'test') {
        targetDeviceId = 'MOCK_DEVICE_001';
    }

    // 3. UI Elements
    const connStatus = document.getElementById('connection-status');
    const statusMessageEl = document.getElementById('status-message');
    const bpmEl = document.getElementById('bpm');
    const spo2El = document.getElementById('spo2');
    const statusEl = document.getElementById('status');

    const colorRed = getCSSVar('--neon-red');

    // Abort if prod and no Device ID specified
    if (currentEnv === 'prod' && !targetDeviceId) {
        if (statusMessageEl) {
            statusMessageEl.textContent = translate('error.no_device', lang);
            statusMessageEl.style.color = colorRed;
        }
        return;
    }

    // 4. Initialize Charts
    const colorBlue = getCSSVar('--neon-blue');
    const colorGreen = getCSSVar('--neon-green');
    const colorYellow = getCSSVar('--neon-yellow');

    const bpmZones = [
        { min: 40, max: 50, color: `${colorRed}2e` },
        { min: 50, max: 60, color: `${colorYellow}26` },
        { min: 60, max: 101, color: `${colorGreen}3b` },
        { min: 101, max: 121, color: `${colorYellow}26` },
        { min: 121, max: 180, color: `${colorRed}2e` }
    ];

    const spo2Zones = [
        { min: 80, max: 90, color: `${colorRed}2e` },
        { min: 90, max: 95, color: `${colorYellow}26` },
        { min: 95, max: 100, color: `${colorGreen}3b` }
    ];

    bpmChart = createChart('bpmChart', translate('chart.hr_trend', lang), colorRed, `${colorRed}1a`, 40, 180, bpmZones, 'BPM');
    spo2Chart = createChart('spo2Chart', translate('chart.spo2_trend', lang), colorBlue, `${colorBlue}1a`, 80, 100, spo2Zones, '%');

    // 5. Initialize MQTT
    try {
        const mqttConfig = await fetchMQTTConfig();
        const brokerUrl = getMQTTBrokerUrl(mqttConfig);
        const options = getMQTTOptions(mqttConfig, clientIdPrefix);
        const subscriptionTopic = constructTopic(currentEnv, targetDeviceId);

        const client = mqtt.connect(brokerUrl, options);

        client.on('connect', () => {
            if (connStatus) {
                connStatus.textContent = translate('ui.conn_connected', lang);
                connStatus.style.borderColor = colorGreen;
                connStatus.style.color = colorGreen;
            }
            client.subscribe(subscriptionTopic);
        });

        client.on('error', (err) => {
            if (connStatus) {
                connStatus.textContent = translate('ui.conn_error', lang);
                connStatus.style.borderColor = colorRed;
                connStatus.style.color = colorRed;
            }
            console.error('MQTT Connection Error:', err);
        });

        client.on('message', (receivedTopic, message) => {
            try {
                const topicParts = receivedTopic.split('/');
                if (topicParts.length !== 4 || topicParts[0] !== 'pulseguard' || topicParts[3] !== 'data') return;

                // Strict Environment & Device Filtering
                if (topicParts[1] !== currentEnv || topicParts[2] !== targetDeviceId) return;

                const data = JSON.parse(message.toString());

                // Status-based reset
                const deviceStatus = (data.device_status || data.status)?.toUpperCase();
                if (deviceStatus === 'RESET') {
                    resetDashboard();
                    return;
                }

                if (deviceStatus === 'COMPLETED') return;

                const now = new Date();
                const fullTime = now.toLocaleTimeString('en-GB', { hour12: false });
                const axisTime = fullTime.split(':').slice(1).join(':');

                // Update UI
                if (data.bpm !== undefined && bpmEl) bpmEl.textContent = data.bpm;
                if (data.spo2 !== undefined && spo2El) spo2El.textContent = data.spo2;
                if (deviceStatus !== undefined && statusEl) {
                    statusEl.textContent = getTranslatedStatus(deviceStatus, lang);
                    updateStatusColor(deviceStatus);
                }

                if (statusMessageEl) {
                    statusMessageEl.textContent = `${translate('ui.last_update', lang)}: ${fullTime}`;
                }

                // Update Charts
                addData(bpmChart, axisTime, fullTime, data.bpm);
                addData(spo2Chart, axisTime, fullTime, data.spo2);

            } catch (e) {
                console.error('Error processing MQTT message:', e);
            }
        });

    } catch (error) {
        console.error('Initialization Error:', error);
        if (connStatus) {
            connStatus.textContent = translate('error.config', lang);
            connStatus.style.borderColor = colorRed;
            connStatus.style.color = colorRed;
        }
    }
}
