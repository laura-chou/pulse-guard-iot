#include <Wire.h> 
#include <Adafruit_GFX.h>    
#include <Adafruit_ST7735.h> 
#include <SPI.h>
#include "MAX30102.h"
#include "Pulse.h"
#include <pgmspace.h>

// --- 網路、MQTT 與 WiFiManager 相關標頭檔 ---
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <WiFiManager.h>

// 定義 TFT 接腳
#define TFT_BLK    4
#define TFT_DC    16
#define TFT_RST   17
#define TFT_CS     5

Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);
MAX30102 sensor; 
Pulse pulseIR;
Pulse pulseRed;
MAFilter bpm;

#define LED LED_BUILTIN
#define BUTTON 15       
#define BUZZER_PIN 19   

// ─── 狀態定義 ───
enum DeviceStatus { STATUS_NORMAL, STATUS_WARNING, STATUS_DANGER, STATUS_RESET, STATUS_COMPLETED };
DeviceStatus currentStatus = STATUS_NORMAL; 

// 開機 RESET 是否已成功由 MQTT 發射出去的標記
volatile bool bootResetSent = false;

// ─── MQTT 與 AP 設定 ───
const char* ap_name = "PulseGuard-IoT";          // AP 名稱
const char* mqtt_server = "YOUR_BROKER";         // 叢集網址
const int mqtt_port = 8883;                      // 埠號
const char* mqtt_user = "YOUR_MQTT_USERNAME";    // 帳號
const char* mqtt_pass = "YOUR_MQTT_PASSWORD";    // 密碼
const char* mqtt_topic = "esp32/topic";          // 發布主題

WiFiClientSecure espClient;
PubSubClient mqttClient(espClient);

// ─── FreeRTOS 雙核通訊 ───
struct SensorData {
    int bpm;
    int spo2;
    DeviceStatus status;
    uint32_t duration_sec; 
};
QueueHandle_t dataQueue; 
TaskHandle_t MqttTaskHandle;

// ─── 全域測量時間設定 ───
uint32_t targetMeasurementSeconds = 30;

// ─── 計時器與動態刷新快取變數 ───
uint32_t totalFingerSeconds = 0;
uint32_t lastTimerUpdate = 0;
uint32_t fingerOnStartTime = 0;
int last_printed_seconds = -1;
int last_printed_status = -1;

// ─── 按鍵偵測與畫面停留變數 ───
unsigned long buttonPressStart = 0; 
bool lastButtonState = HIGH;
const unsigned long LONG_PRESS_TIME = 2000;
const unsigned long DEBOUNCE_TIME = 50;     

bool isShowingReset = false;
unsigned long resetMessageStartTime = 0;

// ─── 蜂鳴器非阻塞控制變數 ───
int beepsToPlay = 0;             
bool isBuzzerOn = false;         
uint32_t lastBuzzerToggleTime = 0;
const int BEEP_ON_TIME = 50;
const int BEEP_OFF_TIME = 50;

// 第一下心跳防呆標記
bool firstBeatAfterPlacement = true;

