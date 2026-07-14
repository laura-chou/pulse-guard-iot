#include "ssd1306h.h"
#include "MAX30102.h"
#include "Pulse.h"
#include <pgmspace.h>
#include <EEPROM.h>

SSD1306 oled;  
MAX30102 sensor;
Pulse pulseIR;
Pulse pulseRed;
MAFilter bpm;

#define LED LED_BUILTIN
#define BUTTON 15  //按鍵GPIO 15
#define OPTIONS 7 // address for EEPROM read/write 

static const uint8_t heart_bits[] PROGMEM = { 0x00, 0x00, 0x38, 0x38, 0x7c, 0x7c, 0xfe, 0xfe, 0xfe, 0xff, 
                                        0xfe, 0xff, 0xfc, 0x7f, 0xf8, 0x3f, 0xf0, 0x1f, 0xe0, 0x0f,
                                        0xc0, 0x07, 0x80, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 
                                        0x00, 0x00 }; //heart icon

//spo2_table is approximated as  -45.060*ratioAverage* ratioAverage + 30.354 *ratioAverage + 94.845 ;
const uint8_t spo2_table[184] PROGMEM =
        { 95, 95, 95, 96, 96, 96, 97, 97, 97, 97, 97, 98, 98, 98, 98, 98, 99, 99, 99, 99, 
          99, 99, 99, 99, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 
          100, 100, 100, 100, 99, 99, 99, 99, 99, 99, 99, 99, 98, 98, 98, 98, 98, 98, 97, 97, 
          97, 97, 96, 96, 96, 96, 95, 95, 95, 94, 94, 94, 93, 93, 93, 92, 92, 92, 91, 91, 
          90, 90, 89, 89, 89, 88, 88, 87, 87, 86, 86, 85, 85, 84, 84, 83, 82, 82, 81, 81, 
          80, 80, 79, 78, 78, 77, 76, 76, 75, 74, 74, 73, 72, 72, 71, 70, 69, 69, 68, 67, 
          66, 66, 65, 64, 63, 62, 62, 61, 60, 59, 58, 57, 56, 56, 55, 54, 53, 52, 51, 50, 
          49, 48, 47, 46, 45, 44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 31, 30, 29, 
          28, 27, 26, 25, 23, 22, 21, 20, 19, 17, 16, 15, 14, 12, 11, 10, 9, 7, 6, 5, 
          3, 2, 1 } ;


void print_digit(int x, int y, long val, char c=' ', uint8_t field = 3,const int BIG = 2)
    {  
    uint8_t ff = field;
    do { 
        char ch = (val!=0) ? val%10+'0': c;
        oled.drawChar( x+BIG*(ff-1)*6, y, ch, BIG);
        val = val/10; 
        --ff;
    } while (ff>0);
}


/*
 *   Record, scale  and display PPG Wavefoem
 */
const uint8_t MAXWAVE = 72;

class Waveform {
  public:
    Waveform(void) {wavep = 0;}

