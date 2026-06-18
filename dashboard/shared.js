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
    let status = 'NORMAL';
    // DANGER: SPO2 <= 90% or BPM < 50 or BPM > 130
    // Note: 130 is used to allow Scenario D (125 BPM) to be WARNING on Edge while DANGER on Cloud (due to Delta)
    if (spo2 <= 90 || bpm < 50 || bpm > 130) {
        status = 'DANGER';
    }
    // WARNING: 91% ≤ SPO2 ≤ 94% or 50 ≤ BPM ≤ 59 or 101 ≤ BPM ≤ 130
    else if ((spo2 >= 91 && spo2 <= 94) || (bpm >= 50 && bpm <= 59) || (bpm >= 101 && bpm <= 130)) {
        status = 'WARNING';
    }
    return status;
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
