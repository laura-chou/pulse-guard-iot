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
#define BUTTON 15  // 按鍵 GPIO 15 (僅保留休眠喚醒功能)

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
    49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 31, 
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
            // 因應數據區下移，波形顯示區限制擴大至 Y: 16 ~ 74 以內 (高度 59px)
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

int  beatAvg;
int  SPO2, SPO2f;
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
        
        if (msg == 2) {
            // ─── 頂部狀態列背景 (0 ~ 15px) ───
            tft.fillRect(0, 0, 160, 15, ST7735_BLUE);
            tft.setTextSize(1);
            tft.setTextColor(ST7735_WHITE, ST7735_BLUE);
            tft.setCursor(4, 4); tft.print(F("PULSE OXIMETER  IR-Avg"));
            
            // ─── 全新 UI 分割線系統 (下移至 75) ───
            tft.drawFastHLine(0, 15, 160, ST7735_WHITE); // 狀態列與波形分隔線 (Y:15)
            tft.drawFastHLine(0, 75, 160, ST7735_WHITE); // 波形與數據區分隔線 (下移至 Y:75)
            tft.drawFastVLine(80, 75, 53, ST7735_WHITE); // 左右數據中央分隔線 (X:80, 高53px)

            // ─── 下方 Icon 與單位並排絕對水平置中 (單次固定渲染，永不消失與閃爍) ───
            // 左側 (♥ BPM) -> 總寬 38px -> 起始 X: (80-38)/2 = 21
            tft.drawXBitmap(21, 110, heart_bits, 16, 16, ST7735_RED);
            tft.setTextSize(1); tft.setTextColor(ST7735_RED, ST7735_BLACK);
            tft.setCursor(21 + 16 + 4, 114); tft.print(F("BPM"));

            // 右側 (O₂ %) -> 總寬 26px -> 起始 X: 80 + (80-26)/2 = 107
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
            tft.setCursor(20, 113); tft.print(F("Mode: IR Filter: Avg"));
            break;

        case 2: 
            wave.draw(0); // 繪製波形區
            
            // ─── 上方中數字動態絕對置中刷新 (下移至 Y: 82，僅局部重繪數字) ───
            
            // 【左半邊：心率數值】
            if (beatAvg != last_printed_bpm) {
                last_printed_bpm = beatAvg;
                tft.fillRect(5, 82, 70, 24, ST7735_BLACK); // 僅精準清除舊數字區，絕不影響下方圖標
                
                int numDigits = (beatAvg < 10) ? 1 : ((beatAvg < 100) ? 2 : 3);
                int numWidth = numDigits * 18; // Size 3 字元寬 18px
                int numX = (80 - numWidth) / 2;
                
                tft.setTextSize(3);
                tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
                tft.setCursor(numX, 82);
                tft.print(beatAvg);
            }
            
            // 【右半邊：血氧數值】
            if (SPO2 != last_printed_spo2) {
                last_printed_spo2 = SPO2;
                tft.fillRect(85, 82, 70, 24, ST7735_BLACK); // 僅精準清除舊數字區
                
                int numDigits = (SPO2 < 10) ? 1 : ((SPO2 < 100) ? 2 : 3);
                int numWidth = numDigits * 18;
                int numX = 80 + (80 - numWidth) / 2;
                
                tft.setTextSize(3);
                tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
                tft.setCursor(numX, 82);
                tft.print(SPO2);
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
            tft.setCursor(26, 45); tft.print(F("POWER OFF")); 
            
            // 10 到 0 的純數字精準流暢倒數
            {
                int secondsLeft = (100 - sleep_counter) / 5;
                // 每 5 步(200ms*5)為 1 秒，精確由 10 倒數至 0
                tft.fillRect(50, 75, 60, 32, ST7735_BLACK);
                // 局部清除舊殘影數字
                
                // Size 4 字元寬度為 24px，計算純數字水平置中座標
                int startX = (secondsLeft == 10) ? 56 : 68; 
                
                tft.setTextSize(4); 
                tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
                tft.setCursor(startX, 75); 
                tft.print(secondsLeft);
            }
            break;
    }
}

void setup(void) {
  pinMode(LED, OUTPUT); 
  pinMode(BUTTON, INPUT_PULLUP); 

  tft.initR(INITR_BLACKTAB); 
  tft.setRotation(1); // 橫向 160x128 模式
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

void loop()  {
    sensor.check();
    long now = millis(); 

    if (!sensor.available()) return; 
    uint32_t irValue = sensor.getIR(); 
    uint32_t redValue = sensor.getRed(); 
    sensor.nextSample();

    if (irValue < 5000) { 
        draw_oled(sleep_counter <= 50 ? 1 : 4);
        delay(200); 
        ++sleep_counter;
        if (sleep_counter > 100) { 
          go_sleep();
          sleep_counter = 0; 
        }
    } else {
        sleep_counter = 0;
        int16_t IR_signal  = pulseIR.ma_filter(pulseIR.dc_filter(irValue));  
        int16_t Red_signal = pulseRed.ma_filter(pulseRed.dc_filter(redValue)); 
        
        bool beatIR  = pulseIR.isBeat(IR_signal); 
        wave.record(-IR_signal);

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