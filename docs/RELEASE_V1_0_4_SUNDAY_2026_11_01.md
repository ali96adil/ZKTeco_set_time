# ZK Clock v1.0.4 — Sunday field-release candidate

**Prepared Saturday, 2026-10-31. Scheduled onsite check Sunday, 2026-11-01.**

> Status: **software candidate / physically incomplete**. Do not represent it as a field-certified production release until the real ZKTeco attendance clock has been read and the authorized correction independently verified from this exact M5StickC Plus.

## Release baseline, no firmware changes

- Source baseline: main commit `24e5b68943a2761df0e0259f527f30c06587e63c` (M13 battery + mDNS retry).
- The last change from green CI commit `4e99201ae2d4b6b6e02be746eb536b051db7eca9` to the baseline affected **only the test** `tests/test_m13_battery_discovery.py`, not the firmware.
- The workflow for `4e99201` passed **firmware build and static tests**. The later `24e5b689` workflow passed static tests but its firmware job stopped when PlatformIO returned a remote **download limit exceeded** error, not a compiler diagnostic.
- This release document does **not change firmware source, partitioning, TLS assets, Wi-Fi credentials, NVS or API semantics**.
- `m5stickc-plus-production` enables *real ZKTeco SET_TIME*. Never mistake it for a read-only build.
- The existing trusted device key (`include/m5_tls_local.h`), local CA, `include/config.h` and ESP32 NVS must **not** be regenerated, erased, shared, or committed.
- Local install must use the owner's Mac build; the CI-generated disposable certificate must **never** be flashed to the real M5.

## Verified from the operator's own tests

- Battery percentage appears on the M5 (voltage-derived **estimate**, not calibrated state of charge).
- M5 internal RTC works according to operator report.
- Restart/power-cycle works according to operator report.
- `SETUP` management has previously worked on `https://192.168.4.1/` when iPhone is joined to the M5's private setup Wi-Fi.
- `CONNECT` hostname `https://zkclock.local/` previously worked on the shared Wi-Fi.
- GitHub CI performed non-hardware tests and compiled the same firmware source.

**NOT physically verified for this exact M5:** TCP connectivity from its Wi-Fi to the ZKTeco terminal, GET_TIME SDK handshake, a real SET_TIME, new independent readback, attendance log invariants after the change.

## Operator Sunday plan: no Mac required for primary workflow

1. Confirm M5 has enough charge and that the date/time on iPhone in Asia/Baghdad are correct. Keep a USB power source handy.
2. Start M5; press **B once on the startup chooser** to enter CONNECT. Do not keep holding it into the operating screen. No automatic write is executed on startup.
3. iPhone connects to the SAME reachable authorized 2.4 GHz LAN; open **https://zkclock.local/**. Make sure this is the protected HTTPS origin and the expected account; do not bypass TLS warnings.
4. Review CONNECT Settings: SSID and ZKTeco target IP. Previously used terminal endpoint was **10.1.65.2:4370**, subject to the onsite network actually still using it.
5. Tap **قراءة** before ANY write. This must show the actual terminal's current date/time, matching the terminal display while the seconds advance. If reading fails, STOP: do not press an Execute shortcut. See the troubleshooting section below.
6. Check RTC tab. If calibration is missing/expired, **مزامنة ساعة M5 من الآيفون** updates ONLY the M5 RTC; it does **not** change ZKTeco.
7. Check saved commands: at most eight complete, static date-time shortcuts. A dated shortcut may now be stale; do not execute it as though it means 'now'. The dedicated `مزامنة من ساعة M5` item uses the fresh M5 RTC, not the stored fixed timestamp.
8. Before any live change: obtain permission, ensure there is no active staff punch-in/out window, confirm an up-to-date attendance backup and check the current terminal time on its physical screen. If these are missing, end with read-only checks.
9. When explicitly authorized and the terminal's time really needs correction, use the dedicated **مزامنة من ساعة M5** item (or a carefully verified stored timestamp): on iPhone, **one tap** on Execute; on the M5, A cycles and holding B about **700 ms** executes the highlighted item. There is no extra confirmation even for large time jumps: inspect the selection carefully before initiating it.
10. A network acknowledgement is not the final check. Wait for **تم تعديل ساعة البصمة والتحقق منها / CLOCK VERIFIED**; independently read again and inspect the actual terminal display and normal attendance operation. If status is **UNVERIFIED**, STOP; do not tap again blindly. The firmware intentionally never retries uncertain SET_TIME writes.
11. Confirm attendance log counts did not decrease and routine staff registrations still work. Do not modify, delete, reset or export biometric/staff records using this project.
12. Record: date, terminal time before/after, M5 read success, verified result, connection status, and attendance-record invariant. Do not include staff personal data or passwords.

