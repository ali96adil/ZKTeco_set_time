# M4 — corrected shortcuts and manual M5 boot selection

This update follows the user's corrections on 2026-10-29.

## Shortcuts: **one complete command**

There are only two shortcut kinds now:

| Kind | Exactly what pressing it does |
|---|---|
| `datetime` | Set the terminal to the saved **full local calendar date and clock time**, YYYY-MM-DDTHH:MM:SS. Both date and time change together. |
| `phone` | Set to the **phone's current Baghdad time** at the moment of tapping in the authorized Mac HTTPS web interface. |

There is **no date-only** or **time-only** preset. Shortcut buttons include a name and the complete datetime; the Mac interface saves them locally. A button triggers one SDK set operation followed by one independent read to verify, with no retry on an ambiguous result. Manual large shifts still require deliberate confirmation.

Note: some old M3 test catalogs may have unsupported types. If an existing file `.secrets/shortcuts.json` uses `"kind":"date"` or `"kind":"time"`, back it up and remove/replace those legacy entries with full `"kind":"datetime"` records before starting M4.

## M5 startup: operator chooses *immediately*

At every boot, **before attempting Wi-Fi**, the M5StickC Plus (original Plus, two primary buttons) displays:

```
ZKTeco Clock
CHOOSE START MODE
A: SETUP Wi-Fi AP
B: CONNECT to Wi-Fi
```

- **A**: broadcast its password-protected setup Wi-Fi and offer `http://192.168.4.1/setup` and `http://192.168.4.1/presets`.
- **B**: keep trying the saved Wi-Fi with reconnect attempts. If unavailable, remain trying it. There is **no 30-second automatic switch to AP**.
- In setup, long-press **B (2s)** to return to the boot-choice screen.
- In connected mode, long-press **A (3s)** to return to the boot-choice screen.

The AP's per-device WPA2 password is generated once and remembered by the phone, not refreshed on every boot. A private AP does not reach the ZKTeco terminal if there is no routed link.

## Using presets directly from the physical M5 buttons

1. First prepare the shortcuts: via `http://192.168.4.1/presets` while the iPhone is connected to M5's **protected setup AP**.
2. On M5 boot menu choose **B: CONNECT** and ensure the M5 can reach ZKTeco through Wi-Fi.
3. **Short A:** cycle through saved complete datetime commands (up to 8 locally on M5).
4. **Hold B around 2.2 seconds:** physically choose and request the selected command.
5. For an unusually large correction (over 24 hours), **keep holding B for ~4.2 seconds**; the shorter hold only shows a warning.
6. When clock-write firmware is explicitly enabled in a *qualified later build*, the operation sends **one SET_TIME** and makes **one new connection** to verify. The local display shows `CLOCK VERIFIED` or `UNVERIFIED`; do not repeat an ambiguous write without inspecting the terminal.

**Current/default M5 firmware remains READ ONLY:** physical shortcut selection, menus and preview/navigation can be tested, but a real time write displays `WRITE LAB DISABLED`. The source contains an opt-in `ZK_ENABLE_M5_TIME_WRITE=1` *lab build* for protocol/compiler verification. **Do not flash a write-enabled variant to the production attendance device until hardware and operator qualification are completed**. The ordinary `m5stickc-plus-readonly` build is the normal upload candidate; CI only compiles the separate `m5stickc-plus-write-lab` target without uploading it.

**Display limitation:** stock M5StickC Plus TFT text doesn't provide Arabic shaping; the preset **index and numeric timestamp** remain visible, while Arabic labels may not render properly on the native LCD. The iPhone web UI supports Arabic names.

## Transfer Mac shortcuts to the M5 without typing them twice

1. In the authenticated Mac HTTPS interface, save complete datetime commands.
2. Tap **نسخ أوامر التاريخ والوقت للـM5**. It copies a plain-text portable list of `name|YYYY-MM-DDTHH:MM:SS` lines. Phone sync is excluded: the physical M5 cannot infer the current phone time without a trusted phone connection.
3. Choose M5 **A: SETUP**, join the protected `ZK-Setup-XXXXXX` AP from Safari.
4. Open `http://192.168.4.1/presets`, paste the clipboard into **استيراد الأوامر من الماك**, and tap import.
5. Exit setup, choose **B: CONNECT**, then cycle the imported shortcuts using physical button A.

Up to 8 presets, at most 24 UTF-8 bytes per imported M5 label. Longer labels are rejected instead of silently truncated; the Mac copy button explains the limit. Export/import is intentionally manual across network boundaries, rather than exposing an unauthenticated control endpoint to the open university Wi-Fi.

## Test and change-control notes

- The previously field-verified **Mac HTTPS live control** supported +92s manual adjustment and −92s phone synchronization.
- M4 changes shortcut semantics and M5 boot UI; all new changes require independent host simulation and ESP32 compilation.
- Physical M5 Wi-Fi, buttons, NVS persistence and clock write still require testing on the actual hardware.
- No employee records or biometric data are read or modified by these features.
