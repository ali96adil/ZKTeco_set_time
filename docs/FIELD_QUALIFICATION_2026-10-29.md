# Mac HTTPS Live Clock Control — Field qualification 2026-10-29

## Scope

User-operated, authorized local Mac gateway connected to the ZKTeco attendance terminal through the previously tested Python SDK; the iPhone acted as an HTTPS browser client. The M5StickC Plus hardware itself was **not** used in this field test.

## Evidence reported by operator

The following is a **sanitized summary** of actual Mac gateway logs supplied by the operator. Credentials, internal addresses, session tokens and sensitive data are intentionally omitted.

- Gateway mode: `LIVE CLOCK WRITES ENABLED`.
- Authenticated browser requests: `GET /`, `GET /api/read`, `POST /api/prepare` and `POST /api/apply`.
- Manual time adjustment: `CLOCK_CHANGE source=manual delta_seconds=92 sent=True verified=True write_error=None`.
- Phone time adjustment: `CLOCK_CHANGE source=phone delta_seconds=-92 sent=True verified=True write_error=None`.
- Subsequent `GET /api/read` requests were observed after both applications.

## Conclusions

1. The user exercised **real SDK clock writes**, not just the in-memory `mock` simulator. Both manual adjustment and phone synchronization succeeded according to the gateway's two-fresh-read verification policy.
2. Backward movement and forward movement are both supported and were observed; the approximately opposite changes largely canceled. These results **do not independently prove** that the phone itself had an accurate clock; the user should verify against a trusted time source if required.
3. The logs show `verified=True` and `write_error=None` for both changes. Physical display confirmation, staff data invariants, biometric state and attendance database checks were **not reported** and are not asserted here.
4. The current field qualification is for **Mac HTTPS gateway only**. It does **not** qualify the M5StickC Plus firmware, the open Wi-Fi route for the M5, or the future hardware-button authorization.
5. The temporary login password was inadvertently included in a shared log; it must be treated as compromised. The operator was instructed to stop the server with Ctrl+C and not leave the HTTPS write gateway available on the open campus WLAN.

## Operational disposition

- **Mac browser → HTTPS Mac gateway → real ZKTeco time read:** verified.
- **Mac browser → manual live time adjustment → two new readings:** verified by program logs.
- **Mac browser → phone-clock live synchronization → two new readings:** verified by program logs.
- **Safety default:** keep `--enable-write` off outside a brief, authorized maintenance window. Stop the process when finished. The gateway intentionally generates a new password on every restart.
- **Security caveat:** this does not amount to a complete penetration test or production security audit. The campus SSID is open; use a restricted authorized management segment and verified HTTPS trust for future sessions.

No new live command was executed when recording this document.
