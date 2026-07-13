#include "display_manager.h"

// Bitmap resources for icons
static const uint8_t heart_bits[] PROGMEM = { 0x00, 0x00, 0x38, 0x38, 0x7c, 0x7c, 0xfe, 0xfe, 0xfe, 0xff, 0xfe, 0xff, 0xfc, 0x7f, 0xf8, 0x3f, 0xf0, 0x1f, 0xe0, 0x0f, 0xc0, 0x07, 0x80, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
static const uint8_t o2_bits[] PROGMEM = { 0xf8, 0x03, 0x0c, 0x06, 0x06, 0x0c, 0x06, 0x0c, 0x06, 0x0c, 0x06, 0x0c, 0x0c, 0x76, 0xf8, 0x63, 0x00, 0x61, 0x00, 0x30, 0x00, 0x1c, 0x00, 0x7f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };

Waveform::Waveform() : wavep(0) {
    memset(waveform, 128, MAXWAVE);
}

void Waveform::record(int waveval) {
    // Normalization and storage in circular buffer
    waveval = waveval / 8; waveval += 128;
    waveval = waveval < 0 ? 0 : (waveval > 255 ? 255 : waveval);
    waveform[wavep] = (uint8_t)waveval;
    wavep = (wavep + 1) % MAXWAVE;
}

void Waveform::scale() {
    // Find min/max for auto-scaling
    uint8_t maxw = 0; uint8_t minw = 255;
    for (int i = 0; i < MAXWAVE; i++) {
        maxw = waveform[i] > maxw ? waveform[i] : maxw;
        minw = waveform[i] < minw ? waveform[i] : minw;
    }
    uint8_t range = maxw - minw; if (range == 0) range = 1;
    uint8_t index = wavep;
    for (int i = 0; i < MAXWAVE; i++) {
#if (DISPLAY_TYPE == TFT_ST7735)
        // Map samples to display height (16 to 70 Y-axis)
        disp_wave[i] = 70 - ((uint16_t)(waveform[index] - minw) * 50) / range;
#else
        // Map samples to OLED display height (for y in 2 to 30)
        disp_wave[i] = 30 - ((uint16_t)(waveform[index] - minw) * 28) / range;
#endif
        index = (index + 1) % MAXWAVE;
    }
}

#if (DISPLAY_TYPE == TFT_ST7735)
void Waveform::draw(Adafruit_ST7735 &tft, uint8_t X) {
    tft.fillRect(X, 16, MAXWAVE, 59, ST7735_BLACK);
    for (int i = 0; i < MAXWAVE - 1; i++) {
        tft.drawLine(X + i, disp_wave[i], X + i + 1, disp_wave[i + 1], ST7735_GREEN);
    }
}
#else
void Waveform::draw(SSD1306 &oled, uint8_t X) {
    for (int i = 0; i < MAXWAVE - 1; i++) {
        oled.drawLine(X + i, disp_wave[i], X + i + 1, disp_wave[i + 1]);
    }
}
#endif

void Waveform::clear() {
    wavep = 0;
    memset(waveform, 128, MAXWAVE);
}

#if (DISPLAY_TYPE == TFT_ST7735)
DisplayManager::DisplayManager() :
    tft(TFT_CS, TFT_DC, TFT_RST),
    last_msg(-1),
    last_printed_bpm(-1),
    last_printed_spo2(-1),
    last_printed_seconds(-1),
    last_printed_status(-1),
    lastWarmingUpState(false),
    lastWarmUpDraw(0) {}
#else
DisplayManager::DisplayManager() :
    last_msg(-1),
    last_printed_bpm(-1),
    last_printed_spo2(-1),
    last_printed_seconds(-1),
    last_printed_status(-1),
    lastWarmingUpState(false),
    lastWarmUpDraw(0) {}
#endif

void DisplayManager::begin() {
#if (DISPLAY_TYPE == TFT_ST7735)
    pinMode(TFT_BLK, OUTPUT);
    digitalWrite(TFT_BLK, HIGH);
    tft.initR(INITR_BLACKTAB);
    tft.setRotation(1); // Landscape mode
    tft.fillScreen(ST7735_BLACK);
#else
    oled.init();
    oled.fill(0x00);
#endif
}

void DisplayManager::enableDisplay(bool enable) {
#if (DISPLAY_TYPE == TFT_ST7735)
    tft.enableDisplay(enable);
    digitalWrite(TFT_BLK, enable ? HIGH : LOW);
#else
    if (enable) oled.on();
    else oled.off();
#endif
}

void DisplayManager::fillScreen(uint16_t color) {
#if (DISPLAY_TYPE == TFT_ST7735)
    tft.fillScreen(color);
#else
    oled.fill(0x00);
#endif
}

void DisplayManager::recordWaveform(int waveval) {
    wave.record(waveval);
}

void DisplayManager::clearWaveform() {
    wave.clear();
}

void DisplayManager::updateScreen(int msg, int beatAvg, int SPO2, DeviceStatus currentStatus, uint32_t totalFingerSeconds, uint32_t fingerOnStartTime) {
#if (DISPLAY_TYPE == TFT_ST7735)
    // If the message mode changed, clear screen and draw static layouts
    if (msg != last_msg) {
        tft.fillScreen(ST7735_BLACK);
        last_msg = msg;
        last_printed_bpm = -1;
        last_printed_spo2 = -1;
        last_printed_seconds = -1;
        last_printed_status = -1;
        if (msg == 2) { // Measuring screen Layout
            tft.fillRect(0, 0, 160, 15, ST7735_BLACK);
            tft.drawFastHLine(0, 15, 160, ST7735_WHITE);
            tft.drawFastHLine(0, 75, 160, ST7735_WHITE);
            tft.drawFastVLine(80, 75, 53, ST7735_WHITE);
            tft.drawXBitmap(21, 110, heart_bits, 16, 16, ST7735_RED);
            tft.setTextSize(1);
            tft.setTextColor(ST7735_RED, ST7735_BLACK);
            tft.setCursor(21 + 16 + 4, 114); tft.print(F("BPM"));
            tft.drawXBitmap(107, 110, o2_bits, 16, 16, ST7735_CYAN);
            tft.setTextSize(1); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            tft.setCursor(107 + 16 + 4, 114); tft.print(F("%"));
        }
    }

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
#else // OLED_SSD1306
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
#endif
}

void DisplayManager::drawDeviceError() {
#if (DISPLAY_TYPE == TFT_ST7735)
    int16_t x1, y1; uint16_t w, h;
    tft.setTextSize(2); tft.setTextColor(ST7735_RED, ST7735_BLACK);
    const char* err = "DEVICE ERROR";
    tft.getTextBounds(err, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 45); tft.print(err);

    tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
    const char* msg2 = "Check I2C Wire!";
    tft.getTextBounds(msg2, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 75); tft.print(msg2);
#else
    // "DEVICE ERROR" length: 12 chars -> 12 * 6 = 72 pixels. Centered at x = 28.
    oled.drawStr(28, 4, "DEVICE ERROR", 1);
    // "Check I2C Wire!" length: 15 chars -> 15 * 6 = 90 pixels. Centered at x = 19.
    oled.drawStr(19, 18, "Check I2C Wire!", 1);
#endif
}

void DisplayManager::drawPlaceFinger() {
#if (DISPLAY_TYPE == TFT_ST7735)
    int16_t x1, y1; uint16_t w, h;
    tft.setTextSize(2); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
    const char* p1 = "PLACE";
    tft.getTextBounds(p1, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 40); tft.print(p1);

    const char* p2 = "FINGER";
    tft.getTextBounds(p2, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 65); tft.print(p2);

    tft.fillRect(0, 108, 160, 20, ST7735_BLACK);
    tft.setTextSize(1); tft.setTextColor(ST7735_GREEN, ST7735_BLACK);
    const char* mode = "Mode: IR Filter: Avg";
    tft.getTextBounds(mode, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 113); tft.print(mode);
#else
    // "PLACE FINGER" length: 12 chars -> 12 * 6 = 72 pixels. Centered at x = 28.
    oled.drawStr(28, 4, "PLACE FINGER", 1);
    // "IR Filter: Avg" length: 14 chars -> 14 * 6 = 84 pixels. Centered at x = 22.
    oled.drawStr(22, 18, "IR Filter: Avg", 1);
#endif
}

void DisplayManager::drawMeasuring(int beatAvg, int SPO2, DeviceStatus currentStatus, uint32_t totalFingerSeconds, uint32_t fingerOnStartTime) {
    bool isWarmingUp = (fingerOnStartTime == 0 || (millis() - fingerOnStartTime < STABILIZATION_MS));

#if (DISPLAY_TYPE == TFT_ST7735)
    if (isWarmingUp) {
        // Show "Stabilizing" message instead of waveform during warm-up
        if (!lastWarmingUpState || last_printed_status == -1 || (millis() - lastWarmUpDraw > 500)) {
            tft.fillRect(0, 16, MAXWAVE, 59, ST7735_BLACK);
            tft.drawFastHLine(0, 45, MAXWAVE, ST7735_GREEN);
            tft.setTextSize(1);
            tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            tft.setCursor(40, 38);
            tft.print("Stabilizing...");
            lastWarmUpDraw = millis();
        }
    } else {
        // Show PPG waveform once stabilized
        if (lastWarmingUpState || last_printed_status == -1) {
            tft.fillRect(0, 16, MAXWAVE, 59, ST7735_BLACK);
        }
        wave.scale();
        wave.draw(tft, 0);
    }
    lastWarmingUpState = isWarmingUp;

    drawHeader(currentStatus, totalFingerSeconds);
    drawData(beatAvg, SPO2);
#else // OLED_SSD1306
    if (isWarmingUp) {
        // Draw "Stabilizing..." centered in OLED screen
        oled.drawStr(22, 12, "Stabilizing...", 1);
    } else {
        // Draw real-time PPG waveform once stabilized in columns 42 to 85.
        wave.scale();
        wave.draw(oled, 42);
    }

    // Draw Heart Rate (BPM) on the left (x=2)
    oled.drawStr(2, 2, "HR", 1);
    if (beatAvg > 0) {
        char bpmStr[8];
        sprintf(bpmStr, "%d", beatAvg);
        oled.drawStr(2, 12, bpmStr, 2);
    } else {
        oled.drawStr(2, 12, "---", 2);
    }

    // Draw SpO2 on the right (x=88)
    oled.drawStr(88, 2, "O2", 1);
    if (SPO2 > 0) {
        char spo2Str[8];
        sprintf(spo2Str, "%d", SPO2);
        oled.drawStr(88, 12, spo2Str, 2);
    } else {
        oled.drawStr(88, 12, "---", 2);
    }
#endif
}

#if (DISPLAY_TYPE == TFT_ST7735)
void DisplayManager::drawHeader(DeviceStatus currentStatus, uint32_t totalFingerSeconds) {
    // Only update if state changed to avoid flicker
    if ((int)currentStatus != last_printed_status || (int)totalFingerSeconds != last_printed_seconds) {
        tft.setTextSize(1);
        if ((int)currentStatus != last_printed_status) {
            last_printed_status = (int)currentStatus;
            tft.fillRect(0, 0, 110, 15, ST7735_BLACK);
            uint16_t dotColor = ST7735_GREEN;
            const char* statusStr = "NORMAL";
            if (currentStatus == STATUS_WARNING) { dotColor = ST7735_YELLOW; statusStr = "WARNING"; }
            else if (currentStatus == STATUS_DANGER) { dotColor = ST7735_RED; statusStr = "DANGER"; }
            tft.fillCircle(8, 7, 3, dotColor);
            tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
            tft.setCursor(18, 4); tft.print(statusStr);
        }

        if ((int)totalFingerSeconds != last_printed_seconds) {
            last_printed_seconds = (int)totalFingerSeconds;
            tft.fillRect(120, 0, 40, 15, ST7735_BLACK);
            int mins = totalFingerSeconds / 60;
            int secs = totalFingerSeconds % 60;
            tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
            tft.setCursor(125, 4);
            if (mins < 10) tft.print('0'); tft.print(mins); tft.print(':');
            if (secs < 10) tft.print('0'); tft.print(secs);
        }
    }
}

void DisplayManager::drawData(int beatAvg, int SPO2) {
    // Redraw BPM only if value changed
    if (beatAvg != last_printed_bpm) {
        last_printed_bpm = beatAvg;
        tft.fillRect(5, 82, 70, 24, ST7735_BLACK);
        tft.setTextSize(3); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
        if (beatAvg > 0) {
            int numDigits = (beatAvg < 10) ? 1 : ((beatAvg < 100) ? 2 : 3);
            int numX = (80 - (numDigits * 18)) / 2;
            tft.setCursor(numX, 82); tft.print(beatAvg);
        } else {
            tft.setCursor((80 - 54) / 2, 82); tft.print(F("---"));
        }
    }

    // Redraw SpO2 only if value changed
    if (SPO2 != last_printed_spo2) {
        last_printed_spo2 = SPO2;
        tft.fillRect(85, 82, 70, 24, ST7735_BLACK);
        tft.setTextSize(3); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
        if (SPO2 > 0) {
            int numDigits = (SPO2 < 10) ? 1 : ((SPO2 < 100) ? 2 : 3);
            int numX = 80 + (80 - (numDigits * 18)) / 2;
            tft.setCursor(numX, 82); tft.print(SPO2);
        } else {
            tft.setCursor(80 + (80 - 54) / 2, 82); tft.print(F("---"));
        }
    }
}
#endif

void DisplayManager::drawWelcome() {
#if (DISPLAY_TYPE == TFT_ST7735)
    int16_t x1, y1; uint16_t w, h;
    tft.drawXBitmap(72, 12, heart_bits, 16, 16, ST7735_RED);

    tft.setTextSize(2); tft.setTextColor(ST7735_CYAN, ST7735_BLACK);
    const char* title = "PulseGuard";
    tft.getTextBounds(title, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 35); tft.print(title);

    tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
    const char* line1 = "Heart Rate &";
    tft.getTextBounds(line1, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 65); tft.print(line1);

    const char* line2 = "SpO2 Monitor";
    tft.getTextBounds(line2, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 80); tft.print(line2);

    tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
    const char* initText = "Initializing...";
    tft.getTextBounds(initText, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 105); tft.print(initText);
#else
    // Center "PulseGuard" BIG=2
    // Length: 10 chars -> width = 10 * 12 = 120 pixels. Centered at x = 4.
    oled.drawStr(4, 2, "PulseGuard", 2);
    // Center "Initializing..." BIG=1
    // Length: 15 chars -> width = 15 * 6 = 90 pixels. Centered at x = 19.
    oled.drawStr(19, 22, "Initializing...", 1);
#endif
}

void DisplayManager::drawPowerOff(int sleep_counter) {
    int secondsLeft = (100 - sleep_counter) / 5;
#if (DISPLAY_TYPE == TFT_ST7735)
    int16_t x1, y1; uint16_t w, h;
    tft.setTextSize(2); tft.setTextColor(ST7735_RED, ST7735_BLACK);
    const char* po = "POWER OFF";
    tft.getTextBounds(po, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 40); tft.print(po);

    tft.fillRect(0, 75, 160, 32, ST7735_BLACK);
    tft.setTextSize(4); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
    char secStr[4]; sprintf(secStr, "%d", secondsLeft);
    tft.getTextBounds(secStr, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 75); tft.print(secStr);
#else
    // "POWER OFF" length: 9 chars -> 9 * 6 = 54 pixels. Centered at x = 37.
    oled.drawStr(37, 2, "POWER OFF", 1);
    // Large countdown digit BIG=2. Length: 1-2 chars -> width = 12..24. Centered at x = 58 or 52.
    char secStr[8];
    sprintf(secStr, "%d s", secondsLeft);
    int len = strlen(secStr);
    int start_x = (128 - (len * 12)) / 2;
    oled.drawStr(start_x, 14, secStr, 2);
#endif
}

void DisplayManager::drawWiFiSetup() {
#if (DISPLAY_TYPE == TFT_ST7735)
    int16_t x1, y1; uint16_t w, h;
    tft.setTextSize(2); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
    const char* title = "WIFI SETUP";
    tft.getTextBounds(title, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 25); tft.print(title);

    tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
    const char* l1 = "Please connect to AP:";
    tft.getTextBounds(l1, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 55); tft.print(l1);

    tft.setTextColor(ST7735_GREEN, ST7735_BLACK);
    tft.getTextBounds(AP_NAME, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 75); tft.print(AP_NAME);

    tft.setTextColor(ST7735_CYAN, ST7735_BLACK);
    const char* l2 = "IP: 192.168.4.1";
    tft.getTextBounds(l2, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 100); tft.print(l2);
#else
    // "PulseGuard-IoT" length: 15 chars -> 15 * 6 = 90 pixels. Centered at x = 19.
    oled.drawStr(19, 4, AP_NAME, 1);
    // "192.168.4.1" length: 11 chars -> 11 * 6 = 66 pixels. Centered at x = 31.
    oled.drawStr(31, 18, "192.168.4.1", 1);
#endif
}

void DisplayManager::drawResetSuccess() {
#if (DISPLAY_TYPE == TFT_ST7735)
    int16_t x1, y1; uint16_t w, h;
    tft.setTextSize(2); tft.setTextColor(ST7735_GREEN, ST7735_BLACK);
    const char* m1 = "SYSTEM RESET";
    tft.getTextBounds(m1, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 45); tft.print(m1);

    tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
    const char* m2 = "SUCCESS !";
    tft.getTextBounds(m2, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 75); tft.print(m2);
#else
    // "SYSTEM RESET" length: 12 chars -> 12 * 6 = 72 pixels. Centered at x = 28.
    oled.drawStr(28, 4, "SYSTEM RESET", 1);
    // "SUCCESS !" length: 9 chars -> 9 * 6 = 54 pixels. Centered at x = 37.
    oled.drawStr(37, 18, "SUCCESS !", 1);
#endif
}

void DisplayManager::drawCompletion() {
#if (DISPLAY_TYPE == TFT_ST7735)
    tft.setTextSize(2); tft.setTextColor(ST7735_CYAN, ST7735_BLACK);
    tft.setCursor(15, 45); tft.print("COMPLETED !");

    tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
    tft.setCursor(30, 85); tft.print("System Sleeping...");
#else
    // "COMPLETED !" length: 11 chars -> 11 * 6 = 66 pixels. Centered at x = 31.
    oled.drawStr(31, 4, "COMPLETED !", 1);
    // "System Sleeping..." length: 18 chars -> 18 * 6 = 108 pixels. Centered at x = 10.
    oled.drawStr(10, 18, "System Sleeping...", 1);
#endif
}

DisplayManager DisplayMgr;
