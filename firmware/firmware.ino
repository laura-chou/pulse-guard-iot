#include <Wire.h> 
#include <Adafruit_GFX.h>    // 核心圖形庫
#include <Adafruit_ST7735.h> // ST7735 TFT 驅動庫
#include <SPI.h>
#include "MAX30102.h"
#include "Pulse.h"
#include <pgmspace.h>

// 定義 TFT 接腳
#define TFT_CS     5
#define TFT_DC    16
#define TFT_RST   17

// 初始化 ST7735 TFT 物件 (橫向 160x128)
Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);
MAX30102 sensor;
Pulse pulseIR;
Pulse pulseRed;
MAFilter bpm;

#define LED LED_BUILTIN
#define BUTTON 15  // 按鍵 GPIO 15

// ─── 狀態判斷條件與定義 ───
enum DeviceStatus { STATUS_NORMAL, STATUS_WARNING, STATUS_DANGER };
DeviceStatus currentStatus = STATUS_NORMAL;

// ─── 計時器與動態刷新快取變數 ───
uint32_t totalFingerSeconds = 0; // 累計有手指的量測秒數
uint32_t lastTimerUpdate = 0;    // 上次計時更新的時間點
int last_printed_seconds = -1;   // 上次繪製的秒數快取 (防閃爍)
int last_printed_status = -1;    // 上次繪製的狀態快取 (防閃爍)

// ─── 按鍵偵測與畫面停留變數 ───
unsigned long buttonPressStart = 0;
bool lastButtonState = HIGH;
const unsigned long LONG_PRESS_TIME = 2000; // 長按定義為 2000 毫秒
const unsigned long DEBOUNCE_TIME = 50;     // 按鍵彈跳過濾

bool isShowingReset = false;             // 是否正在顯示重置訊息
unsigned long resetMessageStartTime = 0; // 重置訊息開始顯示的時間點

// (♥) 心率圖標 16x16 XBM
static const uint8_t heart_bits[] PROGMEM = { 
    0x00, 0x00, 0x38, 0x38, 0x7c, 0x7c, 0xfe, 0xfe, 0xfe, 0xff, 
    0xfe, 0xff, 0xfc, 0x7f, 0xf8, 0x3f, 0xf0, 0x1f, 0xe0, 0x0f, 
    0xc0, 0x07, 0x80, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 
    0x00, 0x00 
};

// (O₂) 血氧圖標 16x16 XBM
static const uint8_t o2_bits[] PROGMEM = {
    0xf8, 0x03, 0x0c, 0x06, 0x06, 0x0c, 0x06, 0x0c, 
    0x06, 0x0c, 0x06, 0x0c, 0x0c, 0x76, 0xf8, 0x63, 
    0x00, 0x61, 0x00, 0x30, 0x00, 0x1c, 0x00, 0x7f, 
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};

const uint8_t spo2_table[184] PROGMEM = { 
    95, 95, 95, 96, 96, 96, 97, 97, 97, 97, 97, 98, 98, 98, 98, 98, 99, 99, 99, 99, 
    99, 99, 99, 99, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 
    100, 100, 100, 100, 99, 99, 99, 99, 99, 99, 99, 99, 98, 98, 98, 98, 98, 98, 97, 97, 
    97, 97, 96, 96, 96, 96, 95, 95, 95, 94, 94, 94, 93, 93, 93, 92, 92, 92,
    91, 91, 
    90, 90, 89, 89, 89, 88, 88, 87, 87, 86, 86, 85, 85, 84, 84, 83, 82, 82, 81, 81, 
    80, 80, 79, 78, 78, 77, 76, 76, 75, 74, 74, 73, 72, 72, 71, 70, 69, 69, 68, 67, 
    66, 66, 65, 64, 63, 62, 62, 
    61, 60, 59, 58, 57, 56, 56, 55, 54, 53, 52, 51, 50, 
    49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36,
    35, 34, 33, 31, 
    30, 29, 
    28, 27, 26, 25, 23, 22, 21, 20, 19, 17, 16, 15, 14, 12, 11, 10, 9, 7, 6, 5, 
    3, 2, 1
};

