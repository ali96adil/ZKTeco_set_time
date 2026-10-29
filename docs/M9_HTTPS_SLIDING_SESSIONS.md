# M9 — HTTPS on M5, renewable iPhone login and independent clock controls

**Implementation branch:** `feature/m9-https-persistent-session`. This is a development build, not yet field-qualified. No ZKTeco clock write has been sent during this implementation.

## User experience

- **M5 itself hosts HTTPS** at `https://zkclock.local/`. It does not require the Mac after installation.
- Choose the permanent username and password on the M5's **private WPA2 setup AP** once. The password is never written in source code or to GitHub; only a salted, slow password verifier is persisted in ESP32 NVS.
- Safari saves a **Secure, HttpOnly, SameSite=Strict** session token. Cookie validity is **365 days, renewed on every successful authenticated request**, so it can persist for years with ongoing use; there is no arbitrary 90-day absolute expiration. A user who doesn't visit for more than a year may log in again with AutoFill.
- Log into up to four browser sessions. The HTTPS Home page has **خروج من كل الأجهزة** to revoke all sessions.
- Mobile shortcut buttons send the requested date+time command directly to M5 over TLS, and the M5 sets the terminal once and verifies with a fresh read in its **explicit write-lab firmware**. Selecting and executing from physical M5 buttons is independent.
- **For >24h corrections** the phone gets an additional confirmation and must deliberately repeat with `confirm=large`. If verification fails, check the terminal instead of retrying blindly.
- On the default safe `m5stickc-plus-readonly` firmware, the HTTPS command returns a clear 'write not available' error and **does not send SET_TIME**. This lets TLS, login, sessions and RTC be tested without touching production attendance time.
- Presets, AP network name, LCD timeout, and phone-to-M5 RTC calibration are available over authenticated HTTPS. In station mode, the old unencrypted HTTP port is shut down.

## Important: Mac's earlier HTTPS cert is **not** used on M5

The M5 gets its own locally generated CA and private leaf cert. The private RSA key is **compiled into a per-device local firmware** and must be protected. Firmware extraction by a physical attacker is not prevented by this design (ESP32 flash encryption/secure boot would be separate hardware hardening).

### First installation on the Mac

```bash
cd ~/zkteco-m5-lab/ZKTeco_set_time || exit 1
git fetch origin
git switch feature/m9-https-persistent-session
git pull --ff-only origin feature/m9-https-persistent-session
test -f include/config.h || { echo "CONFIG MISSING"; exit 1; }

# Creates private files under .secrets/ and an ignored, local TLS header.
# NEVER put the generated M5 private key in a GitHub commit or a chat message.
bash tools/create_m5_tls.sh

# Upload READ ONLY for TLS/security qualification.
"$HOME/.venvs/zk-platformio/bin/pio" run -e m5stickc-plus-readonly \
    -t upload --upload-port /dev/cu.usbserial-5D5A093FF0
```

M9 uses the 4 MiB M5StickC Plus `huge_app.csv` partition layout (3 MiB single application, **no OTA slot**) because TLS exceeds the old 1.25 MiB slot. Changing the partition table may affect saved data; **before flashing, record/back up saved presets, Wi-Fi SSID, setup password, and RTC calibration**. Do not erase flash; NVS is expected at the standard address but must be checked on the physical M5.

The script refuses to regenerate/overwrite existing certificate materials without deliberate backup/revocation. Keep `.secrets/m5-ca.key` and `include/m5_tls_local.h` on your Mac only. Do not upload or share them.

### Trust on iPhone (once)

1. Mac AirDrop **`.secrets/m5-ca.cer` ONLY** to the iPhone; accept the profile and enable full trust under iPhone Settings → General → About → Certificate Trust Settings. Verify its origin. Never AirDrop .key or private firmware source.
2. On M5 boot choose **A — SETUP**, join its WPA2 private Wi-Fi using QR/password from its screen. Open **`http://192.168.4.1/auth/setup`** and choose a fixed username (default `operator`) and a good password of at least 12 characters. This also revokes previously paired web sessions.
3. Leave SETUP, choose **B — CONNECT**, wait until M5 joins the Wi-Fi and open **`https://zkclock.local/`** in Safari.
4. **Never bypass iPhone TLS warnings**. If the trusted hostname/certificate fails, stop and repair trust rather than using HTTP. Log in once using your fixed credentials, with iPhone AutoFill.
5. Safari Share → Add to Home Screen. Later, open from this icon while M5 is on and network-reachable. The 365-day cookie renews on each authenticated visit.
6. To revoke every phone, use the logged-in HTTPS **خروج من كل الأجهزة** action, or return to the protected SETUP AP and reset the username/password at `/auth/setup`.

## Network modes

- **CONNECT:** `https://zkclock.local/` on port 443; **unencrypted HTTP port 80 is intentionally shut down** on the station Wi-Fi.
- **SETUP:** the private WPA2 network still offers `http://zkclock.local/` when Bonjour works, or reliable `http://192.168.4.1/`. Credential enrollment occurs only on this physically enabled AP. It is an offline configuration network, not a ZKTeco clock-write HTTP endpoint.
- mDNS `.local` still requires that the iPhone and M5 can reach each other over the same allowed Wi-Fi segment. MikroTik AP/client isolation can prevent discovery/connection.
- Browser cookies are scoped to the HTTPS host. Avoid using a different IP URL for daily control, as it won't match the certificate and won't share cookies.

## Security and limitations

1. Authenticated HTTPS is required in station mode, including for saved commands, RTC sync and editing; browser requests require strict same-origin and a CSRF header for mutations.
2. Sessions stored on M5 contain **SHA-256 hashes of 256-bit random tokens**, not plaintext tokens. Passwords use a random salt and repeated SHA-256 hashing; verify 12-character minimum.
3. Only up to four active remembered browsers. Each login creates a fresh cookie and shifts out the oldest when full.
4. HTTPS and passwords protect data on Wi-Fi, but are not a substitute for network access control, flash encryption, or firmware signature validation. The SETUP AP password remains stored in device NVS.
5. Certificate validity is one year; renewing the certificate requires a deliberate local regeneration/build/flash and possibly a new iPhone trust profile. The phone login session itself can remain active separately if the device NVS is preserved.
6. RTC freshness remains based on the previously configured seven-day calibration window; calibrate from a correct phone clock.
7. **Do not install `m5stickc-plus-secure-write-lab` on a production attendance terminal until the device-specific SET_TIME packet and timing verification have been qualified physically.** GitHub CI compiles it only. Default firmware can show the complete workflow safely.
8. No employee, attendance or biometric records are collected by this feature.

## Qualification stages

A. Offline tests: TLS certificate SAN/trust, app compile for both variants, session/preset validation.

B. On-device, without the terminal: run HTTPS login from iPhone, save and reopen PWA session, power-cycle the M5, edit preset, revoke all phones, test failed password lockout, RTC calibration.

C. On-device in read-only mode with terminal: read ZKTeco time, inspect/preview shortcut but no write.

D. Only after authorized maintenance and a dedicated protocol qualification: test a deliberately small known clock correction using the independent one-command/one-verification write lab, then consider promotion of a write-enabled build. No automatic clock changes on boot or Wi-Fi reconnect.

The user requested **both independent control paths**; the default prototype deliberately separates secure user experience from unqualified physical write activation.
