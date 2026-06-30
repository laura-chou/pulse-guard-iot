#ifndef SENSOR_PROCESSOR_H
#define SENSOR_PROCESSOR_H

#include <Arduino.h>
#include "max30102.h"
#include "pulse.h"
#include "config.h"

class SensorProcessor {
public:
    SensorProcessor();
    bool begin();
    bool update();
    bool wasBeatDetected();

    int getBeatAvg() const { return beatAvg; }
    int getSPO2() const { return SPO2; }
    DeviceStatus getStatus() const { return currentStatus; }
    bool isFingerDetected() const { return fingerDetected; }
    uint32_t getFingerOnStartTime() const { return fingerOnStartTime; }
    int16_t getIRSignal() const { return latestIRSignal; }

    void reset();
    void sensorOff();

private:
    MAX30102 sensor;
    Pulse pulseIR;
    Pulse pulseRed;
    MAFilter bpm;

    int beatAvg;
    int SPO2;
    DeviceStatus currentStatus;
    bool fingerDetected;
    uint32_t fingerOnStartTime;
    bool firstBeatAfterPlacement;
    long lastBeat;
    unsigned long lastPublishTime;
    int16_t latestIRSignal;
    bool _beatDetected;

    void processSamples();
    void handleFingerRemoved();
    void handleFingerPlaced();
    void calculateHealth(uint32_t irValue, uint32_t redValue);
};

extern SensorProcessor SensorProc;

#endif // SENSOR_PROCESSOR_H
