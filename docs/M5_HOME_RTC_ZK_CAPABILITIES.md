# M5 — Stable iPhone Home Screen, Bonjour addresses, and BM8563 RTC

Status: **draft software qualification**. The M5StickC Plus physical hardware has **not** been flashed or field-tested for this revision. Previously proven Mac HTTPS time-setting still works on its separate branch.

## 1. Stable bookmark on the iPhone

There are **two different hosts**, not one interchangeable server:

| Host | Proposed fixed local address | Notes |
| --- | --- | --- |
| Mac HTTPS live control | `https://<MAC_LOCAL_HOSTNAME>.local:8766/` | User's Mac running the HTTPS gateway; allows authenticated paired iPhone shortcuts |
| M5StickC Plus station web UI | `http://zkclock.local/` | M5 read-only dashboard; mDNS runs in station mode |
| M5 protected setup AP | `http://zkclock.local/` or fallback `http://192.168.4.1/` | Depends on Bonjour support of the M5 AP and iOS; IP fallback is reliable |

The URL continues to work **when DHCP changes the host's IP**, if the local Wi-Fi permits Bonjour/multicast discovery between phone and host. It is **not** a public internet URL and it doesn't work automatically when away from the network, when the host is offline or when MikroTik client isolation/VLAN policies block access.

A single address that transparently switches between the Mac and M5 would require a permanently running, trusted reverse proxy/local-DNS router. We have not built that and should not claim that the above two distinct hosts are one website. Keep the Mac Home Screen app as the primary full-control UI; use M5's separate address as an equipment-specific fallback.

### Mac: make the existing trusted HTTPS certificate match the Bonjour hostname

1. On the Mac with working `~/zkteco-clock/.venv`, switch to branch `feature/m5-home-rtc` and run `bash tools/prepare_home_domain.sh`.
2. The script reads the **existing** Mac `LocalHostName` and prints its full HTTPS URL. It does **not** modify Mac network settings or certificates in this inspection mode.
3. The prior certificate generated for an IP only **does not** cover the hostname. Once the old server is stopped, deliberately run `bash tools/prepare_home_domain.sh --rotate`. This backs up existing TLS materials in the ignored `.secrets/tls-backups/` folder, then generates a fresh temporary CA and server certificate with the Mac's `DNS:...local` Subject Alternative Name.
4. AirDrop **only** the new `.secrets/ZKTeco_Local_CA.cer` file to the iPhone; remove the previous temporary CA profile and trust the new one after confirming its provenance. Never transmit `.key` files. The new temporary root CA is valid for seven days, and the script deletes its signing private key after issuing the server certificate.
5. Run the HTTPS gateway in **read-only** mode with pairing enabled. Open the printed stable URL from iPhone Safari **only if HTTPS is trusted without certificate warnings**, complete one-time pairing again for the new hostname, then use Safari Share → **Add to Home Screen** → **Open as Web App**.
6. The Mac gateway now serves `/manifest.webmanifest` and `/apple-touch-icon.png`, plus Apple standalone metadata.

Example read-only command:

```bash
~/zkteco-clock/.venv/bin/python tools/mac_live_control.py \
  --bind 0.0.0.0 --port 8766 \
  --cert .secrets/mac.crt --key .secrets/mac.key \
  --enable-pairing --paired-only
```

Normal usage after pairing can omit `--enable-pairing`. Use `--enable-write --paired-only` only in short, authorized maintenance sessions. Stop with Ctrl+C afterwards. Root CA trust and pairing are distinct controls; neither guarantees the underlying campus Wi-Fi is isolated.

**If Bonjour fails on university Wi-Fi**, do not weaken TLS or expose port 8766 to the Internet. Prefer an IT-approved DHCP reservation/internal DNS name and a matching trusted certificate. `https://<current-IP>:8766/` remains a tested local fallback when the certificate covers that IP.

## 2. M5 RTC: use its clock as a local time source

The original M5StickC Plus has an onboard **BM8563 RTC**. It is a clock source, not an authoritative time service. A fresh device, lost RTC backup power, clock drift or an uncalibrated device may show the wrong time.

### Calibration

1. Power on the M5 and choose **A: SETUP**.
2. Join its WPA2-protected setup Wi-Fi.
3. Open `http://192.168.4.1/rtc` in iPhone Safari.
4. Verify the iPhone time is correct. Tap **ضبط ساعة M5 من الهاتف** to set **date and time together** (Baghdad civil time).
5. The M5 reads its RTC again and stores the observed calibration date/time in ESP32 Preferences; it does **not** change the ZKTeco terminal during calibration.

The M5 accepts the RTC as a time source only while the saved calibration appears valid and **no more than seven days old**. Date/time must be in 2000–2099. The seven-day window limits stale clocks but cannot guarantee RTC accuracy; compare against a reliable reference before actual production correction. This is a conservative software policy, not a hardware precision claim.

### Physical M5 shortcut

In **B: CONNECT** mode, the M5 local menu includes an additional **SYNC FROM M5 RTC** item alongside full fixed datetime presets. Short **A** cycles menu entries. Long **B** requests execution of the highlighted command; large shifts still need the extended hold. The path uses the same one-shot SET_TIME+fresh read verification as previous M4 physical-only code.

**Default read-only firmware never sends SET_TIME.** In the read-only build the selected shortcut will display `WRITE LAB DISABLED`. A separate `m5stickc-plus-write-lab` target compiles write-capable code but is **not** automatically flashed. Only promote that variant after physically confirming M5 Wi-Fi, local SDK framing, RTC battery retention, clock calibration, and user-controlled writes against the authorized real terminal.

No automatic RTC→ZKTeco synchronization at boot, every hour, or on network recovery. This avoids unobserved clock shifts to employee attendance.

## 3. ZKTeco iFace 950 expansion candidates

The terminal has a broader SDK surface, but actual availability varies by firmware and configuration. Reference capabilities include `get_attendance`, `get_users`, `read_sizes`, `get_firmware_version`, `get_serialnumber`, `live_capture`, `set_user` and biometric template methods. These are **possibilities, not tested on the operator's iFace 950**.

Suggested implementation stages:

- **A. Device health (safe read-only):** clock drift, reachability, SDK version and *counts only* of storage/user/attendance capacity. No biometric read.
- **B. Authorized attendance backup:** explicitly scoped, encrypted archive of attendance transactions, deduplicate and checkpoint records; no deletion/clear commands and no cloud upload by default. Attendance may include personally identifiable worker records: only with organization approval, role limits, audit logs and retention rules.
- **C. Authorized roster reconciliation:** display mismatches between a separately approved official roster and device users, with opt-in create/update person IDs/names through a reviewed write transaction. No admin rights by default.
- **D. Event monitoring:** supported low-load live punch events, if the device SDK/firmware supports them, with bounded buffering and no capture of biometric data.
- **E. Full biometric templates (fingerprint/face):** intentionally excluded from this project. Fingerprint/face templates are highly sensitive and protocol support is inconsistent. Use authorized vendor enrollment workflows instead.

**Never** enable mass deletion of logs, staff users, biometric templates, device resets or shutdowns through a quick button.

Reference documentation (actual support must be verified against live firmware read-only first):
- https://pyzk.readthedocs.io/en/stable/zk_base.html
- https://pyzk.readthedocs.io/en/latest/zk.html
- https://www.zkteco.com/en/faq
- https://docs.m5stack.com/en/core/StickC-Plus
- https://support.apple.com/en-eg/guide/iphone/iphea86e5236/ios

No actual attendance or biometric records were retrieved while building this feature.
