#ifndef DISPLAY_MANAGER_H
#define DISPLAY_MANAGER_H

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#include "config.h"

#define MAXWAVE 160 // Screen width for waveform

/**
 * @class Waveform
 * @brief Manages the buffer and rendering of the real-time PPG waveform.
 */
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

/**
 * @class DisplayManager
 * @brief Handles all UI rendering for the ST7735 display.
 */
class DisplayManager {
public:
    DisplayManager();

    /**
     * @brief Initializes the display and backlight.
     */
    void begin();

    /**
     * @brief Updates the screen content based on the message ID and current sensor data.
     * @param msg Message ID (0: Error, 1: Place Finger, 2: Measuring, 3: Welcome, 4: Sleep, 5: WiFi, 6: Reset, 7: Done)
     */
    void updateScreen(int msg, int beatAvg, int SPO2, DeviceStatus currentStatus, uint32_t totalFingerSeconds, uint32_t fingerOnStartTime);

    /**
     * @brief Records a raw sample into the waveform buffer.
     */
    void recordWaveform(int waveval);

    /**
     * @brief Resets the waveform buffer.
     */
    void clearWaveform();

    /**
     * @brief Toggles the display power and backlight.
     */
    void enableDisplay(bool enable);

    /**
     * @brief Fills the entire screen with a specific color.
     */
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

    // Sub-renderers for different screens
    void drawDeviceError();
    void drawPlaceFinger();
    void drawMeasuring(int beatAvg, int SPO2, DeviceStatus currentStatus, uint32_t totalFingerSeconds, uint32_t fingerOnStartTime);
    void drawWelcome();
    void drawPowerOff(int sleep_counter);
    void drawWiFiSetup();
    void drawResetSuccess();
    void drawCompletion();

    // UI components for Measuring screen
    void drawHeader(DeviceStatus currentStatus, uint32_t totalFingerSeconds);
    void drawData(int beatAvg, int SPO2);
};

extern DisplayManager DisplayMgr;

#endif // DISPLAY_MANAGER_H
