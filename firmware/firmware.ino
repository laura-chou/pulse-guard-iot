#include <Adafruit_GFX.h>    // 核心圖形庫
#include <Adafruit_ST7735.h> // ST7735 TFT 驅動庫
#include <SPI.h>
#include "MAX30102.h"
#include "Pulse.h"
#include <pgmspace.h>
#include <EEPROM.h>

// 定義 TFT 接腳
#define TFT_CS     5
#define TFT_DC    16
#define TFT_RST   17

// 初始化 ST7735 TFT 物件
Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);

MAX30102 sensor;
Pulse pulseIR;
Pulse pulseRed;
MAFilter bpm;

#define LED LED_BUILTIN
#define BUTTON 15  // 按鍵 GPIO 15
#define OPTIONS 7  // EEPROM 讀寫位址

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

// 改用 TFT 的 drawChar 機制，並設定背景色為黑色以防閃爍
void print_digit(int x, int y, long val, char c=' ', uint8_t field = 3, const int BIG = 2) {  
    uint8_t ff = field;
    do { 
        char ch = (val!=0) ? val%10+'0': c; 
        tft.drawChar(x+BIG*(ff-1)*6, y, ch, ST7735_WHITE, ST7735_BLACK, BIG); // 帶有背景色刷新
        val = val/10; 
        --ff;
    } while (ff>0); 
}

const uint8_t MAXWAVE = 72; 
class Waveform {
  public:
    Waveform(void) {wavep = 0;} 

    void record(int waveval) {
        waveval = waveval/8; 
        waveval += 128; 
        waveval = waveval<0? 0 : waveval; 
        waveform[wavep] = (uint8_t) (waveval>255)?255:waveval; 
        wavep = (wavep+1) % MAXWAVE; 
    }
  
    void scale() {
        uint8_t maxw = 0;
        uint8_t minw = 255; 
        for (int i=0; i<MAXWAVE; i++) { 
            maxw = waveform[i]>maxw?waveform[i]:maxw; 
            minw = waveform[i]<minw?waveform[i]:minw; 
        }
        uint8_t scale8 = (maxw-minw)/4 + 1;
        uint8_t index = wavep; 
        for (int i=0; i<MAXWAVE; i++) {
            disp_wave[i] = 31-((uint16_t)(waveform[index]-minw)*8)/scale8; 
            index = (index + 1) % MAXWAVE; 
        }
    }

    void draw(uint8_t X) {
        // 在繪製新波形前，局部清空波形顯示區域（X到X+MAXWAVE, Y從0到32）避免殘影
        tft.fillRect(X, 0, MAXWAVE, 32, ST7735_BLACK); 

        for (int i=0; i<MAXWAVE; i++) {
            uint8_t y = disp_wave[i];
            tft.drawPixel(X+i, y, ST7735_GREEN); // 改成亮綠色波形
            if (i<MAXWAVE-1) {
                uint8_t nexty = disp_wave[i+1]; 
                if (nexty>y) {
                    for (uint8_t iy = y+1; iy<nexty; ++iy)  
                        tft.drawPixel(X+i, iy, ST7735_GREEN); 
                } 
                else if (nexty<y) {
                    for (uint8_t iy = nexty+1; iy<y; ++iy)  
                        tft.drawPixel(X+i, iy, ST7735_GREEN); 
                }
            }
        } 
    }

  private:
    uint8_t waveform[MAXWAVE];
    uint8_t disp_wave[MAXWAVE];
    uint8_t wavep = 0; 
} wave;

int  beatAvg;
int  SPO2, SPO2f;
int  voltage;
bool filter_for_graph = false;
bool draw_Red = false; 
uint8_t pcflag =0;
uint8_t istate = 0;
uint8_t sleep_counter = 0; 

void button(void){ 
    pcflag = 1; 
}

void checkbutton(){ 
    if (pcflag == 1 && digitalRead(BUTTON) == LOW) {
        istate = (istate +1) % 4; 
        filter_for_graph = istate & 0x01; 
        draw_Red = istate & 0x02;
        EEPROM.write(OPTIONS, filter_for_graph); 
        EEPROM.write(OPTIONS+1, draw_Red); 
        EEPROM.commit(); // 修正：ESP32 必須執行 commit 才會真正寫入 Flash
    }
    pcflag = 0; 
}

void Display_5(){ 
   if(pcflag == 1 && digitalRead(BUTTON) == LOW){
     draw_oled(5); 
     delay(3000); 
     ESP.restart();
   }
   pcflag = 0; 
}

void go_sleep() { 
    tft.fillScreen(ST7735_BLACK);
    tft.enableDisplay(false); // 關閉 TFT 顯示驅動省電
    delay(10);
    sensor.off(); 
    delay(10); 
    pinMode(0,INPUT);
    pinMode(2,INPUT);
    esp_deep_sleep_start();
}

int last_msg = -1; // 用來記錄上一次的畫面狀態

