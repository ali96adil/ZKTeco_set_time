# M7 — Web navigation, visible shortcuts, network settings and LCD timeout

## What changed

The operator confirmed **`http://zkclock.local/` works** on a physical M5StickC Plus, but saved shortcuts were only visible on the physical display. The previous `/presets`, `/setup` and `/rtc` pages returned HTTP 403 while connected to normal Wi-Fi because they were restricted entirely to the protected setup access point.

M7 provides a consistent navigation bar, readable over both M5 networking modes:

| Page | URL | CONNECT (untrusted WLAN) | Protected SETUP AP |
| --- | --- | --- | --- |
| Home | `/` | Read real terminal clock and see saved shortcuts | Same read-only dashboard; terminal may be unreachable |
| Shortcuts | `/presets` | Show all saved commands and RTC sync entry | Show and edit 8 local full-datetime presets, import from Mac |
| Settings | `/setup` | Show Wi-Fi SSID, ZKTeco IP, AP SSID and screen timeout (no passwords) | Configure station Wi-Fi, ZKTeco IP, **custom setup-AP network name**, display timeout |
| RTC | `/rtc` | Show RTC time and calibration state | Calibrate the M5 BM8563 RTC from the phone |

A new **`GET /api/presets`** delivers a *read-only* JSON catalog used by the Home page. It exposes labels and timestamps but not passwords or user/attendance data. **There are no HTTP endpoints that execute a saved ZKTeco clock write.** Physical actions and the previously proven Mac HTTPS gateway are separate.

### Why editing is restricted

University Wi-Fi is open. M5's current station web server is **HTTP (not HTTPS)**, so exposing editable SSID/password/IP/preset/RTC operations on that network would allow unauthorized users or network interception. The CONNECT pages are intentionally view-only. To change protected settings, the operator physically selects the M5's WPA2 SETUP mode and connects the iPhone to its private Wi-Fi. The AP password remains stable (and not printed on the public station pages).

## Change the M5 setup network name

1. On the physical M5 in CONNECT, hold **A for around 3 seconds** to return to the boot menu.
2. At the boot menu press **A = SETUP**. Connect the iPhone to the M5's own `ZK-Setup-...` WPA2 network, using the QR or the password shown by the device.
3. In Safari open **`http://192.168.4.1/setup`**, or use the Settings link in the page navigation.
4. Change **اسم شبكة إعداد M5** to 4–24 characters, only ASCII letters/numbers, `-` and `_`. Example: `MyClock-Control`.
5. Save. The new SSID takes effect **the next time you leave and re-enter SETUP mode**, not during the current request, so the phone is not disconnected while saving.
6. Rejoin the renamed SSID once on the iPhone. The private WPA2 password remains unchanged, so there is no need to recreate credentials.

**Wi-Fi password preservation:** leaving the station password empty on the settings form retains the current saved password when the SSID is unchanged. To configure a *different* unprotected/open network, explicitly tick the Open network checkbox; otherwise provide its WPA password.

## Automatic display sleep

The screen timeout is configurable from the same protected `/setup` page:
- 15 seconds
- 30 seconds (default)
- 60 seconds
- 120 seconds
- 0 — never switch the backlight off

This is **display-backlight sleep only** using `M5.Axp.ScreenSwitch(false)` / `true`; ESP32 processing, local RTC, Wi-Fi attempts and HTTP server stay active. It is not ESP32 deep sleep, not a power-off command, and battery savings have not been measured.

Any physical A/B press **wakes the display without triggering a clock shortcut**. Release the button completely before navigating or requesting an operation. Web requests do not wake a sleeping display. Restarting the M5 preserves the chosen timeout in NVS.

## M5StickC Plus button guide

| Screen / state | A button | B button |
| --- | --- | --- |
| Boot menu | Short press: **SETUP** (broadcast protected setup Wi-Fi) | Short press: **CONNECT** (keep trying stored station Wi-Fi) |
| SETUP QR page | Short A: show enlarged WPA2 password | Hold B about 2 sec: back to boot menu |
| SETUP password page | Short A: show QR again | Hold B about 2 sec: boot menu |
| CONNECT, screen lit | Short A: next saved full-datetime preset or RTC sync option; long A ~3 sec: boot menu | Hold B ~2.2 sec: attempt selected command; if correction exceeds a day, continue holding ~4.2 sec |
| CONNECT, screen asleep | **First press only wakes**; release first | **First press only wakes**; release first |

There is no "B quick-click write". The displayed **`WRITE LAB DISABLED`** means you flashed the default **read-only** firmware. This is expected and safe during M5 qualification. The write-enabled lab variant must not be installed until a supervised test of the actual ZKTeco protocol and operator safety.

The M5 menu includes a permanent **SYNC FROM M5 RTC** option. You must calibrate RTC first while on the protected SETUP AP using `/rtc`. The date/time presets on M5 are stored in ESP32 NVS and appear in both the native LCD and web page.

## Deployment / upgrade

The source branch is `feature/m7-web-navigation-display-sleep`. With the previously installed PlatformIO environment and a recognized M5 USB serial port:

```bash
cd ~/zkteco-m5-lab/ZKTeco_set_time || exit 1
git fetch origin
git switch feature/m7-web-navigation-display-sleep
git pull --ff-only origin feature/m7-web-navigation-display-sleep
test -f include/config.h || exit 1

"$HOME/.venvs/zk-platformio/bin/pio" run \
  -e m5stickc-plus-readonly \
  -t upload \
  --upload-port /dev/cu.usbserial-5D5A093FF0
```

Flashing replaces the M5 application firmware. ESP32 Preferences usually persist without a flash-erase operation, but **backup names/presets manually** if important; do not use `erase` or `erase_flash`. No ZKTeco attendance time set operation is available in the default read-only build.

**Testing:** host-side UI/authorization contract tests and both ESP32 firmware compile variants run on GitHub Actions. Physical testing of navigation, SSID rename, sleep/wake and button behavior is still required after flashing.
