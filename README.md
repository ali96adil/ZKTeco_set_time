# ZKTeco Clock Control — M5StickC Plus

**v1.0.0 — full-control production source · physical HTTPS/login verified · time writing needs field acceptance**

> The owner has tested real M5StickC Plus HTTPS, iPhone trust/login and session persistence across power cycle. The hardware's ZKTeco `SET_TIME` command has **not yet been verified** in this conversation. Default firmware is READ ONLY; enable `m5stickc-plus-secure-write-lab` only after a controlled protocol read/write qualification. See [v1 release notes](docs/RELEASE_V1_RC1.md).

## M10 — Complete HTTPS M5 production build

**[Full production & setup guide](docs/V1_FULL_CONTROL_HTTPS_SETUP.md)**

- **Default USB build:** `m5stickc-plus-production` — clock writing enabled on the M5's B button and on the authenticated iPhone HTTPS screen. Read-only remains optional for diagnostics, **not the normal release**.
- **One HTTPS URL:** `https://zkclock.local` on both M5 modes. In A / SETUP, it opens `/setup` on the private WPA2 AP; in B / CONNECT, it opens the authenticated operator dashboard. If Bonjour fails in SETUP, use `https://192.168.4.1/setup` (TLS SAN covers this address).
- **2-second write cooldown**, measured after the previous attempt completes. Independent SDK read after a clock-write and no automatic retry.
- Physical B hold ~2.2 seconds initiates any valid date adjustment. On iPhone, one tap executes any saved shortcut directly — no dialogs, including for differences greater than 24 hours. The independent readback and 2-second cooldown remain.
- The same existing locally trusted M5 certificate is used across both modes. **Never regenerate the certificate merely to upgrade Firmware.**
- The M9 physical HTTPS/login/reboot tests succeeded; M10's real ZKTeco write and physical SETUP HTTPS still require a controlled acceptance test.

## M9 — M5 HTTPS and renewable trusted iPhone sessions (draft)

