# M5 ZK Clock v1.0.0-rc1 — Release candidate

Build: original M5StickC Plus (4 MiB flash); USB firmware upload with `huge_app.csv` partition.

## Verified on the physical M5 by operator

- Wi-Fi CONNECT, HTTPS `https://zkclock.local`, trusted local CA installed on iPhone.
- Fixed credentials accepted with Safari; long-lived Secure/HttpOnly session.
- Session survives turning the M5 off and on.
- Second opening of the web UI is fast; Mac direct HTTPS tests ~1.5–1.8 seconds; first hostname lookup may add time.
- SETUP AP provisioning and screen navigation have worked in earlier M5 builds.

## Final software release hardening

- iPhone dashboard **Read** button calls the actual protected HTTPS endpoint `/api/m9/read`, not the old inaccessible `/api/read`.
- iPhone PWA manifest and icon are delivered over HTTPS (no broken HTTP links).
- Home page tabs and authenticated shortcut editor, RTC sync, settings and revoke-all sessions stay independent of Mac.
- Local button A selects a shortcut; long B triggers an action in opt-in write-enabled firmware; large time shifts need longer physical confirmation.
- Network wire-level `CMD_SET_TIME` encoder has an exact PyZK reference byte fixture: header checksum intentionally uses the previous reply-ID, then increments it.
- Live RTC time is freshly sampled after reading the target terminal, immediately before the write. A 10-second duplicate-write cooldown prevents back-to-back attempts.
- Failed or unverified clock writes are **never** silently retried. Only a fresh independent ZK GET_TIME read with an appropriate clock value can report success.
- Secure cookies have a rolling one-year expiry on each authenticated request; users can revoke all sessions.
- No employee, attendance or biometric records are fetched.

## Release qualification status

This is a **release candidate, not yet write-qualified production firmware**. User physically confirmed HTTPS and sessions; no evidence in this conversation that either `GET_TIME` or `SET_TIME` on the real iFace950 has passed with this ESP32 hardware and network. Compilation alone cannot establish that. Don't claim full attendance-clock write support until the field checklist completes.

The default deployable environment is **`m5stickc-plus-readonly`**. The separately compiled **`m5stickc-plus-secure-write-lab`** enables real time writes from both HTTPS and physical M5 buttons. It must not be flashed blindly.

### Field acceptance (requires user at the actual terminal)

1. Record current time and backup/importable evidence, check reachability of ZK target `10.1.65.2:4370` from M5's active Wi-Fi. The M5 has previously been observed on `192.168.3.101`; different subnets are fine **only if the network routes between them**.
2. Verify authenticated HTTPS `Read` shows terminal clock correctly, in READ ONLY firmware.
3. With authorized maintenance window and no live attendance capture, explicitly flash the write-lab environment *only after* read operation and protocol tests pass.
4. Perform a single carefully controlled, small time change, then independent readback; inspect terminal screen. Avoid large, backward or arbitrary-date shifts on production data.
5. Execute a separate physical B-button test only when the phone test is verified, and ensure post-action 10-second cooldown.
6. Reboot M5; verify long-lived HTTPS session, no automatic write on boot, no dual-button action requirement.
7. If any read/verify fails, stop and revert to read-only firmware, preserving the same per-device HTTPS key and credentials. Never erase NVS unnecessarily.

### Deployment

Generate per-device cert only if not already present: `bash tools/create_m5_tls.sh`. Don't regenerate a CA that the iPhone already trusts. The generated private TLS key remains in the local ignored `include/m5_tls_local.h`.

```bash
cd ~/zkteco-m5-lab/ZKTeco_set_time
git fetch origin && git switch release/v1.0.0-rc1
git pull --ff-only origin release/v1.0.0-rc1
test -f include/config.h && test -f include/m5_tls_local.h
"$HOME/.venvs/zk-platformio/bin/pio" run -e m5stickc-plus-readonly \
  -t upload --upload-port /dev/cu.usbserial-5D5A093FF0
```

**Do not distribute the local binary** without protecting the embedded TLS private key. The compiled CI binary uses a disposable test certificate and cannot replace the operator's locally generated trusted certificate.

**Known future task:** Renew the device HTTPS server certificate before its one-year expiration (independent from cookie lifetime), using a local reflash, preserving the existing trusted private CA.
