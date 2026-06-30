#include "peripherals.h"
#include "sensor_processor.h"
#include "display_manager.h"

Peripherals::Peripherals() :
    lastButtonState(HIGH),
    buttonPressStart(0),
    shortPressFlag(false),
    longPressFlag(false),
    longPressHandled(false),
    beepsToPlay(0),
    isBuzzerOn(false),
    lastBuzzerToggleTime(0) {}

void Peripherals::begin() {
    pinMode(LED, OUTPUT);
    pinMode(BUTTON, INPUT_PULLUP);
    pinMode(BUZZER_PIN, OUTPUT);
    noTone(BUZZER_PIN);
}

void Peripherals::update() {
    updateButton();
    updateBuzzer();
}

void Peripherals::updateButton() {
    bool currentButtonState = digitalRead(BUTTON);
    unsigned long now = millis();

    if (lastButtonState == HIGH && currentButtonState == LOW) {
        buttonPressStart = now;
        longPressHandled = false;
    }
    else if (lastButtonState == LOW && currentButtonState == HIGH) {
        unsigned long pressDuration = now - buttonPressStart;
        if (!longPressHandled && pressDuration >= DEBOUNCE_TIME && pressDuration < LONG_PRESS_TIME) {
            shortPressFlag = true;
        }
        buttonPressStart = 0;
    }

    if (currentButtonState == LOW && buttonPressStart > 0 && !longPressHandled) {
        if (now - buttonPressStart >= LONG_PRESS_TIME) {
            longPressFlag = true;
            longPressHandled = true;
        }
    }
    lastButtonState = currentButtonState;
}

void Peripherals::updateBuzzer() {
    unsigned long now = millis();
    if (beepsToPlay > 0) {
        uint32_t timePassed = now - lastBuzzerToggleTime;
        if (isBuzzerOn) {
            if (timePassed >= BEEP_ON_TIME) {
                noTone(BUZZER_PIN);
                isBuzzerOn = false;
                lastBuzzerToggleTime = now;
                beepsToPlay--;
            }
        } else {
            if (timePassed >= BEEP_OFF_TIME && beepsToPlay > 0) {
                tone(BUZZER_PIN, BEEP_FREQ);
                isBuzzerOn = true;
                lastBuzzerToggleTime = now;
            }
        }
    } else {
        noTone(BUZZER_PIN);
    }
}

bool Peripherals::isShortPressDetected() {
    bool temp = shortPressFlag;
    shortPressFlag = false;
    return temp;
}

bool Peripherals::isLongPressDetected() {
    bool temp = longPressFlag;
    longPressFlag = false;
    return temp;
}

void Peripherals::triggerBeeps(int count) {
    beepsToPlay = count;
    if (beepsToPlay > 0 && !isBuzzerOn) {
        tone(BUZZER_PIN, BEEP_FREQ);
        isBuzzerOn = true;
        lastBuzzerToggleTime = millis();
    }
}

void Peripherals::setLed(bool on) {
    digitalWrite(LED, on ? HIGH : LOW);
}

void Peripherals::goSleep() {
    DisplayMgr.fillScreen(ST7735_BLACK);
    DisplayMgr.enableDisplay(false);
    noTone(BUZZER_PIN);

    delay(10);
    SensorProc.sensorOff();
    delay(10);

    pinMode(0, INPUT);
    pinMode(2, INPUT);
    esp_sleep_enable_ext0_wakeup((gpio_num_t)BUTTON, 0);
    esp_deep_sleep_start();
}

Peripherals Periph;
