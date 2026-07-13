#ifndef PERIPHERALS_H
#define PERIPHERALS_H

#include <Arduino.h>
#include "config.h"

/**
 * @class Peripherals
 * @brief Manages non-blocking interaction with hardware peripherals (Button, Buzzer, LED) and Power Management.
 */
class Peripherals {
public:
    Peripherals();

    /**
     * @brief Initializes GPIO pins for peripherals.
     */
    void begin();

    /**
     * @brief Periodic update function for non-blocking debouncing and buzzer timing.
     */
    void update();

    /**
     * @brief Checks if a short press was detected. Clears the flag on read.
     */
    bool isShortPressDetected();

    /**
     * @brief Checks if a long press (>= 2s) was detected. Clears the flag on read.
     */
    bool isLongPressDetected();

    /**
     * @brief Schedules a sequence of beeps.
     * @param count Number of beeps to play.
     */
    void triggerBeeps(int count);

    /**
     * @brief Enters Deep Sleep mode with Button as wakeup source.
     */
    void goSleep();

    /**
     * @brief Controls the onboard heart rate indicator LED.
     */
    void setLed(bool on);

#if (DISPLAY_TYPE == OLED_SSD1306)
    /**
     * @brief Sets the displayed time on the 4-digit 7-segment display.
     */
    void setSegmentTime(uint32_t totalSeconds);

    /**
     * @brief Enables or disables the 4-digit 7-segment display multiplexing.
     */
    void enableSegmentDisplay(bool enable);

    /**
     * @brief Performs one multiplexing step.
     */
    void refreshSegments();
#endif

private:
    // Button state machine
    bool lastButtonState;
    unsigned long buttonPressStart;
    bool shortPressFlag;
    bool longPressFlag;
    bool longPressHandled;

    // Buzzer non-blocking timer
    int beepsToPlay;
    bool isBuzzerOn;
    uint32_t lastBuzzerToggleTime;

#if (DISPLAY_TYPE == OLED_SSD1306)
    // 7-segment display state
    bool segmentDisplayEnabled;
    uint8_t segmentDigits[4];
#endif

    void updateButton();
    void updateBuzzer();
};

extern Peripherals Periph;

#endif // PERIPHERALS_H