const uint8_t MAXWAVE = 160; // 配合橫向螢幕寬度
class Waveform {
  public:
    Waveform(void) { 
        wavep = 0;
        memset(waveform, 128, MAXWAVE);
    } 

    void record(int waveval) {
        waveval = waveval / 8;
        waveval += 128;
        waveval = waveval < 0 ? 0 : (waveval > 255 ? 255 : waveval);
        waveform[wavep] = (uint8_t)waveval;
        wavep = (wavep + 1) % MAXWAVE;
    }
  
    void scale() {
        uint8_t maxw = 0;
        uint8_t minw = 255;
        for (int i = 0; i < MAXWAVE; i++) { 
            maxw = waveform[i] > maxw ? waveform[i] : maxw;
            minw = waveform[i] < minw ? waveform[i] : minw;
        }
        uint8_t range = maxw - minw;
        if (range == 0) range = 1;

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
        
        // 切換模式時，重置局部刷新快取
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
            tft.setTextSize(2);
            tft.setTextColor(ST7735_RED, ST7735_BLACK);
            tft.setCursor(8, 45); tft.print(F("DEVICE ERROR"));
            tft.setTextSize(1); tft.setCursor(35, 75); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
            tft.print(F("Check I2C Wire!"));
            break;

        case 1: 
            tft.setTextSize(2);
            tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            tft.setCursor(50, 45); tft.print(F("PLACE"));
            tft.setCursor(44, 70); tft.print(F("FINGER"));
            
            tft.fillRect(0, 108, 160, 20, ST7735_BLACK);
            tft.setTextSize(1); tft.setTextColor(ST7735_GREEN, ST7735_BLACK);
            tft.setCursor(20, 113);
            tft.print(F("Mode: IR Filter: Avg"));
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
                    
                    if (currentStatus == STATUS_WARNING) {
                        dotColor = ST7735_YELLOW;
                        statusStr = "WARNING";
                    } else if (currentStatus == STATUS_DANGER) {
                        dotColor = ST7735_RED;
                        statusStr = "DANGER";
                    }
                    
                    tft.fillCircle(8, 7, 3, dotColor);
                    tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
                    tft.setCursor(18, 4);
                    tft.print(statusStr);
                }
                
                if ((int)totalFingerSeconds != last_printed_seconds) {
                    last_printed_seconds = (int)totalFingerSeconds;
                    tft.fillRect(120, 0, 40, 15, ST7735_BLACK); 
                    
                    int mins = totalFingerSeconds / 60;
                    int secs = totalFingerSeconds % 60;
                    
                    tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
                    tft.setCursor(125, 4);
                    if (mins < 10) tft.print('0');
                    tft.print(mins);
                    tft.print(':');
                    if (secs < 10) tft.print('0');
                    tft.print(secs);
                }
            }
            
            // ─── 下方大數字動態局部刷新 (含修復沒數據留白問題) ───
            // 【左半邊：心率數值】
            if (beatAvg != last_printed_bpm) {
                last_printed_bpm = beatAvg;
                tft.fillRect(5, 82, 70, 24, ST7735_BLACK);
                
                tft.setTextSize(3);
                tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
                if (beatAvg > 0) {
                    int numDigits = (beatAvg < 10) ? 1 : ((beatAvg < 100) ? 2 : 3);
                    int numWidth = numDigits * 18;
                    int numX = (80 - numWidth) / 2;
                    tft.setCursor(numX, 82);
                    tft.print(beatAvg);
                } else {
                    // 若數據尚在計算(等於0)，顯示 "---" 佔位符
                    int numWidth = 3 * 18;
                    int numX = (80 - numWidth) / 2;
                    tft.setCursor(numX, 82);
                    tft.print(F("---"));
                }
            }
            
            // 【右半邊：血氧數值】
            if (SPO2 != last_printed_spo2) {
                last_printed_spo2 = SPO2;
                tft.fillRect(85, 82, 70, 24, ST7735_BLACK);
                
                tft.setTextSize(3);
                tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
                if (SPO2 > 0) {
                    int numDigits = (SPO2 < 10) ? 1 : ((SPO2 < 100) ? 2 : 3);
                    int numWidth = numDigits * 18;
                    int numX = 80 + (80 - numWidth) / 2;
                    tft.setCursor(numX, 82);
                    tft.print(SPO2);
                } else {
                    // 若數據尚在計算(等於0)，顯示 "---" 佔位符
                    int numWidth = 3 * 18;
                    int numX = 80 + (80 - numWidth) / 2;
                    tft.setCursor(numX, 82);
                    tft.print(F("---"));
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
            tft.setTextSize(2);
            tft.setTextColor(ST7735_RED, ST7735_BLACK);
            tft.setCursor(26, 45);
            tft.print(F("POWER OFF"));
            {
                int secondsLeft = (100 - sleep_counter) / 5;
                tft.fillRect(50, 75, 60, 32, ST7735_BLACK);
                int startX = (secondsLeft == 10) ? 56 : 68;
                tft.setTextSize(4);
                tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
                tft.setCursor(startX, 75);
                tft.print(secondsLeft);
            }
            break;
    }
}

