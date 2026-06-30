#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// --- TFT Pins ---
#define TFT_BLK    4
#define TFT_DC    16
#define TFT_RST   17
#define TFT_CS     5

// --- Peripheral Pins ---
#define LED LED_BUILTIN
#define BUTTON 15
#define BUZZER_PIN 19

// --- MQTT & Network Settings ---
const char* const AP_NAME = "PulseGuard-IoT";
const char* const MQTT_SERVER = "YOUR_BROKER";
const int MQTT_PORT = 8883;
const char* const MQTT_USER = "YOUR_MQTT_USERNAME";
const char* const MQTT_PASS = "YOUR_MQTT_PASSWORD";
const char* const ENV_PROD = "prod";

// --- Timing & Thresholds ---
const unsigned long LONG_PRESS_TIME = 2000;
const unsigned long DEBOUNCE_TIME = 50;
const uint32_t TARGET_MEASUREMENT_SECONDS = 60;
const uint32_t STABILIZATION_MS = 5000;

const int BEEP_ON_TIME = 50;
const int BEEP_OFF_TIME = 50;
const int BEEP_FREQ = 2000;

// --- Status & Data Structures ---
enum DeviceStatus {
    STATUS_NORMAL,
    STATUS_WARNING,
    STATUS_DANGER,
    STATUS_RESET,
    STATUS_COMPLETED
};

struct SensorData {
    int bpm;
    int spo2;
    DeviceStatus status;
    uint32_t duration_sec;
};

#endif // CONFIG_H
