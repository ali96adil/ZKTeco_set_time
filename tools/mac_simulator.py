#!/usr/bin/env python3
"""Local Mac simulator for the M5StickC Plus ZKTeco clock UI.

MOCK (default): operates on an in-memory virtual clock; it cannot contact the
attendance terminal. Applying a simulated adjustment modifies MEMORY ONLY.

LIVE-READONLY: can use the previously verified pyzk get_time() over TCP 4370,
but never imports or calls set_time(). No POST endpoint is enabled in this mode.

Start with: python3 tools/mac_simulator.py --mode mock --offset-seconds 152
Visit: http://127.0.0.1:8765
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

BAGHDAD = ZoneInfo("Asia/Baghdad")
ROOT = Path(__file__).resolve().parent.parent
FIRMWARE_SOURCE = ROOT / "src" / "main.cpp"
PAGE_PATTERN = re.compile(r'const char PAGE\[\] PROGMEM = R"HTML\((.*?)\)HTML";', re.S)
READ_COOLDOWN_SECONDS = 1.0


def dashboard_html(source_path: Path = FIRMWARE_SOURCE) -> str:
    """Serve the actual embedded firmware UI, not a separate approximation."""
    match = PAGE_PATTERN.search(source_path.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError("Cannot locate PAGE in M5 firmware source")
    return match.group(1)


def parse_local_datetime(value: object) -> datetime:
    """Validate a naive local civil date/time. Only used by fake-clock mode."""
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value
    ):
        raise ValueError("Expected local date and time YYYY-MM-DDTHH:MM:SS")
    dt = datetime.fromisoformat(value)
    if dt.year < 2000 or dt.year > 2099:
        raise ValueError("Year must be 2000-2099")
    return dt


class VirtualClock:
    """ZKTeco-like local clock; adjusted independently from the host's clock."""

    def __init__(self, offset_seconds: float = 152):
        self._lock = threading.Lock()
        self._base = (
            datetime.now(BAGHDAD).replace(tzinfo=None)
            + timedelta(seconds=offset_seconds)
        )
        self._anchor = time.monotonic()

    def get_time(self) -> datetime:
        with self._lock:
            return self._base + timedelta(seconds=time.monotonic() - self._anchor)

    def set_time(self, local_datetime: datetime) -> None:
        # This is ONLY a simulated in-memory clock. No real network I/O.
        if not 2000 <= local_datetime.year <= 2099:
            raise ValueError("Year must be 2000-2099")
        with self._lock:
            self._base = local_datetime
            self._anchor = time.monotonic()


def live_device_time(host: str, port: int) -> datetime:
    """Get time ONLY; intentionally contains no set_time or write operation."""
    try:
        from zk import ZK  # pyzk, optional for live read-only mode
    except ImportError as exc:
        raise RuntimeError(
            "pyzk not installed; use ~/zkteco-clock/.venv/bin/python "
            "or install pyzk in a local virtual environment"
        ) from exc

    conn = None
    try:
        # ommit_ping=True prevents an extra ICMP diagnostic call; no writes.
        conn = ZK(host, port=port, timeout=8, password=0,
                  force_udp=False, ommit_ping=True).connect()
        return conn.get_time()
    finally:
        if conn is not None:
            try:
                conn.disconnect()
            except Exception:
                pass


MOCK_PANEL = """
<section class="card" style="border-color:#5c7a50">
<h2 style="font-size:18px">محاكي التجربة على الماك</h2>
<p class="small">هذا الزر يضبط <b>الساعة الافتراضية في ذاكرة الماك فقط</b>.
لا يتصل بجهاز البصمة الحقيقي ولا يمس سجلات الحضور.</p>
<button id="mockApply" class="primary" type="button" style="background:#4b7958">
تطبيق على الساعة الافتراضية فقط</button>
<p id="mockStatus" class="small"></p></section>
<script>
document.getElementById('mockApply').onclick = async () => {
  const output = document.getElementById('mockStatus');
  const manualValue = document.getElementById('manual').value;
  const localTime = mode === 'manual'
    ? (manualValue.length === 16 ? manualValue + ':00' : manualValue)
    : baghdadParts(Date.now()).replace(' ', 'T');
  if (!localTime || !/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}$/.test(localTime)) {
    output.textContent = 'اختر تاريخاً ووقتاً صحيحين أولاً';
    return;
  }
  if (!window.confirm('تأكيد تعديل الساعة الافتراضية فقط إلى '+localTime+'؟')) return;
  output.textContent = 'جاري تطبيق التعديل على المحاكي...';
  try {
    const response = await fetch('/api/mock/set', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({local_datetime:localTime})
    });
    const result = await response.json();
    if (!response.ok || !result.ok)
      throw new Error(result.error || 'فشلت محاكاة التعديل');
    output.textContent = 'تم تعديل الساعة الافتراضية. اضغط قراءة للتحقق.';
    measuredOffsetMs = null;
    measuredAtMs = 0;
    document.getElementById('previewResult').hidden = true;
    document.getElementById('device').textContent = '—';
    document.getElementById('delta').textContent = '—';
  } catch (e) {
    output.textContent = e.message;
  }
};
</script>
"""


