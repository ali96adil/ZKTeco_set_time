# Validation Plan — M5StickC Plus / ZKTeco Time Control

**No test below authorizes an uncontrolled live SET_TIME.** All production writes require explicit operator action after backup, clock verification and a maintenance window.

## Known-good baseline (Mac)

- ZKTeco iFace 950; firmware `Ver 6.60 May 14 2018`.
- Existing Mac `pyzk==0.9` connected to the terminal using TCP port 4370, communication key zero.
- Mac `get_time()` and `set_time()` tested successfully.
- Fresh connection after write read device time close to Mac time: differences approximately **-1.03 s, -0.10 s, -0.15 s**.
- **Important:** immediate `get_time()` after the write on the same connection returned a stale pre-adjustment clock; a fresh connection was needed to confirm.

## Gate A — source and firmware static review

- [ ] M5StickC Plus target selected (not Plus2); choose compatible board/framework/library.
- [ ] Implement strict ZK command allowlist: CONNECT/GET_TIME/EXIT; SET_TIME added later behind compile-time flag.
- [ ] No `CLEAR_*`, `DELETE_*`, `DISABLEDEVICE`, reboot or user/template/attendance endpoints.
- [ ] No credentials/SSID/API keys in Git history; `.gitignore` catches local secrets.
- [ ] Bound every network frame and timeout; watchdog and safe disconnect.
- [ ] Serialize device requests (never interleave two connections for a single operation).
- [ ] Sensitive HTTP endpoints require authentication, CSRF defense and rate limiting; no cloud/port forwarding.

## Gate B — offline protocol tests (simulated server)

- [ ] 8-byte TCP magic/length frame exactly matches pyzk.
- [ ] 8-byte ZK header/checksum, session/reply IDs and ACK codes validated.
- [ ] Fragmented TCP replies (partial reads) are reassembled safely.
- [ ] Reject malformed lengths, truncated payload, stale/mismatched session, invalid command/ACK, delayed response.
- [ ] Test date codec for leap days, month boundaries, year bounds and February 29.
- [ ] Device time is local wall clock and never directly interpreted as a Unix epoch.
- [ ] Simulation tests prove that read-only build emits **zero** `CMD_SET_TIME` packets.
- [ ] Lost set-time ACK must not cause automatic retransmit.
- [ ] Verify waits/reconnects: success only after fresh reads with drift within tolerance.

## Gate C — read-only hardware qualification

- [ ] M5StickC Plus connected to 2.4 GHz SSID and obtains a network lease.
- [ ] From M5Stick, TCP to target terminal port 4370 succeeds (Mac's route is not sufficient proof).
- [ ] Two separate read-only sessions succeed and match terminal display.
- [ ] Repeated read during normal attendance operations causes no lockups/interference.
- [ ] No employee, face, fingerprint or attendance records read.
- [ ] Station Wi-Fi drop, router reboot and M5 power cycle do not trigger clock writes.
- [ ] Compare user-visible mobile time/terminal time; inspect network latency.

## Gate D — web interface dry-run

- [ ] Default state read-only; Sync and Manual forms show preview but cannot write.
- [ ] Manual date/time rejects impossible dates and formatting but intentionally accepts earlier and later valid dates.
- [ ] Phone time is gathered at button click (not page load).
- [ ] Display Asia/Baghdad local time even when phone is set to another timezone.
- [ ] Show stale source clock, unreliable phone time and high latency warnings.
- [ ] Unauthorized clients cannot invoke clock write path.
- [ ] CSRF, guessing PIN, double submission and stale confirmation are rejected.
- [ ] Physical M5 button is required for each future write.

## Gate E — live write (only after authorization)

- [ ] IT/office authority approval obtained; personnel/attendance backups exist and were verified.
- [ ] Record count/time of device before change, without exporting PII to this project.
- [ ] Perform test **outside punch-in/out window**, with no active transactions.
- [ ] Double-check phone or manually entered time against separate trusted source.
- [ ] Operator reads old/new times and signs off on proposed jump (signed offset in seconds/minutes, forward or backward).
- [ ] Backward time correction is available in both manual and phone-sync modes, including shifts greater than 2 minutes, after a visible attendance timestamp-collision warning and explicit extra acknowledgement; the direction alone never blocks the action.
- [ ] Audit signed correction amount and source (phone/manual) without recording attendance/biometric data.
- [ ] Test rollback correction with a simulator first; never test large live backward shifts during staff check-in.
- [ ] One deliberate `CMD_SET_TIME`; NO automatic retry.
- [ ] Disconnect, wait, reconnect, read twice, compare with advancing reference clock.
- [ ] Show **VERIFIED** only if both reads are within 2 seconds; otherwise **UNVERIFIED**.
- [ ] Ensure existing attendance log count did not decrease and ordinary check-in still works.
- [ ] Audit entry contains time, source and signed offset only; NO user biometric data.

## Stop conditions

Stop immediately if the terminal stops accepting attendance, log counts unexpectedly decrease, communication is unstable, repeated reads interfere with the workstation, or firmware emits unallowlisted commands. Return to existing Windows tool for attendance administration; never reset/erase the terminal to recover a test.

## Release criteria

M1 read-only may be installed after Gates A/B and tested at Gate C. Production write feature remains off until Gates A–E are passed. Design spec: [ARCHITECTURE_AND_SAFETY.md](ARCHITECTURE_AND_SAFETY.md).
