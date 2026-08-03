#include "display_manager.h"
#include <WiFi.h>

#if (DISPLAY_TYPE == OLED_SSD1306)

extern uint32_t totalFingerSeconds;

Waveform::Waveform() : wavep(0) {
    memset(waveform, 128, MAXWAVE);
}

void Waveform::record(int waveval) {
    waveval = waveval / 8; waveval += 128;
    waveval = waveval < 0 ? 0 : (waveval > 255 ? 255 : waveval);
    waveform[wavep] = (uint8_t)waveval;
    wavep = (wavep + 1) % MAXWAVE;
}

void Waveform::scale() {
    uint8_t maxw = 0; uint8_t minw = 255;
    for (int i = 0; i < MAXWAVE; i++) {
        maxw = waveform[i] > maxw ? waveform[i] : maxw;
        minw = waveform[i] < minw ? waveform[i] : minw;
    }
    uint8_t range = maxw - minw; if (range == 0) range = 1;
    uint8_t index = wavep;
    for (int i = 0; i < MAXWAVE; i++) {
        // Map samples to height range Y: 49~62 for the bottom yellow area (Y: 48~63)
        disp_wave[i] = 62 - ((uint16_t)(waveform[index] - minw) * 13) / range;
        index = (index + 1) % MAXWAVE;
    }
}

void Waveform::draw(SSD1306 &oled, uint8_t X) {
    for (int i = 0; i < MAXWAVE - 1; i++) {
        oled.drawLine(X + i, disp_wave[i], X + i + 1, disp_wave[i + 1]);
    }
}

void Waveform::clear() {
    wavep = 0;
    memset(waveform, 128, MAXWAVE);
}

DisplayManager::DisplayManager() :
    last_msg(-1),
    last_printed_bpm(-1),
    last_printed_spo2(-1),
    last_printed_seconds(-1),
    last_printed_status(-1),
    lastWarmingUpState(false),
    lastWarmUpDraw(0) {}

void DisplayManager::begin() {
    oled.init();
    oled.fill(0x00);
}

void DisplayManager::enableDisplay(bool enable) {
    if (enable) oled.on();
    else oled.off();
}

void DisplayManager::fillScreen(uint16_t color) {
    oled.fill(0x00);
}

void DisplayManager::recordWaveform(int waveval) {
    wave.record(waveval);
}

void DisplayManager::clearWaveform() {
    wave.clear();
}

void DisplayManager::updateScreen(int msg, int beatAvg, int SPO2, DeviceStatus currentStatus, uint32_t totalFingerSeconds, uint32_t fingerOnStartTime) {
    last_msg = msg;
    oled.firstPage();
    do {
        switch(msg) {
            case 0: drawDeviceError(); break;
            case 1: drawPlaceFinger(); break;
            case 2: drawMeasuring(beatAvg, SPO2, currentStatus, totalFingerSeconds, fingerOnStartTime); break;
            case 3: drawWelcome(); break;
            case 4: drawPowerOff(totalFingerSeconds); break;
            case 5: drawWiFiSetup(); break;
            case 6: drawResetSuccess(); break;
            case 7: drawCompletion(); break;
        }
    } while (oled.nextPage());
}

void DisplayManager::drawDeviceError() {
    oled.drawStr(28, 20, "DEVICE ERROR", 1);
    oled.drawStr(19, 34, "Check I2C Wire!", 1);
}

void DisplayManager::drawPlaceFinger() {
    oled.drawStr(28, 20, "PLACE FINGER", 1);
    oled.drawStr(22, 34, "IR Filter: Avg", 1);
}

