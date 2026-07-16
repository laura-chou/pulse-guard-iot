/**
 * @file firmware.ino
 * @brief Main entry point for the PulseGuard ESP32 firmware.
 *
 * Orchestrates the modularized components for physiological monitoring (BPM/SpO2).
 * Follows a non-blocking architecture using FreeRTOS for networking.
 */

#include <Arduino.h>
#include <Wire.h>
#include "config.h"
#include "sensor_processor.h"
#include "display_manager.h"
#include "pulse_network_manager.h"
#include "peripherals.h"

// --- Global Variables & State Tracking ---
uint32_t totalFingerSeconds = 0;   // Accumulated measurement time (seconds)
uint32_t lastTimerUpdate = 0;      // Timestamp for the 1s timer update
uint8_t sleep_counter = 0;         // Auto-sleep countdown counter (ticks)
uint32_t lastSleepCounterTime = 0; // Timestamp for the sleep counter tick

bool isShowingReset = false;       // Flag for the persistent "RESET SUCCESS" screen
unsigned long resetMessageStartTime = 0;

unsigned long lastDisplayUpdate = 0; // Screen refresh timer
unsigned long lastBeatTime = 0;      // Timestamp for LED heartbeat feedback
bool ledOn = false;

// --- Function Prototypes ---
void handleShortPress();
void handleLongPress();
void handleCompletion();
void updateTimer();
void handleResetScreen();

/**
 * @brief Standard Arduino Setup.
 */
void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("[DEBUG] --- PulseGuard IoT System Booting ---");

    // Initialize I2C bus FIRST so that OLED and MAX30102 can initialize correctly on GPIO 21, 22
    Serial.println("[DEBUG] Initializing I2C SDA=21, SCL=22...");
    Wire.begin(21, 22);

    // Initialize modules
    Serial.println("[DEBUG] Initializing peripherals (LED, Button, Buzzer, 7-Segment)...");
    Periph.begin();

    Serial.println("[DEBUG] Initializing display...");
    DisplayMgr.begin();
    Serial.println("[DEBUG] Drawing Welcome screen...");
    DisplayMgr.updateScreen(3, 0, 0, STATUS_NORMAL, 0, 0); // Show Welcome screen

    Serial.println("[DEBUG] Initializing Network Manager (WiFi Setup)...");
    NetworkMgr.begin(); // Setup WiFi and MQTT Task

    Serial.println("[DEBUG] Initializing Sensor Processor...");
    if (!SensorProc.begin()) {
        Serial.println("[DEBUG] ERROR: Sensor processor (MAX30102) initialization failed! Halting.");
        DisplayMgr.updateScreen(0, 0, 0, STATUS_NORMAL, 0, 0); // Show Device Error screen
        while (1); // Halt on I2C error
    }
    Serial.println("[DEBUG] Sensor processor successfully initialized.");
    Serial.println("[DEBUG] --- Boot up finished successfully ---");
}

/**
 * @brief Main Execution Loop.
 */
