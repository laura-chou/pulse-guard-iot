#ifndef SENSOR_PROCESSOR_H
#define SENSOR_PROCESSOR_H

#include <Arduino.h>
#include "max30102.h"
#include "pulse.h"
#include "config.h"

/**
 * @class SensorProcessor
 * @brief Handles MAX30102 sensor interaction, signal filtering, and health calculations.
 */
class SensorProcessor {
public:
    SensorProcessor();

    /**
     * @brief Initializes the sensor and internal filters.
     * @return true if sensor is found and initialized.
     */
    bool begin();

    /**
     * @brief Checks sensor for new samples and processes them.
     * @return true if new samples were processed.
     */
    bool update();

    /**
     * @brief Checks if a heartbeat was detected during the last update.
     * @return true if a beat was detected.
     */
    bool wasBeatDetected();

    // Getters for current measurement values
    int getBeatAvg() const { return beatAvg; }
    int getSPO2() const { return SPO2; }
    DeviceStatus getStatus() const { return currentStatus; }
    bool isFingerDetected() const { return fingerDetected; }
    uint32_t getFingerOnStartTime() const { return fingerOnStartTime; }
    int16_t getIRSignal() const { return latestIRSignal; }

    /**
     * @brief Resets the processor state (e.g., after finger removal or system reset).
     */
    void reset();

    /**
     * @brief Powers down the sensor for deep sleep.
     */
    void sensorOff();

private:
    MAX30102 sensor;
    Pulse pulseIR;
    Pulse pulseRed;
    MAFilter bpm; // Moving average filter for BPM

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

// Singleton instance for use across modules
extern SensorProcessor SensorProc;

#endif // SENSOR_PROCESSOR_H
