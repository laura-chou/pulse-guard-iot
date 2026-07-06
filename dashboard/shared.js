// Shared Utilities for PulseGuard Dashboard

// Helper to get CSS variables
export const getCSSVar = (name) => {
    if (typeof window === 'undefined') return '';
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
};

// Clinical Status Calculation Logic
export function calculateStatus(bpm, spo2) {
    /**
     * Hierarchical Waterfall Logic (Edge Version):
     * 1. DANGER: Acute threshold breach (Instant alert)
     * 2. NORMAL: Strict health baseline (Optimal range)
     * 3. WARNING: Any value between Danger and Normal (Transition/Unstable)
     *
     * This eliminates "Dead Zones" where floating-point values (e.g., 90.5% SpO2)
     * would previously incorrectly default to NORMAL.
     */

    // Tier 1: DANGER (Highest Priority)
    // Note: 130 is used to allow Scenario D (125 BPM) to be WARNING on Edge while DANGER on Cloud (due to Delta)
    if (spo2 <= 90 || bpm < 50 || bpm > 130) {
        return 'DANGER';
    }

    // Tier 2: NORMAL (Strict Baseline)
    // Values must fully meet these criteria to be considered "Optimal"
    if (spo2 >= 95 && (bpm >= 60 && bpm <= 100)) {
        return 'NORMAL';
    }

    // Tier 3: WARNING (Fallback)
    // Covers all transition zones: 90 < SpO2 < 95, 50 <= BPM < 60, 100 < BPM <= 130
    return 'WARNING';
}

// MQTT Configuration Loader
export async function fetchMQTTConfig() {
    try {
        const response = await fetch('/api/mqtt-auth.php');
        if (!response.ok) throw new Error('Failed to fetch MQTT config');
        return await response.json();
    } catch (err) {
        console.error('MQTT Config Error:', err);
        throw err;
    }
}

/**
 * Constructs an MQTT topic string
 * @param {string} env - 'prod' or 'test'
 * @param {string} deviceId - The device ID
 */
export function constructTopic(env, deviceId) {
    return `pulseguard/${env}/${deviceId}/data`;
}

/**
 * Constructs the MQTT Broker WebSocket URL
 * @param {Object} config - MQTT configuration object
 */
export function getMQTTBrokerUrl(config) {
    const { MQTT_HOST, MQTT_PORT } = config;
    return `wss://${MQTT_HOST}:${MQTT_PORT}/mqtt`;
}

/**
 * Constructs the MQTT connection options
 * @param {Object} config - MQTT configuration object
 * @param {string} clientIdPrefix - Prefix for the client ID
 */
export function getMQTTOptions(config, clientIdPrefix) {
    return {
        clean: true,
        connectTimeout: 4000,
        clientId: clientIdPrefix + Math.random().toString(16).substr(2, 8),
        username: config.MQTT_USERNAME,
        password: config.MQTT_PASSWORD,
    };
}
