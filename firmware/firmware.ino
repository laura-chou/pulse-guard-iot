#include <Wire.h> 
#include <Adafruit_GFX.h>    
#include <Adafruit_ST7735.h> 
#include <SPI.h>
#include "MAX30102.h"
#include "Pulse.h"
#include <pgmspace.h>

// --- 網路與 MQTT 相關標頭檔 ---
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

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

// ─── 狀態判斷條件與定義 ───
enum DeviceStatus { STATUS_NORMAL, STATUS_WARNING, STATUS_DANGER };
DeviceStatus currentStatus = STATUS_NORMAL;

// ─── Wi-Fi & MQTT 設定 ───
const char* ssid = "YOUR_WIFI_SSID";             // Wi-Fi 名稱
const char* password = "YOUR_WIFI_PASSWORD";     // Wi-Fi 密碼

const char* mqtt_server = "YOUR_BROKER";         // 叢集網址
const int mqtt_port = 8883;                      // 埠號
const char* mqtt_user = "YOUR_MQTT_USERNAME";    // 帳號
const char* mqtt_pass = "YOUR_MQTT_PASSWORD";    // 密碼
const char* mqtt_topic = "esp32/topic";          // 發布主題

WiFiClientSecure espClient;
PubSubClient mqttClient(espClient);

// ─── FreeRTOS 雙核通訊：Queue 設定 ───
struct SensorData {
    int bpm;
    int spo2;
    DeviceStatus status;
};
QueueHandle_t dataQueue;
TaskHandle_t MqttTaskHandle;

// ─── 計時器與動態刷新快取變數 ───
uint32_t totalFingerSeconds = 0; 
uint32_t lastTimerUpdate = 0;
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