// 圖標資源
static const uint8_t heart_bits[] PROGMEM = { 0x00, 0x00, 0x38, 0x38, 0x7c, 0x7c, 0xfe, 0xfe, 0xfe, 0xff, 0xfe, 0xff, 0xfc, 0x7f, 0xf8, 0x3f, 0xf0, 0x1f, 0xe0, 0x0f, 0xc0, 0x07, 0x80, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
static const uint8_t o2_bits[] PROGMEM = { 0xf8, 0x03, 0x0c, 0x06, 0x06, 0x0c, 0x06, 0x0c, 0x06, 0x0c, 0x06, 0x0c, 0x0c, 0x76, 0xf8, 0x63, 0x00, 0x61, 0x00, 0x30, 0x00, 0x1c, 0x00, 0x7f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
const uint8_t MAXWAVE = 160; 

class Waveform {
  public:
    Waveform(void) { wavep = 0; memset(waveform, 128, MAXWAVE); } 
    void record(int waveval) {
        waveval = waveval / 8; waveval += 128; 
        waveval = waveval < 0 ? 0 : (waveval > 255 ? 255 : waveval);
        waveform[wavep] = (uint8_t)waveval; wavep = (wavep + 1) % MAXWAVE;
    }
    void scale() {
        uint8_t maxw = 0; uint8_t minw = 255; 
        for (int i = 0; i < MAXWAVE; i++) { 
            maxw = waveform[i] > maxw ? waveform[i] : maxw; 
            minw = waveform[i] < minw ? waveform[i] : minw;
        } 
        uint8_t range = maxw - minw; if (range == 0) range = 1; 
        uint8_t index = wavep;
        for (int i = 0; i < MAXWAVE; i++) { 
            disp_wave[i] = 70 - ((uint16_t)(waveform[index] - minw) * 50) / range;
            index = (index + 1) % MAXWAVE; 
        }
    }
    void draw(uint8_t X) {
        tft.fillRect(X, 16, MAXWAVE, 59, ST7735_BLACK);
        for (int i = 0; i < MAXWAVE - 1; i++) {
            tft.drawLine(X + i, disp_wave[i], X + i + 1, disp_wave[i + 1], ST7735_GREEN);
        } 
    }
  private:
    uint8_t waveform[MAXWAVE];
    uint8_t disp_wave[MAXWAVE];
    uint8_t wavep = 0;
} wave; 

int  beatAvg = 0; 
int  SPO2 = 0;
uint8_t sleep_counter = 0;

void go_sleep() { 
    tft.fillScreen(ST7735_BLACK); 
    tft.enableDisplay(false);
    noTone(BUZZER_PIN); 
    digitalWrite(TFT_BLK, LOW); 

    delay(10);
    sensor.off();
    delay(10);
    pinMode(0, INPUT);
    pinMode(2, INPUT);
    esp_deep_sleep_start();
}

int last_msg = -1; 
int last_printed_bpm = -1;
int last_printed_spo2 = -1;

void updateDisplay(int msg) {
    if (msg != last_msg) {
        tft.fillScreen(ST7735_BLACK);
        last_msg = msg;
        last_printed_bpm = -1;
        last_printed_spo2 = -1;
        last_printed_seconds = -1; 
        last_printed_status = -1;
        if (msg == 2) {
            tft.fillRect(0, 0, 160, 15, ST7735_BLACK);
            tft.drawFastHLine(0, 15, 160, ST7735_WHITE); 
            tft.drawFastHLine(0, 75, 160, ST7735_WHITE); 
            tft.drawFastVLine(80, 75, 53, ST7735_WHITE); 
            tft.drawXBitmap(21, 110, heart_bits, 16, 16, ST7735_RED); 
            tft.setTextSize(1);
            tft.setTextColor(ST7735_RED, ST7735_BLACK); 
            tft.setCursor(21 + 16 + 4, 114); tft.print(F("BPM"));
            tft.drawXBitmap(107, 110, o2_bits, 16, 16, ST7735_CYAN);
            tft.setTextSize(1); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            tft.setCursor(107 + 16 + 4, 114); tft.print(F("%")); 
        }
    }

    switch(msg){
        case 0: { // 裝置錯誤畫面
            int16_t x1, y1; uint16_t w, h; 
            tft.setTextSize(2); tft.setTextColor(ST7735_RED, ST7735_BLACK);
            const char* err = "DEVICE ERROR";
            tft.getTextBounds(err, 0, 0, &x1, &y1, &w, &h);
            tft.setCursor((160 - w) / 2, 45); tft.print(err); 

            tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
            const char* msg2 = "Check I2C Wire!";
            tft.getTextBounds(msg2, 0, 0, &x1, &y1, &w, &h); 
            tft.setCursor((160 - w) / 2, 75); tft.print(msg2);
            break;
        }
        case 1: { // 請放手指畫面
            int16_t x1, y1; uint16_t w, h; 
            tft.setTextSize(2); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            const char* p1 = "PLACE";
            tft.getTextBounds(p1, 0, 0, &x1, &y1, &w, &h);
            tft.setCursor((160 - w) / 2, 40); tft.print(p1); 

            const char* p2 = "FINGER";
            tft.getTextBounds(p2, 0, 0, &x1, &y1, &w, &h);
            tft.setCursor((160 - w) / 2, 65); tft.print(p2);

            tft.fillRect(0, 108, 160, 20, ST7735_BLACK);
            tft.setTextSize(1); tft.setTextColor(ST7735_GREEN, ST7735_BLACK);
            const char* mode = "Mode: IR Filter: Avg"; 
            tft.getTextBounds(mode, 0, 0, &x1, &y1, &w, &h);
            tft.setCursor((160 - w) / 2, 113); tft.print(mode); 
            break;
        }
        case 2: // 正常測量中畫面
        {
            // 判斷當前是否處於 5 秒熱身收斂期
            bool isWarmingUp = (fingerOnStartTime == 0 || (millis() - fingerOnStartTime < 5000));
            static bool lastWarmingUpState = false;
            static unsigned long lastWarmUpDraw = 0;

            if (isWarmingUp) {
                // 如果剛進入熱身、或剛切換模式 (last_printed_status == -1)、或每 500ms 定時防殘留重繪
                if (!lastWarmingUpState || last_printed_status == -1 || (millis() - lastWarmUpDraw > 500)) {
                    tft.fillRect(0, 16, MAXWAVE, 59, ST7735_BLACK);      // 清空波形區
                    tft.drawFastHLine(0, 45, MAXWAVE, ST7735_GREEN);     // 繪製靜態平穩基線
                    tft.setTextSize(1);
                    tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
                    tft.setCursor(40, 38);
                    tft.print("Stabilizing...");                       // 顯示文字告知使用者正在穩定訊號
                    lastWarmUpDraw = millis();
                }
            } else {
                // 剛結束熱身切換至動態波形的那一刻，先清空一次熱身畫面
                if (lastWarmingUpState || last_printed_status == -1) {
                    tft.fillRect(0, 16, MAXWAVE, 59, ST7735_BLACK);
                }
                wave.draw(0); // 通過 5 秒熱身，開始繪製精準即時波形
            }
            lastWarmingUpState = isWarmingUp; // 快取狀態

            // 更新頂部狀態與計時器
            if ((int)currentStatus != last_printed_status || (int)totalFingerSeconds != last_printed_seconds) { 
                tft.setTextSize(1);
                if ((int)currentStatus != last_printed_status) { 
                    last_printed_status = (int)currentStatus;
                    tft.fillRect(0, 0, 110, 15, ST7735_BLACK);  
                    uint16_t dotColor = ST7735_GREEN;
                    const char* statusStr = "NORMAL";
                    if (currentStatus == STATUS_WARNING) { dotColor = ST7735_YELLOW; statusStr = "WARNING"; } 
                    else if (currentStatus == STATUS_DANGER) { dotColor = ST7735_RED; statusStr = "DANGER"; } 
                    tft.fillCircle(8, 7, 3, dotColor);
                    tft.setTextColor(ST7735_WHITE, ST7735_BLACK); 
                    tft.setCursor(18, 4); tft.print(statusStr);
                }
                
                if ((int)totalFingerSeconds != last_printed_seconds) {
                    last_printed_seconds = (int)totalFingerSeconds;
                    tft.fillRect(120, 0, 40, 15, ST7735_BLACK);  
                    int mins = totalFingerSeconds / 60;
                    int secs = totalFingerSeconds % 60;
                    tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
                    tft.setCursor(125, 4); 
                    if (mins < 10) tft.print('0'); tft.print(mins); tft.print(':');
                    if (secs < 10) tft.print('0'); tft.print(secs);
                } 
            }
            
            // 更新心率數據 (熱身期自動顯示 "---")
            if (beatAvg != last_printed_bpm) {
                last_printed_bpm = beatAvg;
                tft.fillRect(5, 82, 70, 24, ST7735_BLACK); 
                tft.setTextSize(3); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
                if (beatAvg > 0) {
                    int numDigits = (beatAvg < 10) ? 1 : ((beatAvg < 100) ? 2 : 3); 
                    int numX = (80 - (numDigits * 18)) / 2;
                    tft.setCursor(numX, 82); tft.print(beatAvg); 
                } else {
                    tft.setCursor((80 - 54) / 2, 82); tft.print(F("---")); 
                }
            }
            
            // 更新血氧數據 (熱身期自動顯示 "---")
            if (SPO2 != last_printed_spo2) {
                last_printed_spo2 = SPO2;
                tft.fillRect(85, 82, 70, 24, ST7735_BLACK); 
                tft.setTextSize(3); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
                if (SPO2 > 0) {
                    int numDigits = (SPO2 < 10) ? 1 : ((SPO2 < 100) ? 2 : 3); 
                    int numX = 80 + (80 - (numDigits * 18)) / 2;
                    tft.setCursor(numX, 82); tft.print(SPO2); 
                } else {
                    tft.setCursor(80 + (80 - 54) / 2, 82); tft.print(F("---")); 
                }
            }
            break;
        }
        case 3: { // 開機歡迎畫面
            int16_t x1, y1; uint16_t w, h;
            tft.drawXBitmap(72, 12, heart_bits, 16, 16, ST7735_RED); 

            tft.setTextSize(2); tft.setTextColor(ST7735_CYAN, ST7735_BLACK); 
            const char* title = "PulseGuard";
            tft.getTextBounds(title, 0, 0, &x1, &y1, &w, &h); 
            tft.setCursor((160 - w) / 2, 35); tft.print(title);

            tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
            const char* line1 = "Heart Rate &"; 
            tft.getTextBounds(line1, 0, 0, &x1, &y1, &w, &h);
            tft.setCursor((160 - w) / 2, 65); tft.print(line1); 

            const char* line2 = "SpO2 Monitor";
            tft.getTextBounds(line2, 0, 0, &x1, &y1, &w, &h);
            tft.setCursor((160 - w) / 2, 80); tft.print(line2); 

            tft.setTextColor(ST7735_YELLOW, ST7735_BLACK); 
            const char* initText = "Initializing...";
            tft.getTextBounds(initText, 0, 0, &x1, &y1, &w, &h);
            tft.setCursor((160 - w) / 2, 105); tft.print(initText); 
            break;
        }
        case 4: { // 倒數自動斷電畫面
            int16_t x1, y1; uint16_t w, h; 
            tft.setTextSize(2); tft.setTextColor(ST7735_RED, ST7735_BLACK);
            const char* po = "POWER OFF";
            tft.getTextBounds(po, 0, 0, &x1, &y1, &w, &h);
            tft.setCursor((160 - w) / 2, 40); tft.print(po);

            int secondsLeft = (100 - sleep_counter) / 5;
            tft.fillRect(0, 75, 160, 32, ST7735_BLACK);
            tft.setTextSize(4); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            char secStr[4]; sprintf(secStr, "%d", secondsLeft);
            tft.getTextBounds(secStr, 0, 0, &x1, &y1, &w, &h);
            tft.setCursor((160 - w) / 2, 75); tft.print(secStr);
            break;
        }
        case 5: { // WiFiManager 設定畫面
            int16_t x1, y1; uint16_t w, h; 
            tft.setTextSize(2); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            const char* title = "WIFI SETUP";
            tft.getTextBounds(title, 0, 0, &x1, &y1, &w, &h);
            tft.setCursor((160 - w) / 2, 25); tft.print(title);
            
            tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
            const char* l1 = "Please connect to AP:";
            tft.getTextBounds(l1, 0, 0, &x1, &y1, &w, &h); 
            tft.setCursor((160 - w) / 2, 55); tft.print(l1);
            
            tft.setTextColor(ST7735_GREEN, ST7735_BLACK);
            tft.getTextBounds(ap_name, 0, 0, &x1, &y1, &w, &h); 
            tft.setCursor((160 - w) / 2, 75); tft.print(ap_name);
            
            tft.setTextColor(ST7735_CYAN, ST7735_BLACK);
            const char* l2 = "IP: 192.168.4.1"; 
            tft.getTextBounds(l2, 0, 0, &x1, &y1, &w, &h);
            tft.setCursor((160 - w) / 2, 100); tft.print(l2);
            break; 
        }
    }
}

void handleShortPress() {
    sleep_counter = 0; last_msg = -1; updateDisplay(1);
}

void handleLongPress() {
    xQueueReset(dataQueue); 
    if (dataQueue != NULL) {
        SensorData resetData;
        resetData.bpm = 0; resetData.spo2 = 0; resetData.status = STATUS_RESET; 
        xQueueSend(dataQueue, &resetData, 0);
    }
    beatAvg = 0; SPO2 = 0; 
    last_printed_bpm = -1; last_printed_spo2 = -1;
    beepsToPlay = 0; isBuzzerOn = false; noTone(BUZZER_PIN); 
    digitalWrite(LED, LOW);
    totalFingerSeconds = 0; lastTimerUpdate = 0; fingerOnStartTime = 0; last_printed_seconds = -1; 
    currentStatus = STATUS_NORMAL; last_printed_status = -1;

    tft.fillScreen(ST7735_BLACK);
    int16_t x1, y1; uint16_t w, h; 
    tft.setTextSize(2); tft.setTextColor(ST7735_GREEN, ST7735_BLACK);
    const char* m1 = "SYSTEM RESET";
    tft.getTextBounds(m1, 0, 0, &x1, &y1, &w, &h); 
    tft.setCursor((160 - w) / 2, 45); tft.print(m1);
    
    tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
    const char* m2 = "SUCCESS !"; 
    tft.getTextBounds(m2, 0, 0, &x1, &y1, &w, &h);
    tft.setCursor((160 - w) / 2, 75); tft.print(m2);
    isShowingReset = true; resetMessageStartTime = millis(); 
}

void handleCompletion() {
    if (dataQueue != NULL) {
        SensorData compData;
        compData.bpm = beatAvg; 
        compData.spo2 = SPO2;
        compData.status = STATUS_COMPLETED;
        compData.duration_sec = targetMeasurementSeconds; 
        xQueueSend(dataQueue, &compData, 0);
    } 

    tft.fillScreen(ST7735_BLACK);
    tft.setTextSize(2); tft.setTextColor(ST7735_CYAN, ST7735_BLACK); 
    tft.setCursor(15, 45); tft.print("COMPLETED !");
    
    tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK); 
    tft.setCursor(30, 85); tft.print("System Sleeping...");
    delay(3000);
    go_sleep(); 
}

void configModeCallback(WiFiManager *myWiFiManager) {
    updateDisplay(5); 
}

void networkTask(void *pvParameters) {
    espClient.setInsecure();
    mqttClient.setServer(mqtt_server, mqtt_port);
    SensorData dataToPublish; 
    for (;;) { 
        if (WiFi.status() != WL_CONNECTED) {
            WiFi.disconnect(); WiFi.reconnect(); 
            while (WiFi.status() != WL_CONNECTED) {
                vTaskDelay(500 / portTICK_PERIOD_MS);
            }
        }

        if (WiFi.status() == WL_CONNECTED && !mqttClient.connected()) {
            String clientId = "ESP32_HR_O2_";
            clientId += String(random(0xffff), HEX); 
            mqttClient.connect(clientId.c_str(), mqtt_user, mqtt_pass);
            vTaskDelay(500 / portTICK_PERIOD_MS);
        }
        
        mqttClient.loop();
        if (mqttClient.connected()) { 
            if (!bootResetSent) {
                const char* initResetPayload = "{\"status\":\"RESET\"}";
                if (mqttClient.publish(mqtt_topic, initResetPayload)) { 
                    bootResetSent = true;
                }
            } 
            else {
                if (xQueueReceive(dataQueue, &dataToPublish, 0) == pdPASS) { 
                    char jsonPayload[128];
                    const char* sStr = "NORMAL"; 
                    
                    if (dataToPublish.status == STATUS_WARNING) { sStr = "WARNING"; } 
                    else if (dataToPublish.status == STATUS_DANGER) { sStr = "DANGER"; } 
                    else if (dataToPublish.status == STATUS_RESET) { sStr = "RESET"; } 
                    else if (dataToPublish.status == STATUS_COMPLETED) { sStr = "COMPLETED"; } 
                    
                    if (dataToPublish.status == STATUS_COMPLETED) {
                        snprintf(jsonPayload, sizeof(jsonPayload), 
                                 "{\"status\":\"COMPLETED\",\"duration_sec\":%lu}",
                                 (unsigned long)dataToPublish.duration_sec);
                    } else if (dataToPublish.bpm == 0 && dataToPublish.spo2 == 0) {
                        snprintf(jsonPayload, sizeof(jsonPayload),
                                 "{\"status\":\"%s\"}", sStr);
                    } else {
                        snprintf(jsonPayload, sizeof(jsonPayload), 
                                 "{\"bpm\":%d,\"spo2\":%d,\"status\":\"%s\"}",
                                 dataToPublish.bpm, dataToPublish.spo2, sStr); 
                    }
                    mqttClient.publish(mqtt_topic, jsonPayload);
                }
            }
        }
        vTaskDelay(10 / portTICK_PERIOD_MS);
    }
}

void setup(void) {
  Serial.begin(115200); 
  pinMode(LED, OUTPUT);
  pinMode(BUTTON, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT); 
  noTone(BUZZER_PIN);
  
  pinMode(TFT_BLK, OUTPUT);     
  digitalWrite(TFT_BLK, HIGH);

  tft.initR(INITR_BLACKTAB);
  tft.setRotation(1); 
  tft.fillScreen(ST7735_BLACK);

  updateDisplay(3);
  esp_sleep_enable_ext0_wakeup(GPIO_NUM_15, 0);

  WiFiManager wm; 
  wm.setConnectTimeout(10); 
  wm.setConfigPortalTimeout(180);
  wm.setAPCallback(configModeCallback); 
  if (!wm.autoConnect(ap_name)) {
      ESP.restart(); 
  }

  Wire.begin(21, 22);
  if (!sensor.begin())  { 
    updateDisplay(0);         
    while (1);
  }

  // 顯式設定為 SpO2 混合測量模式
  sensor.setup();
  dataQueue = xQueueCreate(5, sizeof(SensorData));
  if (dataQueue != NULL) { 
      xTaskCreatePinnedToCore(
          networkTask, "NetworkTask", 8192, NULL, 1, &MqttTaskHandle, 0                
      );
  }
}

long lastBeat = 0;
long displaytime = 0;
bool led_on = false;
uint32_t lastSleepCounterTime = 0;
unsigned long lastPublishTime = 0; 

void loop()  {
    if (!bootResetSent) {
        sensor.check();
        while (sensor.available()) { 
            sensor.getIR(); 
            sensor.getRed(); 
            sensor.nextSample();
        } 
        vTaskDelay(10 / portTICK_PERIOD_MS); 
        return;
    }

    static bool initialScreenSwitched = false;
    if (!initialScreenSwitched) {
        last_msg = -1;
        updateDisplay(1);  initialScreenSwitched = true; 
    }

    bool currentButtonState = digitalRead(BUTTON);
    if (lastButtonState == HIGH && currentButtonState == LOW) { 
        buttonPressStart = millis();
    } 
    else if (lastButtonState == LOW && currentButtonState == HIGH) {
        unsigned long pressDuration = millis() - buttonPressStart;
        if (pressDuration >= DEBOUNCE_TIME && pressDuration < LONG_PRESS_TIME && buttonPressStart > 0) {
            if (isShowingReset) isShowingReset = false;
            handleShortPress();
        }
        buttonPressStart = 0;
    }

    if (currentButtonState == LOW && buttonPressStart > 0 && (millis() - buttonPressStart >= LONG_PRESS_TIME)) {
        handleLongPress();
        buttonPressStart = 0; 
    }
    lastButtonState = currentButtonState;

    if (isShowingReset) { 
        if (millis() - resetMessageStartTime < 1500) {
            sensor.check();
            while (sensor.available()) { 
                sensor.getIR();
                sensor.getRed(); sensor.nextSample(); 
            }
            return;
        } else {
            isShowingReset = false; sleep_counter = 0;
            lastSleepCounterTime = millis(); last_msg = -1; updateDisplay(1); 
        }
    }

    sensor.check();
    long now = millis();
    if (!sensor.available()) return; 
    uint32_t irValue = sensor.getIR();
    uint32_t redValue = sensor.getRed();
    sensor.nextSample();

    if (irValue < 5000) { 
        // 【情況 A：手指移開】
        lastTimerUpdate = 0;
        fingerOnStartTime = 0;  // 歸零熱身時間
        totalFingerSeconds = 0; // 歸零計時
        beatAvg = 0; 
        SPO2 = 0; 
        currentStatus = STATUS_NORMAL;
        beepsToPlay = 0; isBuzzerOn = false; noTone(BUZZER_PIN); 
        firstBeatAfterPlacement = true; 

        int current_msg = (sleep_counter <= 50 ? 1 : 4);
        updateDisplay(current_msg); 
        if (now - lastSleepCounterTime >= 200) {
            lastSleepCounterTime = now;
            ++sleep_counter; 
            if (sleep_counter > 100) {
              go_sleep();
              sleep_counter = 0; 
            }
        }
    } else {
        // 【情況 B：放上手指進行測量】
        sleep_counter = 0;
        
        // 只要手指一放上去，立刻錨定熱身起點時間（不等待第一下心跳）
        if (fingerOnStartTime == 0) {
            fingerOnStartTime = now;
        }

        int16_t IR_signal  = pulseIR.ma_filter(pulseIR.dc_filter(irValue)); 
        int16_t Red_signal = pulseRed.ma_filter(pulseRed.dc_filter(redValue));
        
        bool beatIR  = pulseIR.isBeat(IR_signal);
        bool beatRed = pulseRed.isBeat(Red_signal); 
        
        wave.record(-IR_signal); 

        // 30 秒倒數計時累積邏輯
        if (lastTimerUpdate == 0) lastTimerUpdate = now;
        if (now - lastTimerUpdate >= 1000) {
            lastTimerUpdate += 1000;
            if (SPO2 > 0) { 
                totalFingerSeconds++;
                if (totalFingerSeconds >= targetMeasurementSeconds) {
                    handleCompletion();
                }
            }
        }

        if (beatIR){ 
            if (firstBeatAfterPlacement) {
                lastBeat = now;
                firstBeatAfterPlacement = false; 
            } else {
                long btpm = 60000 / (now - lastBeat);
                if (btpm > 0 && btpm < 200) beatAvg = bpm.filter((int16_t)btpm); 
                lastBeat = now;
            }
            
            digitalWrite(LED, HIGH);
            led_on = true; 

            // ─── 血氧數據計算 ───
            float rAC = pulseRed.avgAC();
            float rDC = pulseRed.avgDC();
            float iAC = pulseIR.avgAC();
            float iDC = pulseIR.avgDC();

            if (rDC > 0 && iDC > 0 && iAC > 0) {
                float rRatio = (iAC / iDC) / (rAC / rDC);
                float calculatedSpO2 = -45.060 * (rRatio * rRatio) + 30.354 * rRatio + 94.845;
                if (calculatedSpO2 > 100.0) calculatedSpO2 = 100.0;
                
                // 判斷是否真正放滿 5 秒
                if (now - fingerOnStartTime >= 5000) {
                    if (calculatedSpO2 >= 50.0) {
                        SPO2 = (int)calculatedSpO2;
                    } else {
                        SPO2 = 0; 
                    }
                } else {
                    // 熱身未滿 5 秒，強制數據歸零
                    SPO2 = 0;
                    beatAvg = 0; 
                }
            }
            
            // 只有當 5 秒熱身結束，且數值有效時，才允許更新狀態、響蜂鳴器與發送 MQTT
            if (now - fingerOnStartTime >= 5000) {
                if (SPO2 > 0 && beatAvg > 0) { 
                    if (SPO2 < 90 || beatAvg < 50 || beatAvg > 120) { currentStatus = STATUS_DANGER; } 
                    else if (SPO2 < 95 || beatAvg < 60 || beatAvg > 100) { currentStatus = STATUS_WARNING; } 
                    else { currentStatus = STATUS_NORMAL; } 

                    if (now - lastPublishTime > 1000) {
                        SensorData outData;
                        outData.bpm = beatAvg; outData.spo2 = SPO2; outData.status = currentStatus; 
                        xQueueSend(dataQueue, &outData, 0); 
                        lastPublishTime = now;
                    }
                }
                
                if (currentStatus == STATUS_NORMAL) { beepsToPlay = 1; } 
                else if (currentStatus == STATUS_WARNING) { beepsToPlay = 2; } 
                else if (currentStatus == STATUS_DANGER) { beepsToPlay = 4; } 
                
                if (beepsToPlay > 0) {
                    isBuzzerOn = true;
                    lastBuzzerToggleTime = now; tone(BUZZER_PIN, 2000); 
                }
            }
        }

        if (now - displaytime > 50) { 
            displaytime = now;
            wave.scale(); updateDisplay(2); 
        }
    }

    if (led_on && (now - lastBeat) > 25){
        digitalWrite(LED, LOW);
        led_on = false; 
    }
    
    if (beepsToPlay > 0) {
        uint32_t timePassed = millis() - lastBuzzerToggleTime;
        if (isBuzzerOn) {
            if (timePassed >= BEEP_ON_TIME) {
                noTone(BUZZER_PIN);
                isBuzzerOn = false; lastBuzzerToggleTime = millis(); beepsToPlay--; 
            }
        } else {
            if (timePassed >= BEEP_OFF_TIME && beepsToPlay > 0) {
                tone(BUZZER_PIN, 2000);
                isBuzzerOn = true; lastBuzzerToggleTime = millis(); 
            }
        }
    } else {
        noTone(BUZZER_PIN);
    }
}