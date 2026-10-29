#pragma once
// Copy to include/config.h (ignored by Git). Never commit actual Wi-Fi credentials.
// M5StickC Plus connects only to 2.4 GHz networks.
// For OPEN Wi-Fi with a MikroTik Hotspot/captive portal, keep password empty.
// The ESP32 joins Wi-Fi without entering any captive portal username/password;
// access to ZKTeco 10.1.65.2:4370 must be verified separately.
#define ZK_WIFI_SSID "YOUR_OPEN_OR_PROTECTED_WIFI_SSID"
#define ZK_WIFI_PASSWORD ""

// For protected WPA/WPA2 networks, set ZK_WIFI_PASSWORD to the Wi-Fi password.
// Replace with the actual authorized target IP after checking the current network.
#define ZK_DEVICE_IP "192.0.2.10"
#define ZK_DEVICE_PORT 4370
