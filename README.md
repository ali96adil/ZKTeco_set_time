# ZKTeco Clock Control — M5StickC Plus

**M2: EXPERIMENTAL, READ-ONLY + MOBILE DRY-RUN PREVIEW**

> No firmware binary has been built or flashed on the owner's physical M5StickC Plus yet. The existing ZKTeco terminal must not be changed by this branch.

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

The Mac already proved successful read and set/reconnect verification to ZKTeco iFace 950, firmware **Ver 6.60 May 14 2018**, using \`pyzk==0.9\` and **TCP 4370**. **The ESP32 implementation is still untested on the physical device**.

The M5StickC Plus only uses 2.4 GHz Wi-Fi. It must join a private Wi-Fi LAN which can route to the attendance terminal; the earlier Mac routing result alone does not guarantee access from the M5. Phone must access M5's same reachable private network. **Do not port-forward or expose the HTTP page to public networks.**

The terminal is set by an unencrypted SDK protocol with communication key 0 on the previously tested Mac link. Protect the network and review the router ACL with IT.

## Build on macOS (first, no flashing)

\`\`\`bash
git clone https://github.com/ali96adil/ZKTeco_set_time.git
cd ZKTeco_set_time
git switch feature/m2-mobile-preview

cp include/config.example.h include/config.h
nano include/config.h
# Fill your real 2.4-GHz Wi-Fi SSID and password.
# Set ZK_DEVICE_IP to 10.1.65.2 if this is still the authorized device address.
# Save nano: Ctrl+O, Enter, Ctrl+X.

python3 -m venv .pio-venv
. .pio-venv/bin/activate
python -m pip install platformio

node tests/clock_ui.test.cjs
pio run -e m5stickc-plus-readonly
\`\`\`

**Do not paste Wi-Fi secrets into chat or commit them to GitHub.** The local \`include/config.h\` is ignored by Git. If \`node\` is unavailable, the UI test is optional but the PlatformIO build is still required.

## Hardware test only after build passes

Connect the **M5StickC Plus** to your Mac by USB and identify its port:

\`\`\`bash
pio device list
pio run -e m5stickc-plus-readonly -t upload
pio device monitor -b 115200
\`\`\`

If you have multiple serial ports, supply the correct one using \`--upload-port\`. The M5 screen will display \`http://<LAN-IP>\` when Wi-Fi connects. Open that address in the phone browser and press **Read Device**. The read-only firmware sends a request only when the button is pressed (no auto-polling).

Record whether: (a) M5 joins Wi-Fi, (b) device time read returns, (c) the displayed time agrees with the actual ZKTeco screen, and (d) the preview correctly handles earlier and later dates. Do **not** test the live write feature: it is intentionally absent.

The sample config uses a non-routable documentation IP \`192.0.2.10\`. Replace it before testing.

## Technical details

- PlatformIO env: \`m5stickc-plus-readonly\`; \`board = m5stick-c\`; \`M5StickCPlus@0.1.1\`.
- TCP/4370 SDK allowlist: \`CMD_CONNECT=1000\`, \`CMD_GET_TIME=201\`, \`CMD_EXIT=1001\`.
- No setting/reset/clear commands in this branch.
- Exposed local HTTP endpoints: \`GET /\`, \`GET /api/read\`; all other paths return 404.
- Time is a wall-clock value, not Unix UTC. Manual calendar comparisons use a synthetic +03:00 mapping of wall-clock fields; **older historical dates before 2008 are not intended as exact historical UTC instants**, but retain the exact civil time entered.
- Web UI reads one sample per click, then extrapolates locally and marks it stale after one minute.
- No clock authority is assumed for the M5 RTC. The phone's own clock can also be wrong.

## Test status

- [x] Source added to GitHub.
- [x] Mobile JS syntax verified and seven UI behavior tests passed in an isolated JavaScript runtime.
- [x] GitHub Actions compile-and-test confirmed: [run 40851267969](https://github.com/ali96adil/ZKTeco_set_time/actions/runs/40851267969) (both firmware and static-ui jobs passed).
- [x] PlatformIO firmware build passed in CI. Mac local compilation is optional for source review/upload.
- [ ] Physical M5StickC Plus upload succeeds.
- [ ] Direct read over target Wi-Fi works.
- [ ] Write implementation (future milestone) independently tested.

Draft review: https://github.com/ali96adil/ZKTeco_set_time/pull/1
