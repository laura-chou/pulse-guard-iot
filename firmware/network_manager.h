#ifndef NETWORK_MANAGER_H
#define NETWORK_MANAGER_H

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <WiFiManager.h>
#include "config.h"

/**
 * @class NetworkManager
 * @brief Manages WiFi connectivity and non-blocking MQTT communication using FreeRTOS tasks.
 */
class NetworkManager {
public:
    NetworkManager();

    /**
     * @brief Initializes WiFiManager and starts the MQTT background task on Core 0.
     */
    void begin();

    /**
     * @brief Sends sensor data to the MQTT task via a queue.
     */
    void sendData(const SensorData &data);

    /**
     * @brief Checks if the initial RESET MQTT packet has been sent after boot.
     */
    bool isBootResetSent() const { return bootResetSent; }

    /**
     * @brief Clears any pending data in the MQTT publish queue.
     */
    void clearQueue();

private:
    WiFiClientSecure espClient;
    PubSubClient mqttClient;
    QueueHandle_t dataQueue;
    volatile bool bootResetSent;
    char dynamic_mqtt_topic[64];
    char macStr[13];

    /**
     * @brief Static entry point for the FreeRTOS task.
     */
    static void networkTask(void *pvParameters);

    /**
     * @brief Main loop for the MQTT task.
     */
    void runTask();
};

extern NetworkManager NetworkMgr;

#endif // NETWORK_MANAGER_H
