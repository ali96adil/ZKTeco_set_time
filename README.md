# ZKTeco Clock Control — M5StickC Plus

**Current branch: M1 experimental / READ ONLY.**  
**No firmware compiled, flashed or tested against the actual M5Stick yet.**  
**No setting of the attendance terminal's date or time is implemented in this branch.**

## What is currently implemented

- ESP32 Wi-Fi Station mode (2.4 GHz).
- Local mobile dashboard to **read** device time via `GET /` and `GET /api/read`.
- Button A reads terminal time; button B does nothing.
- Direct binary TCP connection to ZKTeco SDK port 4370: `CMD_CONNECT (1000)`, `CMD_GET_TIME (201)`, `CMD_EXIT (1001)`.
- Bounded frame lengths, connection timeouts and validation of returned wall clock values.
- No employee, attendance or biometric operations. **No `CMD_SET_TIME (202)`**.

The separate project to enable **manual setting** and **phone-supplied time sync** will only be added after read-only qualification and safeguards. See [Architecture and Safety](docs/ARCHITECTURE_AND_SAFETY.md) and [Test Plan](docs/TEST_PLAN.md).

## Device/platform

- **M5StickC Plus** (original Plus, not Plus2).
- PlatformIO environment `m5stickc-plus-readonly`; board target `m5stick-c`, with `M5StickCPlus` library.
- Serial 115200 baud.
- Target device: ZKTeco iFace 950; tested **only from Mac** with `pyzk==0.9`, firmware Ver 6.60 May 14 2018.

## Prepare locally on macOS

Clone the repository and switch to this development branch. This does not alter the terminal:

```bash
git clone https://github.com/ali96adil/ZKTeco_set_time.git
cd ZKTeco_set_time
git switch feature/m1-read-only

cp include/config.example.h include/config.h
# Edit include/config.h with actual Wi-Fi SSID/password and authorized target IP.

python3 -m venv .pio-venv
. .pio-venv/bin/activate
python -m pip install platformio
pio run -e m5stickc-plus-readonly
```

Do **not** put Wi-Fi credentials in public files. `include/config.h` is in `.gitignore`.

After a successful build, inspect the source and only then flash the **READ-ONLY** firmware to the M5StickC Plus. For example (USB serial port must match the Mac):

```bash
pio device list
pio run -e m5stickc-plus-readonly -t upload --upload-port /dev/cu.usbserial-EXAMPLE
pio device monitor -b 115200
```

M5Stick must be on an authorized 2.4 GHz network with an actual route to the attendance device; a successful **Mac** test alone does not prove this device will connect. The phone opens `http://<M5-LAN-IP>/` shown on the M5 display.

**Network caution:** M1's local HTTP dashboard has no login because it is read-only. Use only on a private authorized LAN; no public exposure or port forwarding. The future write-capable build will require authentication, CSRF defense and physical authorization.

## What NOT to do

- Do not reset the ZKTeco, change administrator privileges, delete logs or upload employees.
- Do not assume a web page showing a time is sufficient to prove setting time.
- Never enable automated clock changes before backup and maintenance-window approval.
- Do not assume M5StickC Plus's RTC knows the correct real-world time.

Source protocol references:
- https://github.com/fananimi/pyzk/blob/master/zk/base.py
- https://github.com/fananimi/pyzk/blob/master/zk/const.py
- https://docs.m5stack.com/en/core/StickC-Plus
