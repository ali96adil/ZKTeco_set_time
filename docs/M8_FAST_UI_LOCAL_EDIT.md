# M8 — Fast `zkclock.local` mobile interface and local editing

**State:** Development draft. Builds and offline tests should pass before physical M5 flashing. The prior M7 physical deployment is already known to work on `zkclock.local` in station mode. No live ZKTeco time write was executed during M8 development.

## Why M8

The operator reports:
- Opening pages in the M5 web server feels slow.
- Navigation is crowded and there are too many explanatory paragraphs.
- Full-date-time shortcuts need to be visible/actionable **on the main mobile screen**.
- Editing shortcuts, AP setup SSID and screen timeout should be possible **without changing the M5 to SETUP mode** every time.
- They want the same memorable `zkclock.local` address in station and private setup modes.
- The M5 is powered on only briefly for maintenance; they asked whether an existing Mac HTTPS certificate needs to be installed on it.

## Web UI

**`http://zkclock.local/`** is a compact single-page interface, with four instant **in-page** tabs: Home, Shortcuts, Settings and RTC. Switching tabs no longer loads a new HTML page; browser-side JS changes the visible panel. The page has no external CSS, fonts or images and no automatic slow SDK read.

- **Home:** one button to read ZKTeco's time, list of saved complete datetime shortcuts, permanent calibrated M5 RTC sync item, and **Prepare** button on every item.
- **Shortcuts:** add/delete/edit up to eight full-date-time commands, all stored on the M5.
- **Settings:** current Wi-Fi name, target ZK IP (read-only), editable private setup-AP SSID and LCD idle timeout.
- **RTC:** status, calibration result; existing calibration tools remain in the protected setup AP.
- API: `GET /api/m8` for one lightweight state snapshot, `POST /api/m8/save` for benign edits, `POST /api/m8/select` for selection only.
- Older `/presets`, `/setup` and `/rtc` direct URLs remain working.

Opening tabs is instant locally; **the actual speed of the initial request and the SDK read depends on Wi-Fi signal/Bonjour routing** and must be measured on the real device. A failed ZKTeco socket can still take its existing TCP timeout, but that is now initiated only by pressing Read.

## CONNECT mode edits, with physical authorization

**This is not passwordless remote administration of the open university WLAN.**

To avoid frequently changing to SETUP for non-secret edits, in CONNECT mode:
1. Hold **physical M5 buttons A and B simultaneously for ~2 seconds**.
2. The device grants a **90-second** edit window, displaying `WEB EDIT 90s`.
3. On the already-open mobile page tap **Save** (shortcuts, private setup network name or screen idle timeout), or **Prepare** beside a shortcut.
4. The window closes after one successful save/selection; hold A+B again for the next edit.

Button combos are consumed until **both buttons are released**, preventing the B-hold from accidentally triggering clock control. After the LCD sleeps, the first press/hold only wakes it and must be released before arming.

These operations still travel over **unencrypted HTTP** in CONNECT mode. The local physical approval limits unattended changes but **does not make HTTP safe against interception or an active attacker on the same open Wi-Fi**. Changing station Wi-Fi passwords and calibrating RTC from a phone remains limited to the physically protected WPA2 SETUP AP. Do not use the open campus network for confidential commands. For a truly secure single-tap remote clock-write interface, use HTTPS via a trusted control gateway (e.g. the previously verified Mac gateway), a trusted segregated Wi-Fi network, or add an authenticated/validated TLS service to the M5.

## Real clock writes

**The normal firmware is STILL `m5stickc-plus-readonly`.** It cannot modify the ZKTeco clock, either from web or buttons.

The mobile Home **Prepare** action selects the shortcut on the M5 physical display **only**, and requires physical unlocking as above. In a separately hardware-qualified write-enabled lab build, a deliberate long B press may execute the selected option. This is intentionally not an HTTP write endpoint. The user should understand that M8 'Prepare' is not an execution success message.

No attendance/user/biometric data or Wi-Fi passwords are returned by `/api/m8`.

## Local hostname and HTTPS

- `http://zkclock.local/` remains the advertised mDNS address while CONNECT is up. The M5 explicitly restarts mDNS when entering its private SETUP AP to try to register the **same** hostname there.
- mDNS on iPhone and the ESP32 AP is subject to Wi-Fi/mDNS implementation and cached records; **`http://192.168.4.1/` is the dependable fallback in SETUP**. It is not a second domain or separate web application.
- The previously generated temporary private CA/server certificate was for the **Mac HTTPS gateway**, not M5 HTTP. Its 7-day expiry and trust steps are separate from this firmware. You do **not** need to install it on the M5 for the current read-only web UI. Nor should you pretend M5 HTTP is encrypted by merely adding a bookmark or a private CA.
- Turning M5 on only during maintenance reduces total exposure time; it doesn't secure the period while it is connected to an open WLAN.

## Upload read-only version (after CI)

```bash
cd ~/zkteco-m5-lab/ZKTeco_set_time || exit 1
git fetch origin
git switch feature/m8-fast-home-local-edit
git pull --ff-only origin feature/m8-fast-home-local-edit
test -f include/config.h || exit 1
"$HOME/.venvs/zk-platformio/bin/pio" run \
  -e m5stickc-plus-readonly \
  -t upload \
  --upload-port /dev/cu.usbserial-5D5A093FF0
```

M5 flash replaces its running application. Espressif NVS preferences generally survive flashing without `erase_flash`, but **back up important presets** if possible; don't use `erase`.

## Physical test checklist

1. Boot `A = SETUP`, `B = CONNECT`; CONNECT Wi-Fi joins and `zkclock.local` opens.
2. Main page shows RTC sync tile and full-datetime presets; tabs instantly switch panels.
3. Attempt saving a preset in CONNECT without A+B; expect 403 and a clear instruction.
4. Hold A+B ~2 seconds, **release both**, save a harmless new preset; refresh and verify persistence.
5. Repeat arm, select it with Prepare; the M5 LCD should show the selection, no ZKTeco write.
6. Change setup-AP SSID and LCD sleep duration, verify NVS persistence after reboot.
7. From CONNECT return to boot, select SETUP, reconnect iPhone to private WPA2 SSID, try `http://zkclock.local/` then fall back to `http://192.168.4.1/`.
8. Confirm station Wi-Fi password cannot be entered or displayed on the open CONNECT page.
9. Check failure/timeouts of direct `Read` button separately from tab-navigation latency.
10. Never flash write-enabled firmware during this UI-only qualification.
