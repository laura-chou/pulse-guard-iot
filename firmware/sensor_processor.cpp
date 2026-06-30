#include "sensor_processor.h"
#include "network_manager.h"

SensorProcessor::SensorProcessor() :
    beatAvg(0),
    SPO2(0),
    currentStatus(STATUS_NORMAL),
    fingerDetected(false),
    fingerOnStartTime(0),
    firstBeatAfterPlacement(true),
    lastBeat(0),
    lastPublishTime(0),
    latestIRSignal(0),
    _beatDetected(false) {}

bool SensorProcessor::wasBeatDetected() {
    bool temp = _beatDetected;
    _beatDetected = false;
    return temp;
}

bool SensorProcessor::begin() {
    if (!sensor.begin()) return false;
    sensor.setup(); // Default setup for SpO2 mode
    return true;
}

bool SensorProcessor::update() {
    sensor.check();
    if (!sensor.available()) return false;

    _beatDetected = false;
    processSamples();
    return true;
}

void SensorProcessor::processSamples() {
    uint32_t irValue = sensor.getIR();
    uint32_t redValue = sensor.getRed();
    sensor.nextSample();

    unsigned long now = millis();

    if (irValue < 5000) {
        // Finger removed if IR signal is too low
        handleFingerRemoved();
    } else {
        // Finger detected
        handleFingerPlaced();

        // Apply DC removal and Moving Average filters
        latestIRSignal = pulseIR.ma_filter(pulseIR.dc_filter(irValue));
        int16_t redSignal = pulseRed.ma_filter(pulseRed.dc_filter(redValue));

        // Detect heartbeat on IR channel
        bool beatIR = pulseIR.isBeat(latestIRSignal);
        if (beatIR) _beatDetected = true;

        if (beatIR) {
            if (firstBeatAfterPlacement) {
                // First beat is for timing reference only
                lastBeat = now;
                firstBeatAfterPlacement = false;
            } else {
                // Calculate Instantaneous BPM and apply filter
                long btpm = 60000 / (now - lastBeat);
                if (btpm > 0 && btpm < 200) {
                    beatAvg = bpm.filter((int16_t)btpm);
                }
                lastBeat = now;
            }

            // Perform health analysis on every beat
            calculateHealth(irValue, redValue);
        }
    }
}

void SensorProcessor::handleFingerRemoved() {
    fingerDetected = false;
    fingerOnStartTime = 0;
    beatAvg = 0;
    SPO2 = 0;
    currentStatus = STATUS_NORMAL;
    firstBeatAfterPlacement = true;
    latestIRSignal = 0;
}

void SensorProcessor::handleFingerPlaced() {
    if (!fingerDetected) {
        fingerDetected = true;
        fingerOnStartTime = millis();
    }
}

void SensorProcessor::calculateHealth(uint32_t irValue, uint32_t redValue) {
    unsigned long now = millis();

    // Get signal statistics for SpO2 calculation
    float rAC = pulseRed.avgAC();
    float rDC = pulseRed.avgDC();
    float iAC = pulseIR.avgAC();
    float iDC = pulseIR.avgDC();

    // R = (AC_red / DC_red) / (AC_ir / DC_ir)
    if (rDC > 0 && iDC > 0 && iAC > 0) {
        float rRatio = (iAC / iDC) / (rAC / rDC);
        // Empirically derived formula for SpO2
        float calculatedSpO2 = -45.060 * (rRatio * rRatio) + 30.354 * rRatio + 94.845;
        if (calculatedSpO2 > 100.0) calculatedSpO2 = 100.0;

        // Data is only valid after the 5s stabilization period
        if (now - fingerOnStartTime >= STABILIZATION_MS) {
            if (calculatedSpO2 >= 50.0) {
                SPO2 = (int)calculatedSpO2;
            } else {
                SPO2 = 0;
            }
        } else {
            // During stabilization, keep values at 0 (shown as "---" on UI)
            SPO2 = 0;
            beatAvg = 0;
        }
    }

    // Threshold logic for warning/danger levels
    if (now - fingerOnStartTime >= STABILIZATION_MS) {
        if (SPO2 > 0 && beatAvg > 0) {
            if (SPO2 < 90 || beatAvg < 50 || beatAvg > 120) {
                currentStatus = STATUS_DANGER;
            } else if (SPO2 < 95 || beatAvg < 60 || beatAvg > 100) {
                currentStatus = STATUS_WARNING;
            } else {
                currentStatus = STATUS_NORMAL;
            }

            // Publish data to MQTT every 1 second if stable
            if (now - lastPublishTime > 1000) {
                SensorData outData;
                outData.bpm = beatAvg;
                outData.spo2 = SPO2;
                outData.status = currentStatus;
                NetworkMgr.sendData(outData);
                lastPublishTime = now;
            }
        }
    }
}

void SensorProcessor::reset() {
    handleFingerRemoved();
    lastPublishTime = 0;
}

void SensorProcessor::sensorOff() {
    sensor.off();
}

SensorProcessor SensorProc;
