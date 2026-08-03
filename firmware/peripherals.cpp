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
    lastBuzzerToggleTime(0)
{
}

void Peripherals::begin() {
    pinMode(LED, OUTPUT);
    pinMode(BUTTON, INPUT_PULLUP);
    pinMode(BUZZER_PIN, OUTPUT);
    noTone(BUZZER_PIN);

#if (DISPLAY_TYPE == OLED_SSD1306)
    pinMode(LED_RED, OUTPUT);
    pinMode(LED_YELLOW, OUTPUT);
    pinMode(LED_GREEN, OUTPUT);
    digitalWrite(LED_RED, LOW);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_GREEN, LOW);
#endif
}

void Peripherals::update() {
    updateButton();
    updateBuzzer();
}

void Peripherals::updateButton() {
    bool currentButtonState = digitalRead(BUTTON);
    unsigned long now = millis();

    if (lastButtonState == HIGH && currentButtonState == LOW) {
        // Button Pressed
        buttonPressStart = now;
        longPressHandled = false;
    }
    else if (lastButtonState == LOW && currentButtonState == HIGH) {
        // Button Released
        unsigned long pressDuration = now - buttonPressStart;
        if (!longPressHandled && pressDuration >= DEBOUNCE_TIME && pressDuration < LONG_PRESS_TIME) {
            shortPressFlag = true;
        }
        buttonPressStart = 0;
    }

    // Continuous check for long press
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
            // Turning off after BEEP_ON_TIME
            if (timePassed >= BEEP_ON_TIME) {
                noTone(BUZZER_PIN);
                isBuzzerOn = false;
                lastBuzzerToggleTime = now;
                beepsToPlay--;
            }
        } else {
            // Turning on after BEEP_OFF_TIME
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
    // 1. UI Feedback & status LEDs shutdown
#if (DISPLAY_TYPE == OLED_SSD1306)
    digitalWrite(LED_GREEN, LOW);
    digitalWrite(LED_YELLOW, LOW);
    digitalWrite(LED_RED, LOW);
    pinMode(LED_GREEN, INPUT);
    pinMode(LED_YELLOW, INPUT);
    pinMode(LED_RED, INPUT);
#endif

    DisplayMgr.fillScreen(0); // Pass 0 (Black) so it is independent of specific TFT/OLED color macros
    DisplayMgr.enableDisplay(false);
    noTone(BUZZER_PIN);

    // 2. Peripheral Shutdown
    delay(10);
    SensorProc.sensorOff();
    delay(10);

    // 3. Configure Sleep Parameters
    pinMode(0, INPUT); // Disable specific pins to save power
    pinMode(2, INPUT);
    esp_sleep_enable_ext0_wakeup((gpio_num_t)BUTTON, 0); // Wake up when button is pulled LOW

    // 4. Enter Deep Sleep
    esp_deep_sleep_start();
}

#if (DISPLAY_TYPE == OLED_SSD1306)
void Peripherals::updateStatusLeds(DeviceStatus status, bool isMeasuring) {
    if (!isMeasuring) {
        digitalWrite(LED_GREEN, LOW);
        digitalWrite(LED_YELLOW, LOW);
        digitalWrite(LED_RED, LOW);
        return;
    }
    digitalWrite(LED_GREEN, (status == STATUS_NORMAL) ? HIGH : LOW);
    digitalWrite(LED_YELLOW, (status == STATUS_WARNING) ? HIGH : LOW);
    digitalWrite(LED_RED, (status == STATUS_DANGER) ? HIGH : LOW);
}
#endif

Peripherals Periph;
