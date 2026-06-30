#ifndef PERIPHERALS_H
#define PERIPHERALS_H

#include <Arduino.h>
#include "config.h"

class Peripherals {
public:
    Peripherals();
    void begin();
    void update();

    // Button states
    bool isShortPressDetected();
    bool isLongPressDetected();

    // Buzzer control
    void triggerBeeps(int count);

    // Power management
    void goSleep();
    void setLed(bool on);

private:
    bool lastButtonState;
    unsigned long buttonPressStart;
    bool shortPressFlag;
    bool longPressFlag;
    bool longPressHandled;

    int beepsToPlay;
    bool isBuzzerOn;
    uint32_t lastBuzzerToggleTime;

    void updateButton();
    void updateBuzzer();
};

extern Peripherals Periph;

#endif // PERIPHERALS_H
