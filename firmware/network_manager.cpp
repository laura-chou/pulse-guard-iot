#include "network_manager.h"
#include "display_manager.h"

/**
 * @brief Callback triggered when WiFiManager enters Config Portal mode.
 */
void configModeCallback(WiFiManager *myWiFiManager) {
    DisplayMgr.updateScreen(5, 0, 0, STATUS_NORMAL, 0, 0);
}

NetworkManager::NetworkManager() :
    mqttClient(espClient),
    bootResetSent(false) {
    memset(dynamic_mqtt_topic, 0, sizeof(dynamic_mqtt_topic));
    memset(macStr, 0, sizeof(macStr));
}

void NetworkManager::begin() {
    // 1. WiFi Setup using WiFiManager
    WiFiManager wm;
    wm.setConnectTimeout(10);
    wm.setConfigPortalTimeout(180);
    wm.setAPCallback(configModeCallback);
    if (!wm.autoConnect(AP_NAME)) {
        ESP.restart(); // Restart if AP config times out
    }

    // 2. Generate unique Device ID from MAC Address
    uint64_t chipMac = ESP.getEfuseMac();
    snprintf(macStr, sizeof(macStr), "%012llX", chipMac);

    // Topic: pulseguard/<env>/<device_id>/data
    snprintf(dynamic_mqtt_topic, sizeof(dynamic_mqtt_topic), "pulseguard/%s/%s/data", ENV_PROD, macStr);

    // 3. Start the MQTT Background Task on Core 0
    dataQueue = xQueueCreate(5, sizeof(SensorData));
    if (dataQueue != NULL) {
        xTaskCreatePinnedToCore(
            networkTask, "NetworkTask", 8192, this, 1, NULL, 0
        );
    }
}

void NetworkManager::sendData(const SensorData &data) {
    if (dataQueue != NULL) {
        xQueueSend(dataQueue, &data, 0);
    }
}

void NetworkManager::clearQueue() {
    if (dataQueue != NULL) {
        xQueueReset(dataQueue);
    }
}

void NetworkManager::networkTask(void *pvParameters) {
    NetworkManager *instance = (NetworkManager *)pvParameters;
    instance->runTask();
}

void NetworkManager::runTask() {
    espClient.setInsecure(); // Use TLS without certificate verification for simplicity
    mqttClient.setServer(MQTT_SERVER, MQTT_PORT);

    SensorData dataToPublish;
    for (;;) {
        // --- WiFi Monitoring ---
        if (WiFi.status() != WL_CONNECTED) {
            WiFi.disconnect();
            WiFi.reconnect();
            while (WiFi.status() != WL_CONNECTED) {
                vTaskDelay(500 / portTICK_PERIOD_MS);
            }
        }

        // --- MQTT Connection Management ---
        if (WiFi.status() == WL_CONNECTED && !mqttClient.connected()) {
            mqttClient.connect(macStr, MQTT_USER, MQTT_PASS);
            vTaskDelay(500 / portTICK_PERIOD_MS);
        }

        mqttClient.loop();

        if (mqttClient.connected()) {
            // --- Send Boot Reset Message once ---
            if (!bootResetSent) {
                const char* initResetPayload = "{\"device_status\":\"RESET\"}";
                if (mqttClient.publish(dynamic_mqtt_topic, initResetPayload)) {
                    bootResetSent = true;
                }
            }
            // --- Process Data Queue ---
            else {
                if (xQueueReceive(dataQueue, &dataToPublish, 0) == pdPASS) {
                    char jsonPayload[128];
                    const char* sStr = "NORMAL";

                    if (dataToPublish.status == STATUS_WARNING) { sStr = "WARNING"; }
                    else if (dataToPublish.status == STATUS_DANGER) { sStr = "DANGER"; }
                    else if (dataToPublish.status == STATUS_RESET) { sStr = "RESET"; }
                    else if (dataToPublish.status == STATUS_COMPLETED) { sStr = "COMPLETED"; }

                    if (dataToPublish.status == STATUS_COMPLETED) {
                        snprintf(jsonPayload, sizeof(jsonPayload),
                                 "{\"device_status\":\"COMPLETED\",\"duration_sec\":%lu}",
                                 (unsigned long)dataToPublish.duration_sec);
                    } else if (dataToPublish.status == STATUS_RESET) {
                        snprintf(jsonPayload, sizeof(jsonPayload),
                                 "{\"device_status\":\"RESET\"}");
                    } else {
                        snprintf(jsonPayload, sizeof(jsonPayload),
                                 "{\"bpm\":%d,\"spo2\":%d,\"device_status\":\"%s\"}",
                                 dataToPublish.bpm, dataToPublish.spo2, sStr);
                    }
                    mqttClient.publish(dynamic_mqtt_topic, jsonPayload);
                }
            }
        }
        vTaskDelay(10 / portTICK_PERIOD_MS); // Yield to other tasks
    }
}

NetworkManager NetworkMgr;
