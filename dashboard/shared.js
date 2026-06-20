// Shared Utilities for PulseGuard Dashboard

// Helper to get CSS variables
export const getCSSVar = (name) => {
    if (typeof window === 'undefined') return '';
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
};

// Multilingual Logic
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

// Translation Helper
export function getTranslatedStatus(status, lang) {
    if (lang !== 'zh') return status;
    const translations = {
        'NORMAL': '正常',
        'WARNING': '警告',
        'DANGER': '危險',
        'WAITING': '待機中'
    };
    return translations[status] || status;
}

// MQTT Configuration Loader
export async function fetchMQTTConfig() {
    try {
        const response = await fetch('/api/mqtt-auth');
        if (!response.ok) throw new Error('Failed to fetch MQTT config');
        return await response.json();
    } catch (err) {
        console.error('MQTT Config Error:', err);
        throw err;
    }
}
