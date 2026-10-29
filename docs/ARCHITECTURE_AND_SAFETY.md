# Architecture and Safety Review — ZKTeco Clock Control

Status: **DESIGN ONLY — NO DEVICE WRITES / NO FIRMWARE RELEASE**  
Target controller: **M5StickC Plus (original Plus, not Plus2)**  
Target attendance terminal: **ZKTeco iFace 950, firmware Ver 6.60 (2018-05-14)**

## 1. Existing evidence (29 Oct 2026)

On a Mac, `pyzk==0.9` successfully connected via ZKTeco SDK TCP port **4370** with communication key **0**, read the clock, and sent a clock-set request. An independent reconnect and three reads after setting showed the terminal within approximately one second of the Mac. An immediate read on the same connection initially returned the old time; therefore an ACK or immediate same-session read must **not** be treated as proof of applied time.

The Windows attendance workstation remains the source of truth for data backups and attendance management. Its users, biometric templates and attendance logs are **out of scope** for this project.

The M5StickC Plus has Wi-Fi (2.4 GHz) and a battery-backed RTC, but an RTC is **not** a trusted external time source and can drift.

## 2. Primary goal

A local, mobile-friendly web interface hosted on the M5StickC Plus to:
1. **Read** the ZKTeco wall-clock time and show link/firmware status.
2. Show the phone-supplied local Baghdad time and clock offset (read source only; no automatic setting).
3. **Set time manually**, entering full date + HH:MM:SS.
4. **Synchronize from the phone** only after explicit operator confirmation.
5. Reconnect and verify actual terminal time after setting.

No dependence on cloud, internet, Mac, or a continually running PC. **No automatic writes.**

## 3. Out of scope — prohibited firmware/API features

Do not implement device disable/enable, power-off, restart, attendance log download/delete, biometric/user read/write, supervisor permission changes, erase/reset, data clearing, firmware updates or any generic arbitrary ZKTeco command console. The production command allowlist is limited to:
- `CMD_CONNECT = 1000`
- `CMD_GET_TIME = 201`
- `CMD_SET_TIME = 202` (only through explicitly authorized write flow)
- `CMD_EXIT = 1001`
- `CMD_AUTH = 1102` **only if a nonzero communication key is later configured and explicitly approved**.

No personnel data, employee IDs, attendance records or passwords are collected.

## 4. Topology

```text
Phone browser --(private/authorized Wi-Fi LAN)--> M5StickC Plus (HTTP server)
                                              |
                                              | TCP/4370 on routed LAN
                                              v
                                        ZKTeco iFace 950
```

Normal mode: M5Stick joins the existing 2.4-GHz SSID as a Wi-Fi **STA**, and the phone reaches the M5Stick's private LAN IP. The router must permit TCP/4370 between those network segments. An earlier Mac-to-terminal route worked, but **does not prove the M5Stick route works**.

Do **not** assume SoftAP mode routes through to the ZKTeco LAN: AP+STA is not automatically a bridge. If provisioning AP is used, it must close after configuration; production writes must be limited to an approved isolated/secure network.

No Wi-Fi SSID, password, admin PIN, key or phone data is committed to GitHub. Public repo must never contain secrets.

## 5. Clock semantics and correctness

ZKTeco SDK time is a **local wall-clock representation**, not a Unix timestamp. The binary value is a 32-bit little-endian integer using the ZK month=31-day encoding. Implement and test year/month/day/hour/minute/second validity, leap years and year range.

Time sources:
- **Phone sync:** browser obtains current phone clock at the moment the operator submits. Display the effective **Asia/Baghdad (+03:00)** wall time for final confirmation, regardless of phone timezone. Browser clocks can be wrong: do not claim this is independently accurate.
- **Manual:** operator enters YYYY-MM-DD HH:MM:SS and explicitly acknowledges the proposed local Baghdad wall time.
- **RTC / NTP:** optional future hints only. Do not silently choose these as authority.

Transport latency must be recorded. Round-trip delays and clock drift make the delta an estimate, not microsecond precision. Target after fresh reconnect: within **2 seconds** of reference; larger differences or failed reads => **UNVERIFIED**, not SUCCESS.

## 6. Required state machine

