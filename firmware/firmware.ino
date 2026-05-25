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

// 初始化 ST7735 TFT 物件 (1.8吋 128x160)
Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);

MAX30102 sensor;
Pulse pulseIR;
Pulse pulseRed;
MAFilter bpm;

#define LED LED_BUILTIN
#define BUTTON 15  // 按鍵 GPIO 15 (僅保留休眠喚醒功能)

static const uint8_t heart_bits[] PROGMEM = { 
    0x00, 0x00, 0x38, 0x38, 0x7c, 0x7c, 0xfe, 0xfe, 0xfe, 0xff, 
    0xfe, 0xff, 0xfc, 0x7f, 0xf8, 0x3f, 0xf0, 0x1f, 0xe0, 0x0f, 
    0xc0, 0x07, 0x80, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 
    0x00, 0x00 
};

const uint8_t spo2_table[184] PROGMEM = { 
    95, 95, 95, 96, 96, 96, 97, 97, 97, 97, 97, 98, 98, 98, 98, 98, 99, 99, 99, 99, 
    99, 99, 99, 99, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 
    100, 100, 100, 100, 99, 99, 99, 99, 99, 99, 99, 99, 98, 98, 98, 98, 98, 98, 97, 97, 
    97, 97, 96, 96, 96, 96, 95, 95, 95, 94, 94, 94, 93, 93, 93, 92, 92, 92, 91, 91, 
    90, 90, 89, 89, 89, 88, 88, 87, 87, 86, 86, 85, 85, 84, 84, 83, 82, 82, 81, 81, 
    80, 80, 79, 78, 78, 77, 76, 76, 75, 74, 74, 73, 72, 72, 71, 70, 69, 69, 68, 67, 
    66, 66, 65, 64, 63, 62, 62, 
    61, 60, 59, 58, 57, 56, 56, 55, 54, 53, 52, 51, 50, 
    49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 31, 30, 29, 
    28, 27, 26, 25, 23, 22, 21, 20, 19, 17, 16, 15, 14, 12, 11, 10, 9, 7, 6, 5, 
    3, 2, 1 
};

const uint8_t MAXWAVE = 120; 
class Waveform {
  public:
    Waveform(void) { wavep = 0; memset(waveform, 128, MAXWAVE); } 

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
            disp_wave[i] = 68 - ((uint16_t)(waveform[index] - minw) * 44) / range; 
            index = (index + 1) % MAXWAVE; 
        }
    }

    void draw(uint8_t X) {
        tft.fillRect(X, 22, MAXWAVE, 48, ST7735_BLACK); 
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

void draw_oled(int msg) {
    if (msg != last_msg) {
        tft.fillScreen(ST7735_BLACK);
        last_msg = msg;
        
        if (msg == 2) {
            tft.fillRect(0, 0, 128, 20, ST7735_BLUE);
            tft.setTextSize(1);
            tft.setTextColor(ST7735_WHITE, ST7735_BLUE);
            tft.setCursor(4, 6); tft.print(F("PULSE OXIMETER  IR-Avg"));
            
            tft.drawFastHLine(0, 72, 128, ST7735_WHITE);
            
            tft.drawXBitmap(6, 88, heart_bits, 16, 16, ST7735_RED);
            tft.setTextColor(ST7735_RED, ST7735_BLACK);
            tft.setCursor(26, 92); tft.print(F("BPM"));
            
            tft.setTextColor(ST7735_CYAN, ST7735_BLACK);
            tft.setCursor(6, 134); tft.print(F("SpO2"));
            tft.setTextSize(2);
            tft.setCursor(112, 130); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            tft.print(F("%"));
        }
    }

    switch(msg){
        case 0: 
            tft.setTextSize(2); tft.setTextColor(ST7735_RED, ST7735_BLACK);
            tft.setCursor(10, 60); tft.print(F("DEVICE ERROR")); 
            tft.setTextSize(1); tft.setCursor(16, 90); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
            tft.print(F("Check I2C Wire!"));
            break;
            
        case 1: 
            tft.fillRect(0, 0, 128, 20, 0x52AA); 
            tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, 0x52AA);
            tft.setCursor(34, 6); tft.print(F("STATUS BAR"));
            
            tft.setTextSize(2); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            tft.setCursor(34, 50); tft.print(F("PLACE")); 
            tft.setCursor(28, 75); tft.print(F("FINGER"));
            
            tft.fillRect(0, 140, 128, 20, ST7735_BLACK);
            tft.setTextSize(1); tft.setTextColor(ST7735_GREEN, ST7735_BLACK);
            tft.setCursor(16, 145); tft.print(F("Mode: IR Filter: Avg"));
            break;
            
        case 2: 
            wave.draw(4); 
            
            tft.setTextSize(4); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
            tft.setCursor(52, 80);
            if (beatAvg < 10) tft.print(F("  "));
            else if (beatAvg < 100) tft.print(F(" "));
            tft.print(beatAvg); 
            
            tft.setTextSize(4); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            tft.setCursor(52, 120);
            if (SPO2 < 10) tft.print(F("  "));
            else if (SPO2 < 100) tft.print(F(" "));
            tft.print(SPO2); 
            break;
            
        case 3: 
            tft.drawXBitmap(48, 30, heart_bits, 16, 16, ST7735_RED);
            tft.setTextSize(2); tft.setTextColor(ST7735_CYAN, ST7735_BLACK);
            tft.setCursor(16, 65);  tft.print(F("HEART RATE")); 
            tft.setCursor(22, 90);  tft.print(F("OXYMETER")); 
            tft.setTextSize(1); tft.setTextColor(ST7735_WHITE, ST7735_BLACK);
            tft.setCursor(34, 130); tft.print(F("Initializing..."));
            break;
            
        case 4: 
            tft.setTextSize(2); tft.setTextColor(ST7735_RED, ST7735_BLACK);
            tft.setCursor(28, 50); tft.print(F("POWER OFF")); 
            tft.setTextSize(4); tft.setTextColor(ST7735_YELLOW, ST7735_BLACK);
            tft.setCursor(40, 85); tft.print(10 - sleep_counter / 10);
            tft.setTextSize(2); tft.print(F("s"));
            break;
    }
}

void setup(void) {
  pinMode(LED, OUTPUT); 
  pinMode(BUTTON, INPUT_PULLUP); 

  tft.initR(INITR_BLACKTAB); 
  tft.setRotation(0); 
  tft.fillScreen(ST7735_BLACK);

  draw_oled(3); 
  delay(3000); 

  Wire.begin(21, 22); 
  
  if (!sensor.begin())  { 
    draw_oled(0);         
    while (1); 
  }

  // 💡 已移除 attachInterrupt 中斷綁定，按鈕在開機狀態下無任何作用
  esp_sleep_enable_ext0_wakeup(GPIO_NUM_15, 0); // 僅保留 Deep Sleep 的喚醒配置
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