**Branch:** [feature/m9-https-persistent-session](https://github.com/ali96adil/ZKTeco_set_time/tree/feature/m9-https-persistent-session) · [M9 deployment and security guide](docs/M9_HTTPS_SLIDING_SESSIONS.md) · [draft PR #9](https://github.com/ali96adil/ZKTeco_set_time/pull/9).

- M5 independently hosts **`https://zkclock.local/`** in CONNECT mode. Old plain HTTP is restricted to the protected physical SETUP AP.
- Configure a **fixed username/password once** on `http://192.168.4.1/auth/setup` while the M5 broadcasts its private WPA2 network. iPhone Safari AutoFill is supported. The salted password verifier is saved locally, not to GitHub.
- Phone session cookie is **Secure, HttpOnly, SameSite=Strict**, lasts **365 days**, and **renews on every authenticated visit**. There is no 90-day hard expiry; users can revoke all browser sessions.
- Full-datetime presets and M5 RTC can be managed independently from either the iPhone's trusted HTTPS web UI or the M5's physical buttons.
- **Real terminal writes remain disabled in the default firmware.** The separate write-enabled lab build compiles both physical-B and authenticated HTTPS command paths but is **not flashed automatically**. Qualify on real M5 and terminal before considering production activation.
- TLS CA/certificate/private key must be **generated on the operator's Mac** with `tools/create_m5_tls.sh`. The private key and generated `include/m5_tls_local.h` are ignored by Git; never commit or share them. iPhone must explicitly trust the resulting local CA.
- To fit TLS firmware, `huge_app.csv` is used on the original **4 MiB** M5StickC Plus (USB flashing, no OTA slot). Record existing preferences before the first firmware update.

## M8 — Fast one-page M5 control (working draft)

**New branch:** [feature/m8-fast-home-local-edit](https://github.com/ali96adil/ZKTeco_set_time/tree/feature/m8-fast-home-local-edit) · [operator guide](docs/M8_FAST_UI_LOCAL_EDIT.md) · [PR #8](https://github.com/ali96adil/ZKTeco_set_time/pull/8).

- `http://zkclock.local/` now contains **all essential tabs on one page** (Home, Commands, Settings, RTC). Saved shortcuts and the M5 RTC source appear on the Home screen, so you can **Prepare** them without navigating to another HTML page.
- In CONNECT mode, physical **A+B hold ~2 seconds** unlocks editing of saved full-date-time shortcuts, setup AP name, and LCD sleep duration for **90 seconds**. A successful edit closes the window. The station Wi-Fi password is never read, edited or sent over unencrypted campus Wi-Fi.
- **Prepare selects only**: it selects the command on M5's LCD. Clock-write execution remains a *physical hold-B* operation only in a separately validated write-enabled lab build; regular firmware stays **READ ONLY**.
- The same `zkclock.local` mDNS name is attempted on the protected setup AP; `192.168.4.1` is a fallback if iPhone does not resolve mDNS while joined to it.
- M5 does not use the temporary Mac HTTPS CA. Open HTTP on the university network is still unencrypted and has interception risk; for secure remote time writes use a verified TLS gateway/segregated network. Brief-on-demand operation does not remove that risk.

## M5 — Stable iPhone Home Screen and calibrated M5 RTC

**In draft branch `feature/m5-home-rtc`**. Full guide: [Home Screen, trusted Bonjour URL and RTC clock](docs/M5_HOME_RTC_ZK_CAPABILITIES.md).

- Mac HTTPS gateway exposes `/manifest.webmanifest`, Apple Home Screen icon and standalone metadata. Bonjour hostname **`<Mac LocalHostName>.local`** gives a stable name across DHCP changes on Wi-Fi networks where mDNS is allowed. The HTTPS certificate MUST cover that hostname: inspect with `bash tools/prepare_home_domain.sh`, then intentionally rotate it with `--rotate` if needed and re-trust the new temporary CA on the phone.
- M5 uses `zkclock.local` in normal Wi-Fi mode when mDNS is permitted; its protected setup AP retains the known fallback `192.168.4.1`. This does **not** share a hostname or web server with the Mac.
- M5 BM8563 RTC can be calibrated from the phone via the protected AP route `/rtc`, and a calibrated RTC appears as a selectable *physical* M5 shortcut. Seven-day calibration window, no automatic clock writes; M5 production firmware still read-only until hardware verification.
- iFace950 expanded SDK capabilities are documented as **proposals only**. No user, attendance or biometric records were fetched.

## M4 — Full clock commands and manual startup selection

**Current working draft:** [feature/m4-boot-ui-presets](https://github.com/ali96adil/ZKTeco_set_time/tree/feature/m4-boot-ui-presets) · [M4 guide](docs/M4_BOOT_AND_FULL_DATETIME.md).

- **Only two saved shortcut types:** full date+time (e.g. `2026-11-01T08:00:00`) or synchronize with the current phone time. **No time-only/date-only shortcuts.**
- **M5 startup now waits for your decision immediately:** Button **A = SETUP AP**, Button **B = CONNECT**. Choosing CONNECT retries the existing network indefinitely; **never auto switches to setup after 30 seconds**.
- **M5 local shortcuts:** save/import up to eight full datetime commands in its WPA2-protected `/presets` page. In CONNECT mode, tap A to cycle; hold B (~2.2s) to execute the highlighted command in a future qualified write-enabled build. Large shifts require holding B ~4.2s. The default firmware is still READ ONLY for safe physical Wi-Fi qualification.
- **Move shortcuts from Mac to M5:** use the Mac HTTPS dashboard's `نسخ أوامر التاريخ والوقت للـM5` button, then paste its content into the M5's setup AP `http://192.168.4.1/presets` import form. Phone sync stays a **phone-only** shortcut because the M5 cannot infer the phone clock while offline.
- Lab write-enabled code exists behind an explicit compile flag and is **compiled but not flashed** by CI. No M5 physical button or write path has yet been used on the real terminal.

## M3 progress: two network modes and saved mobile shortcuts

New development branch **feature/m3-network-presets**:

- M5StickC Plus: connects to existing 2.4 GHz Wi-Fi (open networks supported) or broadcasts a **WPA2-protected setup AP** after a 30-second Wi-Fi failure / holding button B. Configure from `http://192.168.4.1/setup` while joined to its private network. SSID, Wi-Fi password and terminal IP are saved to ESP32 NVS. **M5 terminal control remains READ ONLY** until hardware qualification.
- Mac HTTPS gateway: pair Safari once using the short Mac-displayed code (`--enable-pairing --paired-only`). Browser remembers session for 30 days; later use `--paired-only` to avoid recurring passwords. Pairing uses TLS and secure browser cookies.
- Save up to 12 shortcuts: **sync phone**, **specific time**, **specific date**, or **date+time**. On the proven Mac gateway, each quick button sends one live time update and one fresh verification when launched with `--enable-write --paired-only`. No repeated dialogs for small shifts; shifts over 24 hours require the previous manual-confirmation path.
- Firmware/AP features are not yet physically tested. The earlier Mac-to-ZKTeco write workflow was field-verified, but M3 pairing and presets have only offline tests.

See **[M3 configuration and usage guide](docs/M3_NETWORK_PAIRING_SHORTCUTS.md)** and [M3 draft pull request](https://github.com/ali96adil/ZKTeco_set_time/pull/3).

## Scope and behavior

The M5StickC Plus (original **Plus**, not Plus2) runs a local Wi-Fi web page:
- Press **A** on M5 or **Read Device** in the mobile browser to read the ZKTeco local wall clock.
- Shows **live elapsed device time**, phone Baghdad time and a stable approximate offset (the old M1 interface incorrectly froze device time between samples; fixed here).
- Choose **Phone Sync Preview**: sample the phone's clock on clicking Preview.
- Choose **Manual Preview**: enter an earlier or later date/time with seconds.
- Show the signed correction and a warning if the new clock would move backward.
- Warn about stale measurements (>60 seconds) and invalid calendar dates.
- **No Set Clock button, no time-write HTTP route and no CMD_SET_TIME.** Preview has no side effects.

Future write-enabled versions will support **both forward and backward** changes after operator confirmation, authentication and M5 physical consent. See [architecture](docs/ARCHITECTURE_AND_SAFETY.md) and [test plan](docs/TEST_PLAN.md).

This is exclusively a clock tool. Attendance logs, fingerprints, employee records, supervisor privileges and configurations are never queried or changed.

## Proven baseline and limitations

The Mac already proved successful read and set/reconnect verification to ZKTeco iFace 950, firmware **Ver 6.60 May 14 2018**, using `pyzk==0.9` and **TCP 4370**. **The ESP32 implementation is still untested on the physical device**.

The M5StickC Plus only uses 2.4 GHz Wi-Fi. For an OPEN WLAN with MikroTik Hotspot, Wi-Fi association needs no passphrase, but the Hotspot may separately block routed TCP/4370 or phone-to-M5 HTTP. See [OPEN_WIFI_MIKROTIK.md](docs/OPEN_WIFI_MIKROTIK.md) for read-only checks and authorized IT options. It must join a private Wi-Fi LAN which can route to the attendance terminal; the earlier Mac routing result alone does not guarantee access from the M5. Phone must access M5's same reachable private network. **Do not port-forward or expose the HTTP page to public networks.**

The terminal is set by an unencrypted SDK protocol with communication key 0 on the previously tested Mac link. Protect the network and review the router ACL with IT.

## Run a no-hardware Mac simulation first

This project now includes a **Mac simulator that serves the same embedded M5 mobile dashboard**. It defaults to a virtual clock, with absolutely no ZKTeco network connection:

```bash
python3 tools/mac_simulator.py --mode mock --offset-seconds 152
```

Open **http://127.0.0.1:8765/** in the Mac browser. Try phone-time synchronization, manual forward/backward previews, and the **SIMULATED APPLY** button (it changes only an in-memory fake clock). No ESP32 or attendance terminal is required.

Optionally read the real terminal's clock **without setting it** from the Mac that previously connected via pyzk:

```bash
~/zkteco-clock/.venv/bin/python tools/mac_simulator.py --mode live-readonly
```

The real-read mode has **no write route**. See [MAC_SIMULATOR.md](docs/MAC_SIMULATOR.md) for details and network restrictions.

## Build on macOS (first, no flashing)

```bash
git clone https://github.com/ali96adil/ZKTeco_set_time.git
cd ZKTeco_set_time
git switch feature/m2-mobile-preview

cp include/config.example.h include/config.h
nano include/config.h
# Fill your real 2.4-GHz Wi-Fi SSID; for OPEN Wi-Fi keep ZK_WIFI_PASSWORD as an empty string (\"\").
# Set ZK_DEVICE_IP to 10.1.65.2 if this is still the authorized device address.
# Save nano: Ctrl+O, Enter, Ctrl+X.

python3 -m venv .pio-venv
. .pio-venv/bin/activate
python -m pip install platformio

node tests/clock_ui.test.cjs
# Optional standalone protocol smoke test on Mac (requires clang++):
clang++ -std=c++11 -Wall -Wextra -Werror -pedantic -Iinclude tests/zk_wire_host.cpp -o /tmp/zk_wire_host && /tmp/zk_wire_host
pio run -e m5stickc-plus-readonly
```

**Do not paste Wi-Fi secrets into chat or commit them to GitHub.** The local `include/config.h` is ignored by Git. If `node` is unavailable, the UI test is optional but the PlatformIO build is still required.

## Hardware test only after build passes

Connect the **M5StickC Plus** to your Mac by USB and identify its port:

```bash
pio device list
pio run -e m5stickc-plus-readonly -t upload
pio device monitor -b 115200
```

If you have multiple serial ports, supply the correct one using `--upload-port`. After joining Wi-Fi the serial monitor prints the M5 IP, gateway and STA MAC; the latter is only for authorized network administration. The M5 screen will display `http://<LAN-IP>` when Wi-Fi connects. Open that address in the phone browser and press **Read Device**. The read-only firmware sends a request only when the button is pressed (no auto-polling).

Record whether: (a) M5 joins Wi-Fi, (b) device time read returns, (c) the displayed time agrees with the actual ZKTeco screen, and (d) the preview correctly handles earlier and later dates. Do **not** test the live write feature: it is intentionally absent.

The sample config uses a non-routable documentation IP `192.0.2.10`. Replace it before testing.

## Technical details

- PlatformIO env: `m5stickc-plus-readonly`; `board = m5stick-c`; `M5StickCPlus@0.1.1`.
- TCP/4370 SDK allowlist: `CMD_CONNECT=1000`, `CMD_GET_TIME=201`, `CMD_EXIT=1001`.
- No setting/reset/clear commands in this branch.
- Exposed local HTTP endpoints (GET /api/read rate-limited to one attempt every 8 seconds): `GET /`, `GET /api/read`; all other paths return 404.
- Time is a wall-clock value, not Unix UTC. Manual calendar comparisons use a synthetic +03:00 mapping of wall-clock fields; **older historical dates before 2008 are not intended as exact historical UTC instants**, but retain the exact civil time entered.
- Web UI reads one sample per click, then extrapolates locally and marks it stale after one minute.
- No clock authority is assumed for the M5 RTC. The phone's own clock can also be wrong.

## Test status

- [x] Source added to GitHub.
- [x] Mobile JS syntax verified and seven UI behavior tests passed in an isolated JavaScript runtime.
- [x] Shared read-only TCP frame/clock decoder extracted to `include/zk_wire.h` with offline C++ fixtures from pyzk, malformed-frame tests and forbidden-command checks.
- [x] GitHub Actions compile-and-test confirmed: [run 40851267969](https://github.com/ali96adil/ZKTeco_set_time/actions/runs/40851267969) (both firmware and static-ui jobs passed).
- [x] PlatformIO firmware build passed in CI. Mac local compilation is optional for source review/upload.
- [ ] Physical M5StickC Plus upload succeeds.
- [ ] Direct read over target Wi-Fi works.
- [ ] Write implementation (future milestone) independently tested.

Draft review: https://github.com/ali96adil/ZKTeco_set_time/pull/1
