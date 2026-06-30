#ifndef NETWORK_MANAGER_H
#define NETWORK_MANAGER_H

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <WiFiManager.h>
#include "config.h"

class NetworkManager {
public:
    NetworkManager();
    void begin();
    void sendData(const SensorData &data);
    bool isBootResetSent() const { return bootResetSent; }
    void clearQueue();

private:
    WiFiClientSecure espClient;
    PubSubClient mqttClient;
    QueueHandle_t dataQueue;
    volatile bool bootResetSent;
    char dynamic_mqtt_topic[64];
    char macStr[13];

    static void networkTask(void *pvParameters);
    void runTask();
};

extern NetworkManager NetworkMgr;

#endif // NETWORK_MANAGER_H