## Two connection modes

| Mode | Phone network | Confirmed URL | Purpose |
|---|---|---|---|
| SETUP (startup A) | M5 private protected AP | `https://192.168.4.1/` | Configure Wi-Fi/target, setup-only shortcuts, login, RTC |
| CONNECT (startup B) | Same reachable LAN as M5 | `https://zkclock.local/` | Authenticated clock read, RTC, presets, controlled time adjustment |

The campus-station IP shown on the LCD is useful for troubleshooting but **is not automatically covered by the device's TLS certificate**. Do not bypass certificate errors to reach it; use the confirmed hostname. SETUP's IP is covered by the existing local leaf certificate.

## If CONNECT or ZKTeco read fails

- Site does not open: confirm that both iPhone and M5 are on the authorized local LAN, the M5 screen says Wi-Fi connected, and Bonjour/mDNS is not blocked. Try re-opening `https://zkclock.local/`. Do not regenerate the CA as a DNS workaround.
- Site opens but **قراءة** fails: this is **not** proof of a firmware bug or of a usable network route. Check Wi-Fi association, terminal power, actual IP and ZK TCP port 4370, authorized LAN routing and ACLs.
- Earlier measurements placed the M5 at `192.168.3.x` and ZKTeco at `10.1.65.2`; different subnets require an IT-approved route. Mac connectivity on a different network does not prove that the M5 can reach the attendance clock. Ask campus IT to verify authorized access if required.
- If the terminal requires a nonzero ZK communication key or rejects the SDK handshake, STOP. This build is not qualified to overcome such a requirement.
- If GET_TIME works but SET_TIME is not verified, check the physical display and terminal operations before any further action; never repeatedly send corrections to guess success.
- Do **not** factory-reset the attendance device, erase NVS, replace the certificate or change the network security configuration just to make a test pass.

## Local optional Mac verification / upload (USB only)

At the Mac's *existing* working repository, use the established PlatformIO environment. The current device already has the baseline firmware if the operator just flashed M13; reflashing is NOT required merely because this document was added.

```bash
cd "$HOME/zkteco-m5-lab/ZKTeco_set_time"  # or your actual existing clone
test -s include/config.h && test -s include/m5_tls_local.h || { echo "STOP: local config/cert missing"; exit 1; }
python3 -m unittest discover -s tests -p 'test_m13_*.py' -v
# ONLY if you need to upload/recover the same firmware:
pio run -e m5stickc-plus-production -t upload
```

Use the correct existing repository path; do not copy the sample `cd` if your clone is elsewhere. Do not run `erase_flash`, clean NVS or regenerate any CA/TLS key.

## Acceptance gate

- **Software build/static review: PASS** (same runtime source as green CI).
- **Reported operator RTC, battery, restart: PASS**.
- **Live attendance terminal read and physical display comparison: PENDING**.
- **Authorized live SET_TIME, independent readback and attendance invariant: PENDING**.

The release can be marked *field-verified* only after the last two pending items succeed on Sunday. If they do not, retain this as a software candidate and report the exact failure; the existing attendance device and its saved records must remain untouched.
