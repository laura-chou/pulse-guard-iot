#include "peripherals.h"
#include "sensor_processor.h"
#include "display_manager.h"

#if (DISPLAY_TYPE == OLED_SSD1306)
// Common Cathode segment mapping for numbers 0-9
// DP, G, F, E, D, C, B, A order (with DP as MSB, A as LSB)
static const uint8_t segment_map[] = {
    0x3F, // 0
    0x06, // 1
    0x5B, // 2
    0x4F, // 3
    0x66, // 4
    0x6D, // 5
    0x7D, // 6
    0x07, // 7
    0x7F, // 8
    0x6F  // 9
};

static const uint8_t segmentPins[] = { SEG_A, SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G, SEG_DP };
static const uint8_t digitPins[] = { DIG_1, DIG_2, DIG_3, DIG_4 };

// FreeRTOS task function for multiplexing the 7-segment display
static void segmentMuxTask(void *pvParameters) {
    while (true) {
        Periph.refreshSegments();
        vTaskDelay(pdMS_TO_TICKS(3)); // Refresh each digit every 3ms
    }
}
#endif

Peripherals::Peripherals() :
    lastButtonState(HIGH),
    buttonPressStart(0),
    shortPressFlag(false),
    longPressFlag(false),
    longPressHandled(false),
    beepsToPlay(0),
    isBuzzerOn(false),
    lastBuzzerToggleTime(0)
#if (DISPLAY_TYPE == OLED_SSD1306)
    , segmentDisplayEnabled(false)
#endif
{
#if (DISPLAY_TYPE == OLED_SSD1306)
    memset(segmentDigits, 0, sizeof(segmentDigits));
#endif
}

void Peripherals::begin() {
    pinMode(LED, OUTPUT);
    pinMode(BUTTON, INPUT_PULLUP);
    pinMode(BUZZER_PIN, OUTPUT);
    noTone(BUZZER_PIN);

#if (DISPLAY_TYPE == OLED_SSD1306)
    // Initialize segment and digit pins as OUTPUT
    for (int i = 0; i < 8; i++) {
        pinMode(segmentPins[i], OUTPUT);
        digitalWrite(segmentPins[i], LOW); // Turn off all segments
    }
    for (int i = 0; i < 4; i++) {
        pinMode(digitPins[i], OUTPUT);
        digitalWrite(digitPins[i], HIGH); // Turn off all digits (Common Cathode: HIGH is OFF)
    }

    // Create background task for multiplexing
    xTaskCreate(
        segmentMuxTask,
        "SegmentMux",
        1024,
        NULL,
        1,
        NULL
    );
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
    // 1. UI Feedback & segment shutdown
#if (DISPLAY_TYPE == OLED_SSD1306)
    enableSegmentDisplay(false);
    // Set segment and digit pins to INPUT to minimize current leakage during deep sleep
    for (int i = 0; i < 8; i++) {
        pinMode(segmentPins[i], INPUT);
    }
    for (int i = 0; i < 4; i++) {
        pinMode(digitPins[i], INPUT);
    }
#endif

    DisplayMgr.fillScreen(ST7735_BLACK);
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
void Peripherals::setSegmentTime(uint32_t totalSeconds) {
    uint32_t mins = totalSeconds / 60;
    uint32_t secs = totalSeconds % 60;

    segmentDigits[0] = segment_map[(mins / 10) % 10];
    segmentDigits[1] = segment_map[mins % 10];
    segmentDigits[2] = segment_map[(secs / 10) % 10];
    segmentDigits[3] = segment_map[secs % 10];

    // Enable the central colon / DP on Digit 2
    segmentDigits[1] |= 0x80;
}

void Peripherals::enableSegmentDisplay(bool enable) {
    segmentDisplayEnabled = enable;
    if (!enable) {
        memset(segmentDigits, 0, sizeof(segmentDigits));
        // Force all digits off immediately
        for (int i = 0; i < 4; i++) {
            digitalWrite(digitPins[i], HIGH);
        }
    }
}

void Peripherals::refreshSegments() {
    if (!segmentDisplayEnabled) {
        // Ensure digits are off
        for (int i = 0; i < 4; i++) {
            digitalWrite(digitPins[i], HIGH);
        }
        return;
    }

    static int currentDigit = 0;

    // Turn off previous digit (all digits HIGH) to prevent ghosting
    for (int i = 0; i < 4; i++) {
        digitalWrite(digitPins[i], HIGH);
    }

    // Set segment pins for the current digit
    uint8_t segments = segmentDigits[currentDigit];
    for (int i = 0; i < 8; i++) {
        digitalWrite(segmentPins[i], (segments & (1 << i)) ? HIGH : LOW);
    }

    // Turn on current digit (LOW for active digit)
    digitalWrite(digitPins[currentDigit], LOW);

    // Move to the next digit
    currentDigit = (currentDigit + 1) % 4;
}
#endif

Peripherals Periph;
