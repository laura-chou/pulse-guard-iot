<?php
header("Access-Control-Allow-Origin: *");
header("Content-Type: application/json");

echo json_encode([
    "MQTT_HOST"     => getenv('MQTT_HOST'),
    "MQTT_PORT"     => getenv('MQTT_PORT'),
    "MQTT_TOPIC"    => getenv('MQTT_TOPIC'),
    "MQTT_USERNAME" => getenv('MQTT_USERNAME'),
    "MQTT_PASSWORD" => getenv('MQTT_PASSWORD')
]);
?>
