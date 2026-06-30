#include <Arduino.h>
#include <Wire.h>
#include "config.h"
#include "sensor_processor.h"
#include "display_manager.h"
#include "network_manager.h"
#include "peripherals.h"

// --- 全域變數 ---
uint32_t totalFingerSeconds = 0;
uint32_t lastTimerUpdate = 0;
uint8_t sleep_counter = 0;
uint32_t lastSleepCounterTime = 0;

bool isShowingReset = false;
unsigned long resetMessageStartTime = 0;

unsigned long lastDisplayUpdate = 0;
unsigned long lastBeatTime = 0;
bool ledOn = false;

// --- 函式宣告 ---
void handleShortPress();
void handleLongPress();
void handleCompletion();
void updateTimer();
void handleResetScreen();

void setup() {
    Serial.begin(115200);

    Periph.begin();
    DisplayMgr.begin();
    DisplayMgr.updateScreen(3, 0, 0, STATUS_NORMAL, 0, 0); // Welcome screen

    NetworkMgr.begin();

    Wire.begin(21, 22);
    if (!SensorProc.begin()) {
        DisplayMgr.updateScreen(0, 0, 0, STATUS_NORMAL, 0, 0); // Error screen
        while (1);
    }
}

void loop() {
    // 1. MQTT 重置未完成前，僅執行感測器維護
    if (!NetworkMgr.isBootResetSent()) {
        SensorProc.update();
        vTaskDelay(10 / portTICK_PERIOD_MS);
        return;
    }

    // 2. 切換初始畫面
    static bool initialScreenSwitched = false;
    if (!initialScreenSwitched) {
        DisplayMgr.updateScreen(1, 0, 0, STATUS_NORMAL, 0, 0); // Place finger
        initialScreenSwitched = true;
    }

    // 3. 更新硬體周邊與按鍵狀態
    Periph.update();
    if (Periph.isShortPressDetected()) handleShortPress();
    if (Periph.isLongPressDetected()) handleLongPress();

    // 4. 處理系統重置顯示狀態
    if (isShowingReset) {
        handleResetScreen();
        return;
    }

    // 5. 更新感測器數據 (若無新樣本則直接結束 loop)
    if (!SensorProc.update()) return;
    unsigned long now = millis();

    if (!SensorProc.isFingerDetected()) {
        // --- 手指移開邏輯 ---
        totalFingerSeconds = 0;
        lastTimerUpdate = 0;

        int current_msg = (sleep_counter <= 50 ? 1 : 4);
        DisplayMgr.updateScreen(current_msg, 0, 0, STATUS_NORMAL, sleep_counter, 0);

        if (now - lastSleepCounterTime >= 200) {
            lastSleepCounterTime = now;
            ++sleep_counter;
            if (sleep_counter > 100) {
                Periph.goSleep();
                sleep_counter = 0;
            }
        }
    } else {
        // --- 手指放置邏輯 ---
        sleep_counter = 0;
        updateTimer();

        // 處理心跳事件
        if (SensorProc.wasBeatDetected()) {
            lastBeatTime = now;
            Periph.setLed(true);
            ledOn = true;

            // 觸發蜂鳴器 (5秒穩定後)
            if (now - SensorProc.getFingerOnStartTime() >= STABILIZATION_MS) {
                DeviceStatus status = SensorProc.getStatus();
                if (status == STATUS_NORMAL) Periph.triggerBeeps(1);
                else if (status == STATUS_WARNING) Periph.triggerBeeps(2);
                else if (status == STATUS_DANGER) Periph.triggerBeeps(4);
            }
        }

        // 紀錄波形 (100% 等價邏輯：每次 sensor 讀取時紀錄)
        DisplayMgr.recordWaveform(-SensorProc.getIRSignal());

        // 定時更新螢幕 (50ms)
        if (now - lastDisplayUpdate > 50) {
            lastDisplayUpdate = now;
            DisplayMgr.updateScreen(2, SensorProc.getBeatAvg(), SensorProc.getSPO2(),
                                   SensorProc.getStatus(), totalFingerSeconds,
                                   SensorProc.getFingerOnStartTime());
        }
    }

    // 關閉心跳指示燈
    if (ledOn && (now - lastBeatTime) > 25) {
        Periph.setLed(false);
        ledOn = false;
    }
}

void handleShortPress() {
    sleep_counter = 0;
    DisplayMgr.updateScreen(1, 0, 0, STATUS_NORMAL, 0, 0);
}

void handleLongPress() {
    NetworkMgr.clearQueue();
    SensorData resetData = {0, 0, STATUS_RESET, 0};
    NetworkMgr.sendData(resetData);

    SensorProc.reset();
    totalFingerSeconds = 0;
    lastTimerUpdate = 0;
    
    isShowingReset = true;
    resetMessageStartTime = millis();
}

void handleResetScreen() {
    DisplayMgr.updateScreen(6, 0, 0, STATUS_NORMAL, 0, 0);

    if (millis() - resetMessageStartTime < 1500) {
        SensorProc.update();
    } else {
        isShowingReset = false;
        sleep_counter = 0;
        lastSleepCounterTime = millis();
        DisplayMgr.updateScreen(1, 0, 0, STATUS_NORMAL, 0, 0);
    }
}

void updateTimer() {
    unsigned long now = millis();
    if (lastTimerUpdate == 0) lastTimerUpdate = now;
    if (now - lastTimerUpdate >= 1000) {
        lastTimerUpdate += 1000;
        if (SensorProc.getSPO2() > 0) {
            totalFingerSeconds++;
            if (totalFingerSeconds >= TARGET_MEASUREMENT_SECONDS) {
                handleCompletion();
            }
        }
    }
}

void handleCompletion() {
    SensorData compData = {SensorProc.getBeatAvg(), SensorProc.getSPO2(), STATUS_COMPLETED, TARGET_MEASUREMENT_SECONDS};
    NetworkMgr.sendData(compData);

    DisplayMgr.fillScreen(ST7735_BLACK);
    DisplayMgr.updateScreen(7, 0, 0, STATUS_NORMAL, 0, 0); // Completion screen
    delay(3000);
    Periph.goSleep();
}