// ─── 按鈕操作：短按 ───
void handleShortPress() {
    sleep_counter = 0; 
    last_msg = -1; 
    draw_oled(1);  
}

// ─── 按鈕操作：長按 8 項 Reset 功能 (無阻塞安全版) ───
void handleLongPress() {
    beatAvg = 0;
    SPO2 = 0;
    SPO2f = 0;
    last_printed_bpm = -1;
    last_printed_spo2 = -1;

    digitalWrite(LED, LOW);
    
    totalFingerSeconds = 0;
    lastTimerUpdate = 0;
    last_printed_seconds = -1;

    currentStatus = STATUS_NORMAL;
    last_printed_status = -1;

    // 顯示成功重置畫面
    tft.fillScreen(ST7735_BLACK);
    tft.setTextSize(2);
    tft.setTextColor(ST7735_GREEN, ST7735_BLACK);
    tft.setCursor(8, 45); 
    tft.print(F("SYSTEM RESET"));
    tft.setTextSize(1);
    tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
    tft.setCursor(52, 75);
    tft.print(F("SUCCESS !"));

    isShowingReset = true;
    resetMessageStartTime = millis();
}

void setup(void) {
  pinMode(LED, OUTPUT);
  pinMode(BUTTON, INPUT_PULLUP);

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
}

long lastBeat = 0;
long displaytime = 0;
bool led_on = false;
uint32_t lastSleepCounterTime = 0; 

void loop()  {
    // ─── 1. 按鍵狀態掃描 ───
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

    // ─── 2. 攔截與清空感測器 Buffer (防卡死機制) ───
    if (isShowingReset) {
        if (millis() - resetMessageStartTime < 1500) {
            sensor.check();
            while (sensor.available()) {
                sensor.getIR();
                sensor.getRed();
                sensor.nextSample(); 
            }
            return; 
        } else {
            isShowingReset = false;
            sleep_counter = 0;
            lastSleepCounterTime = millis();
            last_msg = -1;
            draw_oled(1); 
        }
    }

    // ─── 3. 感測器量測核心邏輯 ───
    sensor.check();
    long now = millis();
    if (!sensor.available()) return;
    uint32_t irValue = sensor.getIR();
    uint32_t redValue = sensor.getRed();
    sensor.nextSample();

    if (irValue < 5000) { 
        lastTimerUpdate = 0; 
        
        // 【新增優化】當手指離開，主動將數據清空為 0
        // 確保下一次重新量測時，數據從 "---" 乾淨地重新計算，不閃爍舊資料
        beatAvg = 0;
        SPO2 = 0;
        SPO2f = 0;
        currentStatus = STATUS_NORMAL;
        
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

        if (lastTimerUpdate == 0) {
            lastTimerUpdate = now; 
        }
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
}