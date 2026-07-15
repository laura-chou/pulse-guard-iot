#include "display_manager.h"

#if (DISPLAY_TYPE == OLED_SSD1306)

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
        // Map samples to height range Y: 2~45 for the top blue area (Y: 0~47)
        disp_wave[i] = 45 - ((uint16_t)(waveform[index] - minw) * 43) / range;
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
    oled.drawStr(28, 4, "DEVICE ERROR", 1);
    oled.drawStr(19, 18, "Check I2C Wire!", 1);
}

void DisplayManager::drawPlaceFinger() {
    oled.drawStr(28, 4, "PLACE FINGER", 1);
    oled.drawStr(22, 18, "IR Filter: Avg", 1);
}

void DisplayManager::drawMeasuring(int beatAvg, int SPO2, DeviceStatus currentStatus, uint32_t totalFingerSeconds, uint32_t fingerOnStartTime) {
    bool isWarmingUp = (fingerOnStartTime == 0 || (millis() - fingerOnStartTime < STABILIZATION_MS));

    // 1. 上方藍色區域（Y: 0~47）
    if (isWarmingUp) {
        oled.drawStr(22, 20, "Stabilizing...", 1);
    } else {
        wave.scale();
        wave.draw(oled, 0); // 橫向滾動心率波形滿畫幅 128 寬度更新
    }

    // 2. 下方黃色區域（Y: 48~63）並排顯示「HR: [數值] bpm」與「SpO2: [數值]%」
    // 左半部 - HR: [數值] bpm
    oled.drawStr(2, 52, "HR:", 1);
    if (beatAvg > 0) {
        char bpmStr[8];
        sprintf(bpmStr, "%d", beatAvg);
        oled.drawStr(20, 48, bpmStr, 2); // 數值使用 BIG=2 高度 16px 填滿黃色區塊
        if (beatAvg >= 100) {
            oled.drawStr(56, 52, "bpm", 1);
        } else {
            oled.drawStr(44, 52, "bpm", 1);
        }
    } else {
        oled.drawStr(20, 48, "---", 2);
        oled.drawStr(56, 52, "bpm", 1);
    }

    // 右半部 - SpO2: [數值]%
    int spo2_x = (beatAvg >= 100) ? 72 : 68; // 動態微調以避免 3位數 HR 與 SpO2 重疊
    oled.drawStr(spo2_x, 52, "SpO2:", 1);
    if (SPO2 > 0) {
        char spo2Str[8];
        sprintf(spo2Str, "%d", SPO2);
        int val_x = spo2_x + 30;
        if (val_x + 24 > 122) val_x = 122 - 24; // 邊界限幅
        oled.drawStr(val_x, 48, spo2Str, 2);    // 數值使用 BIG=2 高度 16px 填滿黃色區塊

        int pct_x = val_x + (SPO2 == 100 ? 36 : 24);
        if (pct_x > 122) pct_x = 122; // 確保百分比符號不會超出螢幕邊界
        oled.drawStr(pct_x, 52, "%", 1);
    } else {
        oled.drawStr(spo2_x + 30, 48, "---", 2);
        oled.drawStr(spo2_x + 54, 52, "%", 1);
    }
}

void DisplayManager::drawWelcome() {
    oled.drawStr(4, 2, "PulseGuard", 2);
    oled.drawStr(19, 22, "Initializing...", 1);
}

void DisplayManager::drawPowerOff(int sleep_counter) {
    int secondsLeft = (100 - sleep_counter) / 5;
    char secStr[8];
    sprintf(secStr, "%d s", secondsLeft);
    int len = strlen(secStr);
    int start_x = (128 - (len * 12)) / 2;
    oled.drawStr(37, 2, "POWER OFF", 1);
    oled.drawStr(start_x, 14, secStr, 2);
}

void DisplayManager::drawWiFiSetup() {
    oled.drawStr(19, 4, AP_NAME, 1);
    oled.drawStr(31, 18, "192.168.4.1", 1);
}

void DisplayManager::drawResetSuccess() {
    oled.drawStr(28, 4, "SYSTEM RESET", 1);
    oled.drawStr(37, 18, "SUCCESS !", 1);
}

void DisplayManager::drawCompletion() {
    oled.drawStr(31, 4, "COMPLETED !", 1);
    oled.drawStr(10, 18, "System Sleeping...", 1);
}

DisplayManager DisplayMgr;

#endif