void draw_oled(int msg) {
    // 只有當頁面狀態改變時才清除全螢幕，防止動態重繪時劇烈閃爍
    if (msg != last_msg) {
        tft.fillScreen(ST7735_BLACK);
        last_msg = msg;
    }

    tft.setTextSize(1);
    tft.setTextColor(ST7735_WHITE, ST7735_BLACK); // 設定文字前景與背景色

    switch(msg){
        case 0:  
            tft.setCursor(10, 0); tft.setTextColor(ST7735_RED, ST7735_BLACK);
            tft.print(F("Device error")); 
            break;
        case 1:  
            tft.setCursor(13, 10); tft.print(F("PLACE")); 
            tft.setCursor(10, 20); tft.print(F("FINGER"));
            tft.setCursor(84, 14); tft.print(F("Display")); 
            tft.setCursor(84, 24);
            if (draw_Red) tft.print(F("Red")); else tft.print(F("IR ")); // 加空格覆蓋舊字
            tft.setCursor(108, 24); 
            if (filter_for_graph) tft.print(F("Avg")); else tft.print(F("Raw")); 
            break;
        case 2:  
            print_digit(86, 0, beatAvg); 
            wave.draw(8); 
            print_digit(98, 16, SPO2f, ' ', 3, 1); 
            tft.drawChar(116, 16, '%', ST7735_YELLOW, ST7735_BLACK, 1);
            print_digit(98, 24, SPO2, ' ', 3, 1); 
            tft.drawChar(116, 24, '%', ST7735_YELLOW, ST7735_BLACK, 1);
            break;
        case 3:  
            tft.setTextColor(ST7735_CYAN, ST7735_BLACK);
            tft.setCursor(30, 9);  tft.print(F("Heart-Rate&")); 
            tft.setCursor(30, 20); tft.print(F("Blood Oxygen")); 
            tft.drawXBitmap(6, 8, heart_bits, 16, 16, ST7735_RED); // 畫出紅色的愛心
            break;
        case 4:  
            tft.setCursor(28, 12); tft.print(F("OFF IN")); 
            tft.drawChar(76, 12, 10-sleep_counter/10+'0', ST7735_YELLOW, ST7735_BLACK, 1);
            tft.drawChar(82, 12, 's', ST7735_YELLOW, ST7735_BLACK, 1); 
            break;
        case 5:  
            tft.setCursor(0, 0); tft.print(F("BMP:")); 
            print_digit(25, 0, beatAvg);
            tft.setCursor(0, 15); tft.print(F("SpO2:")); 
            print_digit(25, 15, SPO2);
            tft.drawXBitmap(106, 8, heart_bits, 16, 16, ST7735_RED);
            break;
    }
}

void setup(void) {
  pinMode(LED, OUTPUT); 
  pinMode(BUTTON, INPUT_PULLUP); 

  EEPROM.begin(32); // 初始化 ESP32 的 EEPROM 模擬空間
  filter_for_graph = EEPROM.read(OPTIONS);  
  draw_Red = EEPROM.read(OPTIONS+1); 

  // 初始化 ST7735 螢幕
  tft.initR(INITR_BLACKTAB); 
  tft.setRotation(0); // 0度直向（寬128, 高160），維持原 OLED 的寬度比例
  tft.fillScreen(ST7735_BLACK);

  draw_oled(3); 
  delay(3000); 

  Wire.begin(21, 22);
  
  if (!sensor.begin())  { 
    draw_oled(0);         
    while (1); 
  }

  attachInterrupt(15, button, FALLING);  
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

    if (irValue<5000) { 
        checkbutton();
        draw_oled(sleep_counter<=50 ? 1 : 4); 
        delay(200); 
        ++sleep_counter;
        if (sleep_counter>100) { 
          go_sleep(); 
          sleep_counter = 0; 
        }
    } else {
        sleep_counter = 0; 
        int16_t IR_signal, Red_signal;
        bool beatRed, beatIR; 

        // 修正：將訊號對調回來（IR對IR，Red對Red）
        if (!filter_for_graph) {
            IR_signal =  pulseIR.dc_filter(irValue);  
            Red_signal = pulseRed.dc_filter(redValue); 
            beatRed = pulseRed.isBeat(pulseRed.ma_filter(Red_signal)); 
            beatIR =  pulseIR.isBeat(pulseIR.ma_filter(IR_signal)); 
        } else {
            IR_signal =  pulseIR.ma_filter(pulseIR.dc_filter(irValue));  
            Red_signal = pulseRed.ma_filter(pulseRed.dc_filter(redValue)); 
            beatRed = pulseRed.isBeat(Red_signal); 
            beatIR =  pulseIR.isBeat(IR_signal); 
        }

        wave.record(draw_Red ? -Red_signal : -IR_signal ); 
   
        if (draw_Red ? beatRed : beatIR){ 
            long btpm = 60000/(now - lastBeat); 
            if (btpm > 0 && btpm < 200) beatAvg = bpm.filter((int16_t)btpm); 
            lastBeat = now; 
            digitalWrite(LED, HIGH); 
            led_on = true; 

            long numerator   = (pulseRed.avgAC() * pulseIR.avgDC())/256; 
            long denominator = (pulseRed.avgDC() * pulseIR.avgAC())/256; 
            int RX100 = (denominator>0) ? (numerator * 100)/denominator : 999; 

            SPO2f = (10400 - RX100*17+50)/100; 
            if ((RX100>=0) && (RX100<184)) 
              SPO2 = pgm_read_byte_near(&spo2_table[RX100]); 
        }

        if (now-displaytime>50) { 
            displaytime = now;
            wave.scale(); 
            draw_oled(2);
        }
        Display_5(); 
    }

    if (led_on && (now - lastBeat)>25){ 
        digitalWrite(LED, LOW);
        led_on = false; 
    }
}