void DisplayManager::drawMeasuring(int beatAvg, int SPO2, DeviceStatus currentStatus, uint32_t totalFingerSeconds, uint32_t fingerOnStartTime) {
    bool isWarmingUp = (fingerOnStartTime == 0 || (millis() - fingerOnStartTime < STABILIZATION_MS));

    // --- 1. Top Blue Area (Y: 0~47): Symmetrical Dual-column Layout ---

    // (A) Left Half: Heart Rate Section (HR, X: 0~63, Y: 0~47)
    // Title: Display small font "HR" (scale 1) at the top-left corner (X: 4, Y: 6)
    oled.drawStr(4, 6, "HR", 1);

    // Value: Convert beatAvg to string and display with large font (scale 2), centered dynamically, Y-coordinate is 20. If <= 0, display "---"
    char bpmStr[8];
    int hr_len = 0;
    if (beatAvg > 0) {
        sprintf(bpmStr, "%d", beatAvg);
        hr_len = strlen(bpmStr);
    } else {
        strcpy(bpmStr, "---");
        hr_len = 3;
    }
    // Large font (scale 2) width is 12px per character. Left half is X: 0~63
    int hr_val_x = (63 - (hr_len * 12)) / 2;
    oled.drawStr(hr_val_x, 20, bpmStr, 2);

    // Unit: Display small font "bpm" (scale 1) at fixed position (X: 40, Y: 36) of the left half
    oled.drawStr(40, 36, "bpm", 1);


    // (B) Central Divider Line
    // Draw a vertical line using oled.drawLine() at X: 63, Y: 6 to 42, separating the left and right halves.
    oled.drawLine(63, 6, 63, 42);


    // (C) Right Half: Blood Oxygen Section (SpO2, X: 64~128, Y: 0~47)
    // Title: Display small font "SpO2" (scale 1) at top-left corner of the right half (X: 70, Y: 6)
    oled.drawStr(70, 6, "SpO2", 1);

    // Value: Convert SPO2 to string and display with large font (scale 2), centered dynamically in the right half, Y-coordinate is 20. If <= 0, display "---"
    char spo2Str[8];
    int o2_len = 0;
    if (SPO2 > 0) {
        sprintf(spo2Str, "%d", SPO2);
        o2_len = strlen(spo2Str);
    } else {
        strcpy(spo2Str, "---");
        o2_len = 3;
    }
    // Right half width is 64px (from X: 64 to 128). Center X = 64 + (64 - width) / 2
    int o2_val_x = 64 + (64 - (o2_len * 12)) / 2;
    oled.drawStr(o2_val_x, 20, spo2Str, 2);

    // Unit: Display small font "%" (scale 1) at fixed position (X: 110, Y: 36) of the right half
    oled.drawStr(110, 36, "%", 1);


    // --- 2. Bottom Yellow Area (Y: 48~63): Real-time Waveform Display ---
    if (isWarmingUp) {
        oled.drawStr(2, 52, "Stabilizing", 1);
    } else {
        wave.scale();
        wave.draw(oled, 0); // Horizontal scroll yellow PPG waveform with left-side 80-pixel width update
    }

    // Always draw cumulative timer on the right side of the bottom yellow area
    char timeStr[8];
    sprintf(timeStr, "%d:%02d", totalFingerSeconds / 60, totalFingerSeconds % 60);
    oled.drawStr(80, 48, timeStr, 2);

}

void DisplayManager::drawWelcome() {
    oled.drawStr(4, 20, "PulseGuard", 2);
    oled.drawStr(19, 40, "Initializing...", 1);
}

void DisplayManager::drawPowerOff(int sleep_counter) {
    int secondsLeft = (100 - sleep_counter) / 5;
    char secStr[8];
    sprintf(secStr, "%d s", secondsLeft);
    int len = strlen(secStr);
    int start_x = (128 - (len * 12)) / 2;
    oled.drawStr(37, 20, "POWER OFF", 1);
    oled.drawStr(start_x, 34, secStr, 2);
}

void DisplayManager::drawWiFiSetup() {
    oled.drawStr(19, 20, AP_NAME, 1);
    String ipStr = WiFi.softAPIP().toString();
    // Calculate centering and display dynamic AP IP
    int start_x = (128 - (ipStr.length() * 6)) / 2;
    if (start_x < 0) start_x = 0;
    oled.drawStr(start_x, 34, ipStr.c_str(), 1);
}

void DisplayManager::drawResetSuccess() {
    oled.drawStr(28, 20, "SYSTEM RESET", 1);
    oled.drawStr(37, 34, "SUCCESS !", 1);
}

void DisplayManager::drawCompletion() {
    oled.drawStr(31, 20, "COMPLETED !", 1);
    oled.drawStr(10, 34, "System Sleeping...", 1);
}

DisplayManager DisplayMgr;

#endif