```text
BOOT -> WIFI_CONNECTING -> READ_ONLY_READY
 READ_ONLY_READY -> READ_TIME -> SHOW_COMPARISON
 SHOW_COMPARISON -> PREPARE_REQUEST -> CONFIRM_REFERENCE
 CONFIRM_REFERENCE -> AUTHORIZE_OPERATOR -> PHYSICAL_CONFIRM
 PHYSICAL_CONFIRM -> SET_ONCE -> DISCONNECT -> WAIT -> RECONNECT
 RECONNECT -> READ_TWICE -> VERIFY -> SUCCESS | UNVERIFIED
```

Safety conditions:
- Read-only is the power-on default; no writes on boot/reconnect/time-out.
- Require PIN/session authentication, rate limit failed attempts, anti-CSRF for any write, and a **physical button on the M5Stick** pressed to authorize each write (short-lived window). An ordinary webpage alone must not be enough to set the clock.
- Require a recent successful device read (e.g., less than 60 s old) and a recent phone time sample (e.g., under 5 s); reject stale/ambiguous data.
- Present the old time, proposed time and signed offset; require explicit confirmation.
- Block implausible dates, unexpected timezone offsets, giant time jumps and clock-changing requests without physical authorization; any exceptional jump needs separate deliberate override and a documented maintenance window.
- Do not repeat set-time automatically if response is lost (avoid ambiguous double writes).
- Read time after disconnect/reconnect and short delay. Perform two reads; compare with the reference time adjusted for passage of time, not the original fixed timestamp.
- If verification fails, show **UNVERIFIED** and tell operator to compare the terminal display. Never mark an ACK alone as success.
- Do not lock terminal input via `CMD_DISABLEDEVICE`.

## 7. Attendance integrity and deployment precautions

Clock changes do **not** inherently delete old logs; however setting time backward may produce overlapping/duplicated local timestamps in **future punches**, affecting audit trails/payroll. Earlier logs retain their old timestamps and are **not** repaired by setting the clock.

Before first live SET_TIME:
1. With responsible office approval, preserve backup of Windows attendance database and exported attendance events. Verify backup can be opened.
2. Record terminal identity, firmware, displayed time and attendance record count.
3. Choose a period with **no employees checking in/out**.
4. Verify proposed reference time against another reliable clock.
5. Keep current Windows software unchanged; do not trigger download-and-clear actions.
6. After test, re-check record count and new punching behavior with authorized staff.

If read-only connection itself interferes with the terminal or workstation, stop the experiment.

## 8. Security

The ZKTeco SDK port is not a modern encrypted/authenticated management API (communication key=0 in the proven Mac setup). Securing the M5Stick web UI **does not secure the terminal if another LAN client can reach port 4370**. Restrict port 4370 by router ACL/firewall to authorized hosts if IT permits, and isolate network from guests.

HTTP on ESP32 can expose auth secrets on an untrusted LAN. Avoid exposing the web server outside the authorized Wi-Fi; never port-forward to the internet. Consider an operator-controlled isolated SSID, local physical consent, secure provisioning, strong unpredictable credentials and short sessions. No telemetry/cloud.

If permanently installed, use **stable USB-C power**, not the M5Stick's small battery as the sole source.

## 9. Implementation milestones / hold points

- **M0 (this branch):** architecture + risk/test plan, no firmware writes.
- **M1:** firmware builds on M5StickC Plus, Wi-Fi provisioning, secure read-only `GET_TIME`, read diagnostics, watchdog/timeouts and unit tests with simulated ZKTeco server. Never contact production target automatically on boot.
- **M2:** validate physical M5Stick read-only against actual terminal, including 2.4-GHz Wi-Fi route and coexistence with Windows attendance software.
- **M3:** add authenticated mobile UI for date/time entry and phone clock, but still **DRY_RUN** by default.
- **M4:** after explicit approved maintenance window + backup, add one-shot `SET_TIME` guarded by physical confirmation, disconnect/reconnect verification and audit log.
- **M5:** deploy, harden, measure drift and check attendance integrity.

## Sources

- `pyzk` protocol implementation: https://github.com/fananimi/pyzk/blob/master/zk/base.py
- ZKTeco command definitions: https://github.com/fananimi/pyzk/blob/master/zk/const.py
- Protocol notes: https://github.com/adrobinoga/zk-protocol/blob/master/sections/terminal.md
- M5StickC Plus official documentation: https://docs.m5stack.com/en/core/StickC-Plus

This is a design assessment, **not evidence that ESP32 firmware or a device write has been tested**.
