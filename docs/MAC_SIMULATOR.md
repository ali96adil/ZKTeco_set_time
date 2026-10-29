# Mac simulator — M5StickC Plus clock web UI

The Mac runner serves **exactly the embedded HTML/JavaScript** from \`src/main.cpp\`, rather than approximating its user interface. It is a **web/application simulator**, not a full emulation of the ESP32 chip, screen, Wi-Fi radio or ZKTeco TCP link.

## 1 — Mock device (safe default)

Requires macOS and Python 3.9+. From the repository root:

\`\`\`bash
git switch feature/m2-mobile-preview
python3 tools/mac_simulator.py --mode mock --offset-seconds 152
\`\`\`

Open **http://127.0.0.1:8765/** in Safari or Chrome on the **Mac**.

The virtual terminal starts approximately **2 minutes 32 seconds ahead** of the Mac clock, matching the previously diagnosed drift.

Use **قراءة ساعة الجهاز** to read it; choose **مزامنة الهاتف** or **إدخال يدوي** to preview a forward or backward adjustment. The extra button **تطبيق على الساعة الافتراضية فقط** modifies **memory on the Mac only**. Re-read and verify. The simulated clock resets when the server restarts.

An optional API smoke test is \`curl -s http://127.0.0.1:8765/api/read\`. It responds with \`"simulated":true\` and a wall-clock timestamp. Mock mode **never connects** to the real attendance terminal.

Stop the simulator with **Ctrl+C**.

## 2 — Read the real terminal (without write permissions)

Only if you want to compare actual time read from the previously verified ZKTeco iFace 950. From the repository root:

\`\`\`bash
~/zkteco-clock/.venv/bin/python tools/mac_simulator.py --mode live-readonly
\`\`\`

Then open **http://127.0.0.1:8765/**.

This mode uses \`pyzk\` to perform **connect → get_time → disconnect** to \`10.1.65.2:4370\`. It has **no clock-setting operation or POST endpoint**. If the terminal is unreachable, the page shows a read error.

## 3 — Safe network defaults

By default the server listens on **127.0.0.1**, accessible only from the Mac. This matters because the office wireless network is open, with a MikroTik Hotspot. **Do not bind an unprotected management interface to an open office Wi-Fi network.**

For a separately protected lab Wi-Fi only, \`--bind 0.0.0.0\` makes the simulator reachable from another trusted device via the Mac LAN address. Never port-forward it to the public internet.

## 4 — Offline tests

\`\`\`bash
python3 -m unittest discover -s tests -p 'test_mac_simulator.py' -v
node tests/clock_ui.test.cjs
\`\`\`

Tests cover the actual M5 HTML, HTTP API response, mock backward and forward clock changes, invalid dates and denial of time-setting requests in live-readonly mode. No staff records, fingerprint templates or attendance logs are accessed.

## 5 — What it does not prove

This is **not** M5 hardware emulation. It does not qualify M5StickC Plus Wi-Fi, the MikroTik Hotspot route, MCU protocol implementation, physical confirmation button or real device-time writes. Those still require later separate tests.
