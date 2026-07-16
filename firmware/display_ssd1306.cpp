#include "display_manager.h"
#include <WiFi.h>

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
    oled.drawStr(28, 4, "DEVICE ERROR", 1);
    oled.drawStr(19, 18, "Check I2C Wire!", 1);
}

void DisplayManager::drawPlaceFinger() {
    oled.drawStr(28, 4, "PLACE FINGER", 1);
    oled.drawStr(22, 18, "IR Filter: Avg", 1);
}

void DisplayManager::drawMeasuring(int beatAvg, int SPO2, DeviceStatus currentStatus, uint32_t totalFingerSeconds, uint32_t fingerOnStartTime) {
    bool isWarmingUp = (fingerOnStartTime == 0 || (millis() - fingerOnStartTime < STABILIZATION_MS));

    // --- 1. 上方藍色區域（Y: 0~47）：左右對稱雙柱設計 ---

    // (A) 左半部：心率區塊 (HR, X: 0~60, Y: 0~47)
    // 標題：在左上角 (X: 4, Y: 6) 顯示小字體 HR (scale 1)
    oled.drawStr(4, 6, "HR", 1);

    // 數值：將 beatAvg 轉為字串後，以大字體 (scale 2) 顯示，根據長度置中，Y 座標設為 24。若 <= 0 顯示 "---"
    char bpmStr[8];
    int hr_len = 0;
    if (beatAvg > 0) {
        sprintf(bpmStr, "%d", beatAvg);
        hr_len = strlen(bpmStr);
    } else {
        strcpy(bpmStr, "---");
        hr_len = 3;
    }
    // 大字體 (scale 2) 每字寬度為 12px
    int hr_val_x = (60 - (hr_len * 12)) / 2;
    oled.drawStr(hr_val_x, 24, bpmStr, 2);

    // 單位：在左下角固定位置 (X: 4, Y: 38) 顯示小字體 bpm (scale 1)，防止 3 位數時與右側發生重疊
    oled.drawStr(4, 38, "bpm", 1);


    // (B) 中央分隔線
    // 在 X: 63 的位置，使用 oled.drawLine() 畫一條垂直線，Y 座標從 6 到 42，將左右兩邊隔開。
    oled.drawLine(63, 6, 63, 42);


    // (C) 右半部：血氧區塊 (SpO2, X: 66~128, Y: 0~47)
    // 標題：在右半部左上角 (X: 70, Y: 6) 顯示小字體 SpO2 (scale 1)
    oled.drawStr(70, 6, "SpO2", 1);

    // 數值：將 SPO2 轉為字串後，以大字體 (scale 2) 顯示，同樣動態計算 X 座標使其在右半部置中，Y 座標設為 24。若 <= 0 則顯示 "---"
    char spo2Str[8];
    int o2_len = 0;
    if (SPO2 > 0) {
        sprintf(spo2Str, "%d", SPO2);
        o2_len = strlen(spo2Str);
    } else {
        strcpy(spo2Str, "---");
        o2_len = 3;
    }
    // 右半部寬度為 62px (從 X: 66 到 128)，置中 X = 66 + (62 - width) / 2
    int o2_val_x = 66 + (62 - (o2_len * 12)) / 2;
    oled.drawStr(o2_val_x, 24, spo2Str, 2);

    // 單位：在數值的右側顯示小字體 % (scale 1)
    int o2_unit_x = o2_val_x + (o2_len * 12) + 2;
    if (o2_unit_x > 122) o2_unit_x = 122; // 確保不超出 128 螢幕邊界
    oled.drawStr(o2_unit_x, 24, "%", 1);


    // --- 2. 下方黃色區域（Y: 48~63）顯示即時波形 ---
    if (isWarmingUp) {
        oled.drawStr(22, 52, "Stabilizing...", 1);
    } else {
        wave.scale();
        wave.draw(oled, 0); // 橫向滾動黃色心率波形滿畫幅 128 寬度更新
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
    String ipStr = WiFi.softAPIP().toString();
    // 居中計算並顯示動態 AP IP
    int start_x = (128 - (ipStr.length() * 6)) / 2;
    if (start_x < 0) start_x = 0;
    oled.drawStr(start_x, 18, ipStr.c_str(), 1);
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