// 圖標與查表資料
static const uint8_t heart_bits[] PROGMEM = { 0x00, 0x00, 0x38, 0x38, 0x7c, 0x7c, 0xfe, 0xfe, 0xfe, 0xff, 0xfe, 0xff, 0xfc, 0x7f, 0xf8, 0x3f, 0xf0, 0x1f, 0xe0, 0x0f, 0xc0, 0x07, 0x80, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
static const uint8_t o2_bits[] PROGMEM = { 0xf8, 0x03, 0x0c, 0x06, 0x06, 0x0c, 0x06, 0x0c, 0x06, 0x0c, 0x06, 0x0c, 0x0c, 0x76, 0xf8, 0x63, 0x00, 0x61, 0x00, 0x30, 0x00, 0x1c, 0x00, 0x7f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
const uint8_t spo2_table[184] PROGMEM = { 95, 95, 95, 96, 96, 96, 97, 97, 97, 97, 97, 98, 98, 98, 98, 98, 99, 99, 99, 99, 99, 99, 99, 99, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 99, 99, 99, 99, 99, 99, 99, 99, 98, 98, 98, 98, 98, 98, 97, 97, 97, 97, 96, 96, 96, 96, 95, 95, 95, 94, 94, 94, 93, 93, 93, 92, 92, 92, 91, 91, 90, 90, 89, 89, 89, 88, 88, 87, 87, 86, 86, 85, 85, 84, 84, 83, 82, 82, 81, 81, 80, 80, 79, 78, 78, 77, 76, 76, 75, 74, 74, 73, 72, 72, 71, 70, 69, 69, 68, 67, 66, 66, 65, 64, 63, 62, 62, 61, 60, 59, 58, 57, 56, 56, 55, 54, 53, 52, 51, 50, 49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 31, 30, 29, 28, 27, 26, 25, 23, 22, 21, 20, 19, 17, 16, 15, 14, 12, 11, 10, 9, 7, 6, 5, 3, 2, 1 };

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
int  SPO2 = 0, SPO2f = 0;
uint8_t sleep_counter = 0;

void go_sleep() { 
    tft.fillScreen(ST7735_BLACK);
    tft.enableDisplay(false);
    noTone(BUZZER_PIN); 
    digitalWrite(TFT_BLK, LOW); // 關閉螢幕背光
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

void draw_oled(int msg) {
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
            tft.setTextSize(1); tft.setTextColor(ST7735_RED, ST7735_BLACK);
            tft.setCursor(21 + 16 + 4, 114); tft.print(F("BPM"));
            tft.drawXBitmap(107, 110, o2_bits, 16, 16, ST7735_CYAN);
            tft.setTextSize(1); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            tft.setCursor(107 + 16 + 4, 114); tft.print(F("%"));
        }
    }

    switch(msg){
        case 0: 
            tft.setTextSize(2); tft.setTextColor(ST7735_RED, ST7735_BLACK);
            tft.setCursor(8, 45); tft.print(F("DEVICE ERROR"));
            tft.setTextSize(1); tft.setCursor(35, 75); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
            tft.print(F("Check I2C Wire!"));
            break;
        case 1: 
            tft.setTextSize(2); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            tft.setCursor(50, 45); tft.print(F("PLACE"));
            tft.setCursor(44, 70); tft.print(F("FINGER"));
            tft.fillRect(0, 108, 160, 20, ST7735_BLACK);
            tft.setTextSize(1); tft.setTextColor(ST7735_GREEN, ST7735_BLACK);
            tft.setCursor(20, 113); tft.print(F("Mode: IR Filter: Avg"));
            break;
        case 2: 
            wave.draw(0);
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
        case 3: 
            tft.drawXBitmap(72, 20, heart_bits, 16, 16, ST7735_RED);
            tft.setTextSize(2); tft.setTextColor(ST7735_CYAN, ST7735_BLACK);
            tft.setCursor(20, 45);  tft.print(F("HEART RATE"));
            tft.setCursor(32, 70);  tft.print(F("OXYMETER"));
            tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
            tft.setCursor(35, 105); tft.print(F("Initializing..."));
            break;
        case 4: 
            tft.setTextSize(2); tft.setTextColor(ST7735_RED, ST7735_BLACK);
            tft.setCursor(26, 45); tft.print(F("POWER OFF"));
            {
                int secondsLeft = (100 - sleep_counter) / 5;
                tft.fillRect(50, 75, 60, 32, ST7735_BLACK);
                int startX = (secondsLeft == 10) ? 56 : 68;
                tft.setTextSize(4); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
                tft.setCursor(startX, 75); tft.print(secondsLeft);
            }
            break;
    }
}

void handleShortPress() {
    sleep_counter = 0; 
    last_msg = -1; 
    draw_oled(1);
}

void handleLongPress() {
    beatAvg = 0; SPO2 = 0; SPO2f = 0;
    last_printed_bpm = -1; last_printed_spo2 = -1;
    beepsToPlay = 0; isBuzzerOn = false; noTone(BUZZER_PIN);
    digitalWrite(LED, LOW);
    totalFingerSeconds = 0; lastTimerUpdate = 0; last_printed_seconds = -1;
    currentStatus = STATUS_NORMAL; last_printed_status = -1;
    
    xQueueReset(dataQueue); // 重置時順便清空發送佇列

    tft.fillScreen(ST7735_BLACK);
    tft.setTextSize(2); tft.setTextColor(ST7735_GREEN, ST7735_BLACK);
    tft.setCursor(8, 45); tft.print(F("SYSTEM RESET"));
    tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
    tft.setCursor(52, 75); tft.print(F("SUCCESS !"));
    isShowingReset = true;
    resetMessageStartTime = millis();
}

// =================================================================
// ─── Core 0 專用 MQTT 通訊任務 ───
// =================================================================
void networkTask(void *pvParameters) {
    // 忽略 SSL 憑證驗證 (開發測試較方便)
    espClient.setInsecure();
    mqttClient.setServer(mqtt_server, mqtt_port);

    SensorData dataToPublish;

    for (;;) { // FreeRTOS 無窮迴圈
        // 1. 檢查並維持 Wi-Fi 連線
        if (WiFi.status() != WL_CONNECTED) {
            WiFi.begin(ssid, password);
            while (WiFi.status() != WL_CONNECTED) {
                vTaskDelay(500 / portTICK_PERIOD_MS); 
            }
        }

        // 2. 檢查並維持 MQTT 連線
        if (WiFi.status() == WL_CONNECTED && !mqttClient.connected()) {
            // 使用 ESP32 的 MAC 地址作為 Client ID，避免重複
            String clientId = "ESP32_HR_O2_";
            clientId += String(random(0xffff), HEX);
            mqttClient.connect(clientId.c_str(), mqtt_user, mqtt_pass);
            vTaskDelay(500 / portTICK_PERIOD_MS); // 等待連線
        }
        
        mqttClient.loop();

        // 3. 檢查佇列中是否有 Core 1 傳來的新數據
        if (mqttClient.connected()) {
            if (xQueueReceive(dataQueue, &dataToPublish, 0) == pdPASS) {
                // 收到數據，組裝 JSON 格式字串
                char jsonPayload[128];
                const char* sStr = (dataToPublish.status == STATUS_NORMAL) ? "NORMAL" : (dataToPublish.status == STATUS_WARNING ? "WARNING" : "DANGER");
                
                // 組裝 JSON: { "bpm": 79, "spo2": 98, "status": "NORMAL" }
                snprintf(jsonPayload, sizeof(jsonPayload), 
                         "{\n  \"bpm\": %d,\n  \"spo2\": %d,\n  \"status\": \"%s\"\n}", 
                         dataToPublish.bpm, dataToPublish.spo2, sStr);
                
                // 發布至 HiveMQ
                mqttClient.publish(mqtt_topic, jsonPayload);
            }
        }
        
        // 讓出 CPU 時間，避免觸發 Watchdog
        vTaskDelay(10 / portTICK_PERIOD_MS); 
    }
}

void setup(void) {
  pinMode(LED, OUTPUT);
  pinMode(BUTTON, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT); 
  noTone(BUZZER_PIN);
  
  pinMode(TFT_BLK, OUTPUT);     // 背光設定
  digitalWrite(TFT_BLK, HIGH);

  tft.initR(INITR_BLACKTAB);
  tft.setRotation(1); 
  tft.fillScreen(ST7735_BLACK);

  draw_oled(3);
  delay(3000);

  Wire.begin(21, 22);
  if (!sensor.begin())  {
    draw_oled(0);         
    while (1);
  }

  esp_sleep_enable_ext0_wakeup(GPIO_NUM_15, 0);
  sensor.setup();

  // ─── 初始化 Queue 與分配 Core 0 任務 ───
  // 建立長度為 5 的佇列，足夠緩衝來不及發出的資料
  dataQueue = xQueueCreate(5, sizeof(SensorData));
  
  if (dataQueue != NULL) {
      // 將網路處理綁定在 Core 0
      xTaskCreatePinnedToCore(
          networkTask,     // 任務執行的函數
          "NetworkTask",   // 任務名稱
          8192,            // 堆疊大小 (網路通訊需要較大)
          NULL,            // 傳入參數
          1,               // 優先權
          &MqttTaskHandle, // 任務控制代碼
          0                // 綁定到 Core 0
      );
  }
}

long lastBeat = 0;
long displaytime = 0;
bool led_on = false;
uint32_t lastSleepCounterTime = 0; 
unsigned long lastPublishTime = 0; // 控制發送頻率的變數

// =================================================================
// ─── 預設 loop() 綁定在 Core 1，專心處理感測器與畫面 ───
// =================================================================
void loop()  {
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
                sensor.getIR(); sensor.getRed(); sensor.nextSample(); 
            }
            return;
        } else {
            isShowingReset = false; sleep_counter = 0;
            lastSleepCounterTime = millis(); last_msg = -1; draw_oled(1); 
        }
    }

    sensor.check();
    long now = millis();
    if (!sensor.available()) return;
    uint32_t irValue = sensor.getIR();
    uint32_t redValue = sensor.getRed();
    sensor.nextSample();

    if (irValue < 5000) { 
        lastTimerUpdate = 0;
        beatAvg = 0; SPO2 = 0; SPO2f = 0;
        currentStatus = STATUS_NORMAL;
        beepsToPlay = 0; isBuzzerOn = false; noTone(BUZZER_PIN);
        
        int current_msg = (sleep_counter <= 50 ? 1 : 4);
        draw_oled(current_msg);
        
        if (now - lastSleepCounterTime >= 200) {
            lastSleepCounterTime = now;
            ++sleep_counter;
            if (sleep_counter > 100) {
              go_sleep();
              sleep_counter = 0;
            }
        }
    } else {
        sleep_counter = 0;
        int16_t IR_signal  = pulseIR.ma_filter(pulseIR.dc_filter(irValue)); 
        int16_t Red_signal = pulseRed.ma_filter(pulseRed.dc_filter(redValue));
        
        bool beatIR  = pulseIR.isBeat(IR_signal);
        wave.record(-IR_signal);

        if (lastTimerUpdate == 0) lastTimerUpdate = now;
        if (now - lastTimerUpdate >= 1000) {
            totalFingerSeconds++;
            lastTimerUpdate += 1000; 
        }

        if (beatIR){ 
            long btpm = 60000 / (now - lastBeat);
            if (btpm > 0 && btpm < 200) beatAvg = bpm.filter((int16_t)btpm);
            lastBeat = now;
            digitalWrite(LED, HIGH);
            led_on = true;

            long numerator   = (pulseRed.avgAC() * pulseIR.avgDC()) / 256;
            long denominator = (pulseRed.avgDC() * pulseIR.avgAC()) / 256;
            int RX100 = (denominator > 0) ? (numerator * 100) / denominator : 999;
            SPO2f = (10400 - RX100 * 17 + 50) / 100;
            
            if ((RX100 >= 0) && (RX100 < 184))
              SPO2 = pgm_read_byte_near(&spo2_table[RX100]);

            if (SPO2 > 0 && beatAvg > 0) { 
                if (SPO2 < 90 || beatAvg < 50 || beatAvg > 120) {
                    currentStatus = STATUS_DANGER;
                } else if (SPO2 < 95 || beatAvg < 60 || beatAvg > 100) {
                    currentStatus = STATUS_WARNING;
                } else {
                    currentStatus = STATUS_NORMAL;
                }

                // ─── 將有效數據推送至佇列給 Core 0 發送 ───
                // 為了避免每次心跳都發送導致 MQTT 頻寬超載，這裡限制至少相隔 2 秒發送一次
                if (now - lastPublishTime > 2000) {
                    SensorData outData;
                    outData.bpm = beatAvg;
                    outData.spo2 = SPO2;
                    outData.status = currentStatus;
                    
                    // non-blocking 發送：如果佇列滿了就不強迫塞入 (等待時間 0)
                    xQueueSend(dataQueue, &outData, 0); 
                    lastPublishTime = now;
                }
            }
            
            if (currentStatus == STATUS_NORMAL) { beepsToPlay = 1; } 
            else if (currentStatus == STATUS_WARNING) { beepsToPlay = 2; } 
            else if (currentStatus == STATUS_DANGER) { beepsToPlay = 4; }
            
            if (beepsToPlay > 0) {
                isBuzzerOn = true;
                lastBuzzerToggleTime = now;
                tone(BUZZER_PIN, 2000); 
            }
        }

        if (now - displaytime > 50) { 
            displaytime = now;
            wave.scale();
            draw_oled(2);
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
                isBuzzerOn = false;
                lastBuzzerToggleTime = millis();
                beepsToPlay--; 
            }
        } else {
            if (timePassed >= BEEP_OFF_TIME && beepsToPlay > 0) {
                tone(BUZZER_PIN, 2000);
                isBuzzerOn = true;
                lastBuzzerToggleTime = millis();
            }
        }
    } else {
        noTone(BUZZER_PIN);
    }
}