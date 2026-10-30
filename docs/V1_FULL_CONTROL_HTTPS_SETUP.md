# ZK Clock v1.0.0 — M10 full production candidate

**Two user-selected modes, one HTTPS domain:**

| M5 selection | iPhone Wi-Fi | URL | Purpose |
|---|---|---|---|
| A — SETUP | Join the M5 private WPA2 SSID shown/QR on M5 screen | **https://zkclock.local/** | HTTPS redirects to `/setup`: configure Wi-Fi, target ZKTeco IP, presets, internal RTC and fixed operator login |
| B — CONNECT | Join same reachable local network as the M5 | **https://zkclock.local/** | Authenticated dashboard: read the device clock, edit presets, sync RTC, execute ZKTeco clock corrections |

If `.local` discovery fails **in SETUP only**, use `https://192.168.4.1/setup`. The locally generated leaf cert from M9 already includes SAN `DNS:zkclock.local, IP:192.168.4.1`; this is a valid encrypted backup address, not HTTP. Do not bypass TLS errors or generate a new CA.

**Do not confuse the SSID and the site URL.** The AP may be named `ZK-Setup-xxxxxx` or a user-chosen name; the browser domain remains `https://zkclock.local`.

## Production behavior

- PlatformIO **default** is `m5stickc-plus-production`, enabling real `CMD_SET_TIME`. Not read-only. Optional diagnostic/read-only environment remains available solely for troubleshooting/rollback.
- Physical M5: A cycles presets, B long-press ~2.2s initiates one deliberate write; no second hold or additional confirmation, including for shifts over 24h.
- iPhone: authenticated web UI operates without physical A+B permission. One tap on **Execute** immediately sends exactly one authenticated command, with no browser confirmation, and no greater-than-24h confirmation. The HTTPS station API uses a one-year sliding Secure/HttpOnly/SameSite cookie, origin/CSRF protections and revocation.
- Clock-write **cooldown is 2 seconds after the previous attempt FINISHES**, including failures. Writes never auto-trigger at boot, network reconnect, or opening the page.
- Each clock command reads the terminal first, creates one SDK `SET_TIME` frame, expects acknowledgement, performs a new independent GET_TIME to verify, and **never retries automatically** on an uncertain result.
- Live `SYNC FROM M5 RTC` obtains a fresh M5 clock sample after initial ZKTeco read; if RTC calibration is expired (7 days) it refuses the write.
- Wi-Fi credentials only change from **physical AP SETUP over HTTPS**, not from campus station mode. The AP setup forms require same-origin HTTPS POSTs. All HTML setup, import and RTC pages are restricted to AP. The phone can edit nonsecret settings/shortcuts in normal authenticated CONNECT.
- HTTPS TLS key remains private in the *local* ignored `include/m5_tls_local.h`; the CI's disposable-CA binary must not be used as a device update. Preserve your trusted certificate and credentials.

## Operator deployment

User has already confirmed real HTTPS trust, password login, Safari session persistence after M5 power-cycle and quick repeat loading on the existing M9 branch. Production M10 code changes **have not yet been flashed or tested on the M5**, and no evidence exists that this ESP32 has ever written ZKTeco time successfully. That last hardware test is mandatory for full operational acceptance.

To compile and upload the **intended complete production** image locally (after verifying the real ZKTeco clock is reachable and scheduling a safe maintenance check):

```bash
cd ~/zkteco-m5-lab/ZKTeco_set_time || exit 1
git fetch origin
git switch main
git pull --ff-only origin main
test -s include/config.h || exit 1
test -s include/m5_tls_local.h || exit 1
test -s .secrets/m5-ca.crt || exit 1

"$HOME/.venvs/zk-platformio/bin/pio" run -e m5stickc-plus-production \
  -t upload --upload-port /dev/cu.usbserial-5D5A093FF0
```

**Do not call the M10 release field-certified until these tests complete:** power-cycle + two HTTPS modes, Wi-Fi reconfiguration AP, sessions still valid, access denied to setup page on station, terminal GET_TIME, one explicitly authorized small correction during a safe maintenance window with an independent physical comparison, and both iPhone/B-button execution. If the M5 cannot reach the ZKTeco IP `10.1.65.2` on its existing network, attempts must fail closed with a clear error; M5 `192.168.3.101` and terminal `10.1.65.2` require correct routing.

To rollback only in case of a real failure, use `m5stickc-plus-readonly` **diagnostic** build with the same local cert and NVS. Never delete/replace user-generated private TLS material casually.

## Critical maintenance constraints

- A production clock shift can impact attendance timestamps; **backup/record existing terminal time and work only when authorized**.
- ESP32 flash contains device-specific TLS private material and normal NVS preferences; do not distribute compiled production binaries or raw flash dumps.
- Server TLS leaf currently generated for one year; cookie renewability does not extend certificate validity. Plan deliberate renewal before expiry using the existing local CA rather than replacing it arbitrarily.