      void record(int waveval) {
        waveval = waveval/8;         // scale to fit in byte  
        waveval += 128;              //shift so entired waveform is +ve  
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
        uint8_t scale8 = (maxw-minw)/4 + 1;  //scale * 8 to preserve precision
        uint8_t index = wavep;
        for (int i=0; i<MAXWAVE; i++) {
          disp_wave[i] = 31-((uint16_t)(waveform[index]-minw)*8)/scale8;
          index = (index + 1) % MAXWAVE;
        }
      }

void draw(uint8_t X) {
  for (int i=0; i<MAXWAVE; i++) {
    uint8_t y = disp_wave[i];
    oled.drawPixel(X+i, y);
    if (i<MAXWAVE-1) {
      uint8_t nexty = disp_wave[i+1];
      if (nexty>y) {
        for (uint8_t iy = y+1; iy<nexty; ++iy)  
        oled.drawPixel(X+i, iy);
        } 
        else if (nexty<y) {
          for (uint8_t iy = nexty+1; iy<y; ++iy)  
          oled.drawPixel(X+i, iy);
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

void button(void){ //觸發旗標
    pcflag = 1;
}

void checkbutton(){ // MODE /IR RAW/IR AVG/RED RAW/RED AVG
    if (pcflag == 1 && digitalRead(BUTTON) == LOW) {
      istate = (istate +1) % 4;
      filter_for_graph = istate & 0x01;
      draw_Red = istate & 0x02;
      EEPROM.write(OPTIONS, filter_for_graph);  //EEPROM.write(address, value)
      EEPROM.write(OPTIONS+1, draw_Red);
    }
    pcflag = 0; //旗標復位
}



void Display_5(){ //畫出現在讀到的 BMP & SPO2
   if(pcflag == 1 && digitalRead(BUTTON) == LOW){
     draw_oled(5);
     delay(3000);
     ESP.restart();
   }
   pcflag = 0;
}

void go_sleep() { //休眠模式 省電模式
    oled.fill(0);
    oled.off();
    delay(10);
    sensor.off();
    delay(10);
    delay(10);
    pinMode(0,INPUT);
    pinMode(2,INPUT);
    esp_deep_sleep_start();
    // cause reset
}
// 
void draw_oled(int msg) {
    oled.firstPage();
    do{
    switch(msg){
        case 0:  oled.drawStr(10,0,F("Device error"),1);  //max30102 init fail
                 break;
        case 1:  oled.drawStr(13,10,F("PLACE"),1);        //閒置畫面
                 oled.drawStr(10,20,F("FINGER"),1);
                 oled.drawStr(84,14,F("Display"),1); 
                 if (draw_Red) 
                    oled.drawStr(84,24,F("Red"),1); 
                 else
                    oled.drawStr(84,24,F("IR"),1); 
                 if (filter_for_graph) 
                    oled.drawStr(108,24,F("Avg"),1); 
                 else
                    oled.drawStr(108,24,F("Raw"),1); 
                 break;
        case 2:  print_digit(86,0,beatAvg); //畫出波形、顯示心率、SPO2
                 wave.draw(8);
                 print_digit(98,16,SPO2f,' ',3,1);
                 oled.drawChar(116,16,'%',1);
                 print_digit(98,24,SPO2,' ',3,1);
                 oled.drawChar(116,24,'%',1);
                 break;
        case 3:  oled.drawStr(30,9,F("Heart-Rate&"),1); //開機畫面
                 oled.drawStr(30,20,F("Blood Oxygen"),1);
                 oled.drawXBMP(6,8,16,16,heart_bits);
                
                 break;
        case 4:  oled.drawStr(28,12,F("OFF IN"),1);     //顯示休眠到數計時
                 oled.drawChar(76,12,10-sleep_counter/10+'0',1);
                 oled.drawChar(82,12,'s',1);
                 break;
        case 5:  oled.drawStr(0,0,F("BMP:"),1);  //顯示當下BMP和SPO2
                 print_digit(25,0,beatAvg);
                 oled.drawStr(0,15,F("SpO2:"),1); 
                 print_digit(25,15,SPO2);
                 oled.drawXBMP(106,8,16,16,heart_bits);
                 break;
        }
    } while (oled.nextPage());
}

void setup(void) {
  pinMode(LED, OUTPUT);
  pinMode(BUTTON, INPUT_PULLUP); //default pullup
  filter_for_graph = EEPROM.read(OPTIONS);  //EEPROM.read(address)
  draw_Red = EEPROM.read(OPTIONS+1);
  oled.init();
  oled.fill(0x00); //清除畫面
  draw_oled(3);  // draw 開機畫面
  delay(3000); 
  if (!sensor.begin())  { // init max30102 error 
    draw_oled(0);         
    while (1);
  }

  attachInterrupt(15, button, FALLING);  //一般中斷呼叫
  esp_sleep_enable_ext0_wakeup(GPIO_NUM_15, 0); //睡眠喚醒中斷呼叫
  sensor.setup();  // LOAD max30102 configuration
}

long lastBeat = 0;    //Time of the last beat 
long displaytime = 0; //Time of the last display update
bool led_on = false;


void loop()  {
    sensor.check(); //check Wrap condition #Samples
    long now = millis();   //start time of this cycle
    if (!sensor.available()) return;
    uint32_t irValue = sensor.getIR(); 
    uint32_t redValue = sensor.getRed();
    sensor.nextSample();
    if (irValue<5000) {
        checkbutton();
        draw_oled(sleep_counter<=50 ? 1 : 4); // finger not down message
        delay(200);
        ++sleep_counter;
        if (sleep_counter>100) { //
          go_sleep(); 
          sleep_counter = 0;
        }
    } else {
        sleep_counter = 0;
        int16_t IR_signal, Red_signal;
        bool beatRed, beatIR;
        if (!filter_for_graph) {//
            // IR_signal =  pulseIR.dc_filter(irValue) ;
            // Red_signal = pulseRed.dc_filter(redValue);
            Red_signal =  pulseIR.dc_filter(irValue) ;
            IR_signal = pulseRed.dc_filter(redValue);
            beatRed = pulseRed.isBeat(pulseRed.ma_filter(Red_signal));
            beatIR =  pulseIR.isBeat(pulseIR.ma_filter(IR_signal));        
        } else {
            // IR_signal =  pulseIR.ma_filter(pulseIR.dc_filter(irValue)) ;
            // Red_signal = pulseRed.ma_filter(pulseRed.dc_filter(redValue));
            Red_signal =  pulseIR.ma_filter(pulseIR.dc_filter(irValue));
            IR_signal = pulseRed.ma_filter(pulseRed.dc_filter(redValue));
            beatRed = pulseRed.isBeat(Red_signal);
            beatIR =  pulseIR.isBeat(IR_signal);
        }
        // invert waveform to get classical BP waveshape
        wave.record(draw_Red ? -Red_signal : -IR_signal ); 
        // check IR or Red for heartbeat     
        if (draw_Red ? beatRed : beatIR){
            long btpm = 60000/(now - lastBeat);
            if (btpm > 0 && btpm < 200) beatAvg = bpm.filter((int16_t)btpm);
            lastBeat = now; 
            digitalWrite(LED, HIGH); 
            led_on = true;
            // compute SpO2 ratio
            long numerator   = (pulseRed.avgAC() * pulseIR.avgDC())/256;
            long denominator = (pulseRed.avgDC() * pulseIR.avgAC())/256;
            int RX100 = (denominator>0) ? (numerator * 100)/denominator : 999;
            // using formula
            SPO2f = (10400 - RX100*17+50)/100;  
            // from table
            if ((RX100>=0) && (RX100<184))
              SPO2 = pgm_read_byte_near(&spo2_table[RX100]);
        }
        // update display every 50 ms if fingerdown
        if (now-displaytime>50) {
            displaytime = now;
            wave.scale();
            draw_oled(2);
            
        }
        Display_5();
    }
    // flash led for 25 ms
    if (led_on && (now - lastBeat)>25){
        digitalWrite(LED, LOW);
        led_on = false;
    }
}
