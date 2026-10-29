# M3 — Network modes, phone pairing and clock shortcuts

M3 is a **test branch**, not yet validated on the physical M5StickC Plus. It contains two independently deployable parts:

1. **M5 read-only firmware:** Wi-Fi station mode and a protected setup access point for offline configuration.
2. **Mac HTTPS gateway:** persistent trusted-phone login and one-tap saved time shortcuts with a single fresh verification.

The M5 itself is still READ ONLY in this branch. No TCP time-write command has been added to its firmware. A successful Mac test is not proof of M5 functionality.

## M5 dual Wi-Fi modes (original M5StickC Plus)

### Station / connect to existing Wi-Fi

- Connect with the stored SSID and WPA password. An empty password means an **open Wi-Fi network**, e.g. the university MikroTik SSID.
- Store network information and terminal IP in ESP32 Preferences (NVS). Settings survive reboot.
- The station may join the hotspot SSID, but MikroTik login/routing is a separate constraint; an open association does not guarantee TCP/4370 access.

### Setup AP / emit own Wi-Fi

- If station Wi-Fi is unavailable for 30 seconds, the M5 automatically starts its **WPA2-protected setup AP**.
- Hold **Button B for about 1.8 seconds** to turn the setup AP on/off intentionally.
- The physical M5 screen shows `ZK-Setup-XXXXXX` and an individually generated 14-character WPA2 password. The password changes when the AP is started again, and is not posted on the university network.
- Join the M5 AP from the phone and open `http://192.168.4.1/setup`. This is an AP-only configuration page, not a terminal clock-write endpoint.
- Set SSID, optional Wi-Fi password and target ZKTeco IP; save. Return to station Wi-Fi when available.
- **If the M5 is not connected to a network that routes to the ZKTeco terminal, the AP only permits configuration. It cannot remotely set an unreachable terminal.** The ESP32 is not magically bridged into the ZKTeco LAN.

There is deliberately **no open, password-free M5 setup AP**.

## Mac gateway: paired Safari without repeated passwords

The university network is unencrypted Wi-Fi, so HTTPS trust is mandatory. Continue using the previously generated short-lived local CA and IP-SAN server certificate. A fresh terminal password is still an emergency fallback, but pairing makes everyday Safari use password-free.

From the project directory, with the trusted TLS certificates already created:

```bash
git fetch origin
git switch feature/m3-network-presets
git pull --ff-only origin feature/m3-network-presets

~/zkteco-clock/.venv/bin/python tools/mac_live_control.py \
  --bind 0.0.0.0 --port 8766 \
  --cert .secrets/mac.crt --key .secrets/mac.key \
  --enable-pairing
```

The Mac prints a **one-time eight-digit pairing code**, valid for **five minutes** and **five unsuccessful attempts**. On the iPhone, open the trusted `https://MAC_IP:8766/` address, enter the code once and pair. The gateway sets a `Secure; HttpOnly; SameSite=Strict` cookie, backed by a **SHA-256 hashed token** in local `.secrets/paired_phones.json`.

Restarting the gateway **without `--enable-pairing`** should recognize the same Safari browser for up to 30 days, as long as the cookie and the local token store remain. Clearing Safari site data/private browsing or changing phones requires pairing again.

Pair only a personally controlled phone. To revoke all paired phones, **stop the server first**, then delete `.secrets/paired_phones.json` from the Mac and restart. This invalidates all remembered sessions. Only up to five paired phones can be stored.

**Never trust unknown TLS certificates or bypass certificate warnings on the open Wi-Fi.** The server always requires HTTPS. Secure cookie pairing is not a substitute for the TLS trust chain.

## Save and use shortcuts

The authenticated HTTPS page includes shortcuts:
- **Phone sync:** set the device to the phone's Baghdad time at the moment you tap.
- **Time only:** set a chosen HH:MM:SS while retaining the device date.
- **Date only:** set a chosen YYYY-MM-DD while retaining the device HH:MM:SS.
- **Full date+time:** store exact civil YYYY-MM-DDTHH:MM:SS.

Add up to 12 shortcuts, name them and delete unused ones. Data is saved locally in `.secrets/shortcuts.json`, not GitHub or the ZKTeco device.

For the approved clock maintenance session, stop the server and restart with both flags:

```bash
~/zkteco-clock/.venv/bin/python tools/mac_live_control.py \
  --bind 0.0.0.0 --port 8766 \
  --cert .secrets/mac.crt --key .secrets/mac.key \
  --enable-write
```

Because Safari is already paired, it should reopen without asking for a new password.

**One tap:** tapping a shortcut sends one time-write request, then makes **one new connection to verify** the result. The button is locked during execution, and the server prevents consecutive quick actions within eight seconds. There is no automatic retry if the command result is ambiguous. `UNVERIFIED` requires inspecting the terminal first.

**Large shifts over 24 hours intentionally require the existing prepare/confirm workflow** rather than a one-tap shortcut, to avoid accidental corruption of attendance chronology. Shortcuts must not execute automatically on page load or reboot.

The original manual prepare/confirm path remains available for arbitrary forward or backward adjustments.

## Simplified routine

1. Turn on the Mac gateway in read-only mode during normal work.
2. Use the remembered iPhone to open the trusted HTTPS address.
3. To adjust during an approved maintenance period, restart with `--enable-write`.
4. Tap a saved clock shortcut; check the short `VERIFIED` status.
5. Stop the gateway with Ctrl+C when the maintenance session ends.

Do not leave real time-setting enabled on the university's open Wi-Fi. No user accounts, face/fingerprint templates, employee data or attendance logs are accessed by this code. Backward adjustments can still cause overlapping future punch timestamps.

## Qualification

- Code is stored under `feature/m3-network-presets`, with a draft PR.
- GitHub Actions runs host-only shortcut/pairing/one-shot tests and builds the M5 firmware.
- The M5 AP, physical Button B and MikroTik routing have **not been hardware-tested**.
- Mac live gateway before M3 was field-verified for a +92-second manual adjustment and a −92-second phone sync on 2026-10-29. New M3 shortcuts/pairing must be qualified separately.
