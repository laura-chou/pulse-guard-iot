#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

/**
 * @file config.h
 * @brief Global configuration, pin definitions, and shared data structures.
 */

// --- Display Mode Settings ---
// Must use preprocessor #define for integer values, otherwise enum will be treated as 0 in #if conditional checks, causing serious logic errors
#define TFT_ST7735   0
#define OLED_SSD1306 1

#define DISPLAY_TYPE TFT_ST7735

// --- TFT Display Pins ---
#define TFT_BLK    19
#define TFT_DC    16
#define TFT_RST   17
#define TFT_CS     5

// --- 4-Digit 7-Segment Display Pins (Common Cathode) ---
// Segment pins (A~G, DP) - output HIGH to light up
#define SEG_A     15 // Avoid using GPIO 12 which is a strapping pin
#define SEG_B     14
#define SEG_C     33
#define SEG_D     26
#define SEG_E     27
#define SEG_F     13
#define SEG_G     32
#define SEG_DP    25 // Colon / Decimal point

// Digit select pins (Digit 2~4) - output LOW to enable the digit (Common Cathode)
// Digit 1 is unused
#define DIG_2     5
#define DIG_3     17
#define DIG_4     16

// --- Peripheral Pins ---
#define LED LED_BUILTIN
#define BUTTON 4
#define BUZZER_PIN 23

// --- Dual I2C Pins for MAX30102 (OLED Mode only) ---
#define MAX30102_SDA 19
#define MAX30102_SCL 18

// --- MQTT & Network Settings ---
const char* const AP_NAME = "PulseGuard-IoT";      // Access Point name for WiFi Setup
const char* const MQTT_SERVER = "YOUR_BROKER";     // MQTT Broker URL
const int MQTT_PORT = 8883;                        // Secure MQTT port
const char* const MQTT_USER = "YOUR_MQTT_USERNAME";
const char* const MQTT_PASS = "YOUR_MQTT_PASSWORD";
const char* const ENV_PROD = "prod";               // Environment prefix for MQTT topic

// --- Timing & Thresholds ---
const unsigned long LONG_PRESS_TIME = 2000;        // 2 seconds for system reset
const unsigned long DEBOUNCE_TIME = 50;            // 50ms button debounce
const uint32_t TARGET_MEASUREMENT_SECONDS = 60;    // Target measurement duration
const uint32_t STABILIZATION_MS = 10000;           // 10 seconds warm-up for sensor stabilization

const int BEEP_ON_TIME = 50;                       // Buzzer on duration
const int BEEP_OFF_TIME = 50;                      // Buzzer off duration between beeps
const int BEEP_FREQ = 2000;                        // Buzzer frequency (Hz)

/**
 * @enum DeviceStatus
 * @brief Health status levels and system states.
 */
enum DeviceStatus {
    STATUS_NORMAL,
    STATUS_WARNING,
    STATUS_DANGER,
    STATUS_RESET,
    STATUS_COMPLETED
};

/**
 * @struct SensorData
 * @brief Structure for passing measurement data to the Network task.
 */
struct SensorData {
    int bpm;
    int spo2;
    DeviceStatus status;
    uint32_t duration_sec;
};

#endif // CONFIG_H
