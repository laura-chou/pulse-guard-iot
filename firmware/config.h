#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

/**
 * @file config.h
 * @brief Global configuration, pin definitions, and shared data structures.
 */

// --- Display Mode Settings ---
// 必須使用預處理器 #define 定義整數，否則 enum 在 #if 預處理器條件判斷中會被當成 0 處理，導致嚴重的判斷邏輯錯誤
#define TFT_ST7735   0
#define OLED_SSD1306 1

#define DISPLAY_TYPE TFT_ST7735

// --- TFT Display Pins ---
#define TFT_BLK    4
#define TFT_DC    16
#define TFT_RST   17
#define TFT_CS     5

// --- 4-Digit 7-Segment Display Pins (共陰極 Common Cathode) ---
// 段碼接腳 (A~G, DP) - 輸出 HIGH 點亮
#define SEG_A     23 // 避免使用 GPIO 12 啟動選址腳位 (Strapping Pin)
#define SEG_B     13
#define SEG_C     14
#define SEG_D     25
#define SEG_E     26
#define SEG_F     27
#define SEG_G     32
#define SEG_DP    33 // 冒號/小數點

// 位碼選擇接腳 (Digit 1~4) - 輸出 LOW 啟用該位數 (Common Cathode)
// 由於 TFT 顯示器與 4位7段顯示器在實體硬體上不會同時存在，
// 且為了避免與段碼接腳 SEG_C (14) 及 SEG_F (27) 重複，這裡統一回歸並維持原始無重複的預設配置：
#define DIG_1     4
#define DIG_2     16
#define DIG_3     17
#define DIG_4     5

// --- Peripheral Pins ---
#define LED LED_BUILTIN
#define BUTTON 15
#define BUZZER_PIN 19

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
