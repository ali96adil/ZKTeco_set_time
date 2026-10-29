# M6 — Big M5StickC Plus LCD, iPhone Wi-Fi QR

This changes **only the screen UI** on the original M5StickC Plus (240 × 135 LCD) and adds a QR library to the read-only firmware. The existing password in ESP32 Preferences **is not reset**, so paired iPhones do not lose the Wi-Fi password they previously saved.

## Why

The first live USB flash was successful, but the operator reported that setup text on the tiny TFT display was illegible and the 14-character WPA2 password was cumbersome to enter manually.

## New display

On boot, the M5 has two large, high-contrast choices:
- **A — SETUP WIFI:** Broadcast the private WPA2 setup network.
- **B — CONNECT WIFI:** Keep trying the configured 2.4-GHz network; no automatic change of mode after 30 seconds.

In SETUP mode there are now two screen pages; **tap button A** to toggle between them:

1. **SCAN QR (default):** A large version-4 QR code with WPA2 setup SSID and password, surrounded by a four-module white border. Open the iPhone Camera and scan it to join `ZK-Setup-...` rather than typing the password. The QR contains *only* protected setup Wi-Fi credentials, not ZKTeco device commands or data.
2. **PASSWORD:** Large network name and the existing WPA2 password displayed in two visually separated halves. Type the two halves **without a space** if the QR cannot be scanned.

Hold B about 2 seconds to return to the main boot menu.

Once connected to the M5 setup AP, open `http://192.168.4.1/setup`, `/presets` or `/rtc`. A working internet connection is not necessary for setup.

## Safety

- Read-only build `m5stickc-plus-readonly` continues to have all real terminal clock-write paths disabled.
- A separate `m5stickc-plus-write-lab` build may be compiled in CI, but it must not be flashed as part of initial LCD testing.
- The password is deliberately not hard-coded or printed over USB serial; the physical QR displays it only to those near the M5.
- If the iPhone joins a different Wi-Fi when the M5 network has no internet, disable auto-join of the other network temporarily and remain connected to the M5.
- Small 123 px QR codes can be difficult to scan depending on camera focus and reflections; use the password page as a fallback. Do not weaken WPA2 encryption to solve a QR problem.

## Testing

GitHub CI compiles both firmware variants and runs offline QR UI regression checks. The operator must still confirm that QR scan works on the physical 240 × 135 screen after flashing.
