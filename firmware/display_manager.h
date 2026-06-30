#ifndef DISPLAY_MANAGER_H
#define DISPLAY_MANAGER_H

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#include "config.h"

#define MAXWAVE 160

class Waveform {
public:
    Waveform();
    void record(int waveval);
    void scale();
    void draw(Adafruit_ST7735 &tft, uint8_t X);
    void clear();

private:
    uint8_t waveform[MAXWAVE];
    uint8_t disp_wave[MAXWAVE];
    uint8_t wavep;
};

class DisplayManager {
public:
    DisplayManager();
    void begin();
    void updateScreen(int msg, int beatAvg, int SPO2, DeviceStatus currentStatus, uint32_t totalFingerSeconds, uint32_t fingerOnStartTime);
    void recordWaveform(int waveval);
    void clearWaveform();
    void enableDisplay(bool enable);
    void fillScreen(uint16_t color);

private:
    Adafruit_ST7735 tft;
    Waveform wave;
    int last_msg;
    int last_printed_bpm;
    int last_printed_spo2;
    int last_printed_seconds;
    int last_printed_status;
    bool lastWarmingUpState;
    unsigned long lastWarmUpDraw;

    void drawDeviceError();
    void drawPlaceFinger();
    void drawMeasuring(int beatAvg, int SPO2, DeviceStatus currentStatus, uint32_t totalFingerSeconds, uint32_t fingerOnStartTime);
    void drawWelcome();
    void drawPowerOff(int sleep_counter);
    void drawWiFiSetup();
    void drawResetSuccess();
    void drawCompletion();

    void drawHeader(DeviceStatus currentStatus, uint32_t totalFingerSeconds);
    void drawData(int beatAvg, int SPO2);
};

extern DisplayManager DisplayMgr;

#endif // DISPLAY_MANAGER_H