def page_for_mode(mode: str) -> bytes:
    page = dashboard_html()
    heading = ("المحاكاة الافتراضية — بدون اتصال بجهاز البصمة" if mode == "mock"
               else "قراءة ساعة جهاز البصمة الحقيقي فقط — بدون تغيير")
    page = page.replace(
        "<header>",
        '<header><p style="padding:12px;background:#244d35;border-radius:10px">'
        + heading + "</p>",
        1,
    )
    if mode == "mock":
        if "</main>" not in page:
            raise RuntimeError("Expected main tag not found in dashboard")
        page = page.replace("</main>", MOCK_PANEL + "</main>", 1)
    return page.encode("utf-8")


class MacSimulator(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], *, mode: str,
                 offset_seconds: float = 152,
                 device_host: str = "10.1.65.2",
                 device_port: int = 4370):
        if mode not in ("mock", "live-readonly"):
            raise ValueError("Unknown mode")
        self.mode = mode
        self.clock = VirtualClock(offset_seconds)
        self.device_host = device_host
        self.device_port = device_port
        self.last_read = 0.0
        self.read_lock = threading.Lock()
        self.page = page_for_mode(mode)
        super().__init__(address, MacHandler)

    def read_time(self) -> datetime:
        if self.mode == "mock":
            return self.clock.get_time()
        return live_device_time(self.device_host, self.device_port)


class MacHandler(BaseHTTPRequestHandler):
    server: MacSimulator

    def log_message(self, format: str, *args: object) -> None:
        # No confidential device information or request body in HTTP logs.
        print("%s %s" % (self.address_string(), format % args))

    def reply(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def as_json(self, status: int, obj: dict) -> None:
        self.reply(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            return self.reply(200, self.server.page, "text/html; charset=utf-8")
        if path == "/api/read":
            with self.server.read_lock:
                now = time.monotonic()
                if now - self.server.last_read < READ_COOLDOWN_SECONDS:
                    return self.as_json(429, {"ok": False, "error": "Read too frequent"})
                self.server.last_read = now
                start = time.monotonic()
                try:
                    clock = self.server.read_time()
                    return self.as_json(200, {
                        "ok": True,
                        "device_time": clock.strftime("%Y-%m-%dT%H:%M:%S"),
                        "duration_ms": int((time.monotonic() - start) * 1000),
                        "simulated": self.server.mode == "mock",
                    })
                except Exception as exc:
                    return self.as_json(503, {
                        "ok": False, "error": f"Read failed: {type(exc).__name__}"
                    })
        self.as_json(404, {"ok": False, "error": "Not found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        # LIVE mode has zero write endpoints, independent of request body.
        if self.server.mode != "mock" or path != "/api/mock/set":
            return self.as_json(404, {"ok": False, "error": "No write endpoint"})
        length = self.headers.get("Content-Length", "")
        if not length.isdigit() or not 0 < int(length) <= 256:
            return self.as_json(413, {"ok": False, "error": "Invalid body size"})
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self.as_json(415, {"ok": False, "error": "Use application/json"})
        try:
            document = json.loads(self.rfile.read(int(length)))
            if not isinstance(document, dict) or set(document) != {"local_datetime"}:
                raise ValueError("Invalid JSON keys")
            new_time = parse_local_datetime(document["local_datetime"])
        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            return self.as_json(400, {"ok": False, "error": "Invalid date/time"})
        self.server.clock.set_time(new_time)  # strictly local in-memory simulator
        self.as_json(200, {
            "ok": True, "simulated": True,
            "device_time": self.server.clock.get_time().strftime("%Y-%m-%dT%H:%M:%S"),
        })


def main() -> None:
    parser = argparse.ArgumentParser(description="M5StickC Plus Mac clock UI simulator")
    parser.add_argument("--mode", choices=("mock", "live-readonly"), default="mock")
    parser.add_argument("--offset-seconds", type=float, default=152.0,
                        help="Simulated device drift, default +152 seconds")
    parser.add_argument("--bind", default="127.0.0.1",
                        help="Bind address; default loopback only")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--device-host", default="10.1.65.2")
    parser.add_argument("--device-port", type=int, default=4370)
    args = parser.parse_args()
    if args.bind not in ("127.0.0.1", "::1", "localhost"):
        print("WARNING: LAN HTTP is unencrypted; avoid public/open Wi-Fi.")
        print("Use localhost unless running on an isolated trusted network.")
    server = MacSimulator((args.bind, args.port), mode=args.mode,
                          offset_seconds=args.offset_seconds,
                          device_host=args.device_host, device_port=args.device_port)
    host, port = server.server_address[:2]
    print(f"ZKTeco Mac simulator [{args.mode}] http://{host}:{port}")
    print("No real clock-setting commands exist in this simulator.")
    print("Stop with Ctrl+C.")
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