void loop() {
    // 1. Wait for MQTT Connection and the initial RESET packet
    if (!NetworkMgr.isBootResetSent()) {
        SensorProc.update(); // Keep sensor buffer clear
        vTaskDelay(10 / portTICK_PERIOD_MS);
        return;
    }

    // 2. Initial UI Transition after boot
    static bool initialScreenSwitched = false;
    if (!initialScreenSwitched) {
        DisplayMgr.updateScreen(1, 0, 0, STATUS_NORMAL, 0, 0); // Show "Place Finger"
        initialScreenSwitched = true;
    }

    // 3. Update Hardware Peripherals (Button, Buzzer)
    Periph.update();
    if (Periph.isShortPressDetected()) handleShortPress();
    if (Periph.isLongPressDetected()) handleLongPress();

    // 4. Handle persistent Reset Screen display period
    if (isShowingReset) {
        handleResetScreen();
        return;
    }

    // 5. Update Sensor and Processing (Non-blocking)
    if (!SensorProc.update()) return; // No new samples, yield loop
    unsigned long now = millis();

    if (!SensorProc.isFingerDetected()) {
        // --- CASE A: Finger Removed ---
        // 手指離開期間（包含「請放置手指」與「關機倒數」共 20 秒內）完全不歸零！
        if (sleep_counter > 50) {
#if (DISPLAY_TYPE == OLED_SSD1306)
            Periph.enableSegmentDisplay(false); // 10秒後熄滅七段顯示器（但秒數不歸零）
#endif
        }

        // Switch between "Place Finger" and "Power Off" countdown
        int current_msg = (sleep_counter <= 50 ? 1 : 4);
        DisplayMgr.updateScreen(current_msg, 0, 0, STATUS_NORMAL, sleep_counter, 0);

        // Increment sleep counter every 200ms
        if (now - lastSleepCounterTime >= 200) {
            lastSleepCounterTime = now;
            ++sleep_counter;
            if (sleep_counter > 100) {
                // 只有在設備真正要進入深度睡眠關機時，才將累積秒數與計時基準清零
                totalFingerSeconds = 0;
                lastTimerUpdate = 0;
                Periph.goSleep(); // 20s idle -> deep sleep
                sleep_counter = 0;
            }
        }
    } else {
        // --- CASE B: Finger Detected (Measuring) ---
        sleep_counter = 0;
        updateTimer();

#if (DISPLAY_TYPE == OLED_SSD1306)
        Periph.enableSegmentDisplay(true);
        Periph.setSegmentTime(totalFingerSeconds);
#endif

        // Heartbeat Visual/Audio Feedback
        if (SensorProc.wasBeatDetected()) {
            lastBeatTime = now;
            Periph.setLed(true);
            ledOn = true;

            // Trigger status-specific buzzer beeps (after 5s stabilization)
            if (now - SensorProc.getFingerOnStartTime() >= STABILIZATION_MS) {
                DeviceStatus status = SensorProc.getStatus();
                if (status == STATUS_NORMAL) Periph.triggerBeeps(1);
                else if (status == STATUS_WARNING) Periph.triggerBeeps(2);
                else if (status == STATUS_DANGER) Periph.triggerBeeps(4);
            }
        }

        // Record PPG Waveform Sample
        DisplayMgr.recordWaveform(-SensorProc.getIRSignal());

        // Update UI at 20Hz (50ms)
        if (now - lastDisplayUpdate > 50) {
            lastDisplayUpdate = now;
            DisplayMgr.updateScreen(2, SensorProc.getBeatAvg(), SensorProc.getSPO2(),
                                   SensorProc.getStatus(), totalFingerSeconds,
                                   SensorProc.getFingerOnStartTime());
        }
    }

    // Turn off heartbeat indicator LED after 25ms
    if (ledOn && (now - lastBeatTime) > 25) {
        Periph.setLed(false);
        ledOn = false;
    }
}

/**
 * @brief Handles short button press (Wake up or Reset status UI).
 */
void handleShortPress() {
    sleep_counter = 0;
    DisplayMgr.updateScreen(1, 0, 0, STATUS_NORMAL, 0, 0);
}

/**
 * @brief Handles long button press (System Reset).
 */
void handleLongPress() {
    // Clear MQTT queue and send RESET packet
    NetworkMgr.clearQueue();
    SensorData resetData = {0, 0, STATUS_RESET, 0};
    NetworkMgr.sendData(resetData);

    // Reset local measurement state
    SensorProc.reset();
    totalFingerSeconds = 0;
    lastTimerUpdate = 0;
    
    isShowingReset = true;
    resetMessageStartTime = millis();

#if (DISPLAY_TYPE == OLED_SSD1306)
    Periph.enableSegmentDisplay(false);
#endif
}

/**
 * @brief Manages the "SYSTEM RESET SUCCESS" screen duration (1.5s).
 */
void handleResetScreen() {
    DisplayMgr.updateScreen(6, 0, 0, STATUS_NORMAL, 0, 0);

    if (millis() - resetMessageStartTime < 1500) {
        SensorProc.update(); // Keep background processing active
    } else {
        isShowingReset = false;
        sleep_counter = 0;
        lastSleepCounterTime = millis();
        DisplayMgr.updateScreen(1, 0, 0, STATUS_NORMAL, 0, 0);
    }
}

/**
 * @brief Accumulates valid measurement time.
 */
void updateTimer() {
    unsigned long now = millis();
    if (lastTimerUpdate == 0) lastTimerUpdate = now;
    if (now - lastTimerUpdate >= 1000) {
        lastTimerUpdate += 1000;
        // Only count time if SpO2 signal is valid (post-stabilization)
        if (SensorProc.getSPO2() > 0) {
            totalFingerSeconds++;
            if (totalFingerSeconds >= TARGET_MEASUREMENT_SECONDS) {
                handleCompletion();
            }
        }
    }
}

/**
 * @brief Handles the completion of a 60s measurement session.
 */
void handleCompletion() {
    // Send final summary via MQTT
    SensorData compData = {SensorProc.getBeatAvg(), SensorProc.getSPO2(), STATUS_COMPLETED, TARGET_MEASUREMENT_SECONDS};
    NetworkMgr.sendData(compData);

    // Show completion screen and enter deep sleep
    DisplayMgr.updateScreen(7, 0, 0, STATUS_NORMAL, 0, 0);

#if (DISPLAY_TYPE == OLED_SSD1306)
    Periph.enableSegmentDisplay(false);
#endif

    delay(3000);
    Periph.goSleep();
}
