# Mac HTTPS live clock control — optional M5 substitute

This separate Mac gateway runs the existing mobile dashboard and uses the same previously verified `pyzk` SDK for the ZKTeco iFace 950 on `10.1.65.2:4370`. **The earlier `mock` mode always changes a virtual clock only.** This is different: when deliberately enabled, this gateway can change the **actual** terminal's date/time.

**Current status: experimental draft. No live terminal write has been performed with the gateway code. Test/verify before use in production.** It is NOT ESP32 firmware.

## Three modes

| Command | Read actual device? | Set actual device? |
| --- | --- | --- |
| `tools/mac_simulator.py --mode mock` | No | Never (virtual only) |
| `tools/mac_simulator.py --mode live-readonly` | Yes | Never |
| `tools/mac_live_control.py` (without `--enable-write`) | Yes | No |
| `tools/mac_live_control.py --enable-write` | Yes | **Yes, after authenticated confirmation** |

This gateway is independent of the M5Stick firmware and does **not** add a firmware write opcode.

## Network and HTTPS requirements

The campus Wi-Fi is **open**, with a MikroTik captive portal. An ordinary HTTP control endpoint on this network is unsafe. This server therefore requires a TLS certificate and key for **all** modes, uses a randomly generated temporary administrator password, enforces Basic authentication, same-origin and CSRF protections, and requires a one-shot confirmation.

A self-signed certificate is **not trustworthy merely because Safari allows bypassing a warning**. Do not enter the operator password after clicking through an unverified certificate warning on the open Wi-Fi network. First establish a trusted certificate (or explicitly install/verify a private trust anchor on the phone), or operate exclusively on an isolated, protected administrative LAN. The Mac must still be able to route to ZKTeco over the permitted private LAN.

No port forwarding; do not expose this management server to the internet. Restrict Mac firewall access to authorized clients.

## macOS setup

From your checked-out project branch:

```bash
cd ~/zkteco-m5-lab/ZKTeco_set_time
git fetch origin
git switch feature/mac-live-control
git pull --ff-only origin feature/mac-live-control

mkdir -p .secrets
MAC_IP=$(ipconfig getifaddr en0)
echo "Mac IP: $MAC_IP"

openssl req -x509 -newkey rsa:3072 -sha256 -nodes \
  -keyout .secrets/mac.key -out .secrets/mac.crt -days 7 \
  -subj "/CN=$MAC_IP" \
  -addext "subjectAltName=IP:$MAC_IP,IP:127.0.0.1,DNS:localhost"

chmod 600 .secrets/mac.key
```

**Important:** This creates a self-signed lab certificate, which iOS will NOT trust automatically. For real mobile use on an open Wi-Fi network, arrange **proper certificate trust and validation** with IT first. Never copy private keys to the phone. The certificate/key stay local and are excluded from Git.

Test the gateway read-only *on the Mac* (it still needs a valid/trusted HTTPS cert for the browser):

```bash
~/zkteco-clock/.venv/bin/python tools/mac_live_control.py \
  --cert .secrets/mac.crt --key .secrets/mac.key
```

When the Mac and phone are on an isolated, authorized network where the certificate trust is established, explicitly enable live write support:

```bash
~/zkteco-clock/.venv/bin/python tools/mac_live_control.py \
  --bind 0.0.0.0 --port 8766 \
  --cert .secrets/mac.crt --key .secrets/mac.key \
  --enable-write
```

Open `https://MAC_IP:8766/` from the phone, using the **actual LAN IP** from the command. The Mac terminal prints temporary credentials: username `operator` and a random password that changes each restart. Use the credentials *only after verifying the HTTPS certificate*.

This server defaults to `127.0.0.1` and **read-only**. The deliberate `--enable-write` flag is required for real clock changes. Server port **8766** is separate from mock simulator port **8765**; close the mock simulator if it is confusing to compare tabs.

## Mobile workflow, actual device

1. Authenticate over trusted HTTPS.
2. Press **قراءة ساعة الجهاز**; compare with a trusted real-world clock.
3. Select **مزامنة الهاتف** or **إدخال يدوي**. Both backward and forward changes are supported.
4. Press **تحضير تصحيح فعلي**. The Mac reads the device again and shows old/new times and signed offset. The request expires within 25 seconds.
5. If the offset is correct, acknowledge the database backup, no staff clocking in/out and valid time source; press **تنفيذ التصحيح على جهاز البصمة**, then accept the final browser confirmation.
6. The gateway sends **one** `pyzk.set_time()` request, disconnects, and reads the terminal through **two new connections**. Only two readings within 2 seconds of expected advancing time count as `VERIFIED`.
7. `UNVERIFIED` or network error means check the physical terminal display **before attempting a second correction**. Never auto-retry an ambiguous write.

A backwards correction may create overlapping timestamps for **new** attendance events but does not inherently erase historical logs. Do the correction during a maintenance window and retain a checked backup.

## Safety boundaries

- No user, face, fingerprint, administrator or attendance-record functions.
- No device disable, erase, reset, or automatic synchronization loops.
- One pending transaction, one-time token consumed before sending.
- HTTPS, short-lived in-memory credentials, CSRF and same-origin restrictions.
- Audit log contains the adjustment direction/magnitude and verification outcome only.
- The original unencrypted ZKTeco TCP/4370 network still requires router access controls.
- The gateway must be stopped with **Ctrl+C** when the session ends.

## Validation

- [x] Independent earlier Mac `pyzk` read/set/reconnect experiment confirmed clock adjustment.
- [ ] Syntax, isolated gateway tests and GitHub Actions for this new gateway confirmed.
- [ ] Trusted mobile HTTPS certificate and authorization reviewed.
- [ ] Controlled live write via this new gateway confirmed by an operator during an approved maintenance window.

This document and code do not prove that the new gateway was used on the live attendance device.
