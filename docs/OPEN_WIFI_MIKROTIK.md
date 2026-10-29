# Open Wi-Fi and MikroTik Hotspot qualification

The existing user network is an **open (no WPA/WPA2 password) 2.4-GHz Wi-Fi with MikroTik Hotspot/captive portal**. Do not confuse the wireless passphrase with the independent Hotspot login.

## Configure M5StickC Plus

`include/config.h` (local only, ignored by Git):

```cpp
#define ZK_WIFI_SSID "ACTUAL_WIFI_NAME"
#define ZK_WIFI_PASSWORD ""
#define ZK_DEVICE_IP "10.1.65.2"
#define ZK_DEVICE_PORT 4370
```

The firmware uses `WiFi.begin(ssid)` and `WiFi.setMinSecurity(WIFI_AUTH_OPEN)` when the password is empty. This obtains Wi-Fi association / DHCP **only**, and does not perform a captive-portal login.

After USB upload, check serial monitor (115200 baud) for:
- SSID;
- M5 local IPv4;
- router gateway;
- **M5 STA MAC** (for the network administrator only).

M5 screen should show an IP after association. If no IP, check signal, SSID, 2.4-GHz and client limits. **Wi-Fi connected does not prove reachability to the attendance device.**

## Determine if the Hotspot blocks access

1. Press M5 button A (firmware is READ ONLY) or press **Read Device** from mobile page.
2. If the ZKTeco clock appears, TCP/4370 is permitted from the M5 and a Hotspot login is not required for this route.
3. If device read fails, ask the authorized MikroTik administrator to check routing, Hotspot policy, VLAN isolation/firewall, and the M5 assigned IP. Do not assume the failure is from Wi-Fi association.
4. If office network policy requires the device to bypass Hotspot login, an authorized MikroTik administrator may register its Wi-Fi station MAC under **IP > Hotspot > IP Bindings** with type **bypassed**. Such a rule is an *access policy exception*, **not a security authentication mechanism**. Do not create it without IT approval. It alone may not permit cross-subnet traffic: firewall/routing permissions still matter.
5. Hotspot isolation may also prevent the *phone* from reaching the M5's `http://<M5-IP>` page. Phone-to-M5 and M5-to-ZKTeco are two distinct paths. If the phone cannot access it, test first from a permitted laptop and review client isolation with IT; do not disable Hotspot protections for all users.

## Open network security warning

An open WLAN is not encrypted at the Wi-Fi link layer. M2 exposes only a read-only, rate-limited HTTP endpoint for temporary diagnostics; **never use an unauthenticated write-enabled dashboard on this WLAN**. The next phase must use an isolated secure administration network or a password-protected M5 SoftAP plus authorized physical confirmation, and restrict access to its management interface. A secure M5 AP still does not encrypt ZKTeco's older TCP/4370 link to the terminal; use network isolation.

On public/open networks, disconnect the M5 after the read-only test; avoid leaving a permanent unauthenticated web server running.

## Router background

MikroTik's official Hotspot documentation describes IP Binding and `type=bypassed`:
https://help.mikrotik.com/docs/spaces/ROS/pages/56459266/HotSpot%2B-%2BCaptive%2Bportal

Arduino ESP32 Wi-Fi connection details:
https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html
