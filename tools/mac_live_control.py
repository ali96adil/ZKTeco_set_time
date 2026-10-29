#!/usr/bin/env python3
"""Explicitly opt-in HTTPS Mac gateway for reading/setting ZKTeco clock.

This is NOT firmware. It runs on the Mac and uses proven pyzk TCP SDK.
No connections at startup. --enable-write is REQUIRED for set operations.
Never exposes a write interface on unencrypted HTTP.
No employee or biometric APIs; do not export attendance data.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import ssl
import threading
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from mac_simulator import dashboard_html, parse_local_datetime
from clock_presets import ShortcutStore, target_time
from phone_pairing import PairingStore, get_cookie, cookie_header
from shortcut_ui import shortcut_panel

BAGHDAD = ZoneInfo("Asia/Baghdad")
MAX_BODY = 512
PREPARE_LIFETIME = 25.0
VERIFY_TOLERANCE = 2.0


def baghdad_naive_from_epoch_ms(epoch_ms: int) -> datetime:
    if not isinstance(epoch_ms, int) or isinstance(epoch_ms, bool):
        raise ValueError("Invalid phone epoch")
    dt = datetime.fromtimestamp(epoch_ms / 1000, BAGHDAD).replace(tzinfo=None)
    if not 2000 <= dt.year <= 2099:
        raise ValueError("Phone clock outside supported years")
    return dt


def read_real_clock(host: str, port: int) -> datetime:
    from zk import ZK
    conn = None
    try:
        conn = ZK(host, port=port, timeout=8, password=0,
                  force_udp=False, ommit_ping=True).connect()
        return conn.get_time()
    finally:
        if conn is not None:
            try:
                conn.disconnect()
            except Exception:
                pass


def set_real_clock_once(host: str, port: int, dt: datetime) -> None:
    """Exactly one command; never retry even if network response is ambiguous."""
    from zk import ZK
    conn = None
    try:
        conn = ZK(host, port=port, timeout=8, password=0,
                  force_udp=False, ommit_ping=True).connect()
        conn.set_time(dt)
    finally:
        if conn is not None:
            try:
                conn.disconnect()
            except Exception:
                pass


@dataclass(frozen=True)
class PendingChange:
    nonce: str
    old_clock: datetime
    proposed: datetime
    source: str
    prepared_at: float
    phone_epoch_ms: int | None


class Gateway(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr: tuple[str, int], *, device_host: str,
                 device_port: int, password: str, enable_write: bool,
                 reader=None, setter=None, shortcut_path=None,
                 pairing_path=None, allow_pairing=False, allow_basic=True):
        self.device_host = device_host
        self.device_port = device_port
        self.password = password
        self.allow_basic = allow_basic
        self.csrf_token = secrets.token_urlsafe(32)
        self.enable_write = enable_write
        self.reader = reader or (lambda: read_real_clock(device_host, device_port))
        self.setter = setter or (lambda dt: set_real_clock_once(device_host, device_port, dt))
        self.lock = threading.RLock()
        self.shortcuts = ShortcutStore(Path(shortcut_path or ".secrets/shortcuts.json"))
        self.pairing = PairingStore(
            Path(pairing_path or ".secrets/paired_phones.json"),
            allow_new=allow_pairing,
        )
        self.last_quick = 0.0
        self.pending: PendingChange | None = None
        self.page = build_live_page(self.csrf_token, enable_write)
        super().__init__(addr, Handler)

    def read_once(self) -> datetime:
        # This lock serializes concurrent SDK sessions with local writes.
        with self.lock:
            return self.reader()

    def prepare(self, doc: dict) -> dict:
        with self.lock:
            if not self.enable_write:
                raise PermissionError("Write mode is disabled")
            if doc.get("source") not in ("manual", "phone"):
                raise ValueError("Invalid time source")
            source = doc["source"]
            prepared_at = time.monotonic()
            phone_epoch_ms = None
            if source == "manual":
                if set(doc) != {"source", "local_datetime"}:
                    raise ValueError("Invalid manual fields")
                proposed = parse_local_datetime(doc["local_datetime"])
            else:
                if set(doc) != {"source", "client_epoch_ms"}:
                    raise ValueError("Invalid phone fields")
                phone_epoch_ms = doc["client_epoch_ms"]
                proposed = baghdad_naive_from_epoch_ms(phone_epoch_ms)
                # A stale or inaccurate phone clock needs operator review;
                # no implicit NTP correction occurs.
            old = self.reader()
            self.pending = PendingChange(
                nonce=secrets.token_urlsafe(24),
                old_clock=old,
                proposed=proposed,
                source=source,
                prepared_at=prepared_at,
                phone_epoch_ms=phone_epoch_ms,
            )
            diff = (proposed - old).total_seconds()
            return {
                "ok": True,
                "nonce": self.pending.nonce,
                "old_time": old.strftime("%Y-%m-%dT%H:%M:%S"),
                "proposed_time": proposed.strftime("%Y-%m-%dT%H:%M:%S"),
                "offset_seconds": int(round(diff)),
                "backward": diff < 0,
                "expires_in_seconds": int(PREPARE_LIFETIME),
            }

    def apply(self, doc: dict) -> dict:
        with self.lock:
            if not self.enable_write:
                raise PermissionError("Write mode is disabled")
            if set(doc) != {"nonce", "confirmed", "backup_confirmed"}:
                raise ValueError("Invalid confirmation fields")
            p = self.pending
            # Consume the request once whether it succeeds or fails.
            self.pending = None
            if p is None or not secrets.compare_digest(str(doc["nonce"]), p.nonce):
                raise ValueError("No valid pending change")
            if doc["confirmed"] is not True or doc["backup_confirmed"] is not True:
                raise ValueError("Explicit confirmation and backup acknowledgement required")
            age = time.monotonic() - p.prepared_at
            if age > PREPARE_LIFETIME:
                raise ValueError("Confirmation expired; read and prepare again")
            old_now = self.reader()
            old_expected = p.old_clock + timedelta(seconds=age)
            if abs((old_now - old_expected).total_seconds()) > 3:
                raise RuntimeError("Device clock changed since preview; no command sent")

            if p.source == "phone":
                assert p.phone_epoch_ms is not None
                corrected_ms = p.phone_epoch_ms + int(age * 1000)
                target = baghdad_naive_from_epoch_ms(corrected_ms)
            else:
                target = p.proposed

            # Deliberately allow backward AND forward adjustment.
            before_send = time.monotonic()
            sent = False
            write_error = None
            try:
                sent = True
                self.setter(target)   # ONE SDK SET_TIME attempt; NO retry.
            except Exception as exc:
                write_error = type(exc).__name__

            # Earlier iFace 950 testing showed an immediate same-session read
            # can be stale. Verify only after a fresh connection/short delay.
            time.sleep(0.8)
            checks = []
            for idx in range(2):
                if idx:
                    time.sleep(0.5)
                try:
                    current = self.reader()  # fresh SDK connection per read
                    expected = target + timedelta(seconds=time.monotonic() - before_send)
                    delta = (current - expected).total_seconds()
                    checks.append({"time": current.strftime("%Y-%m-%dT%H:%M:%S"),
                                   "error_seconds": round(delta, 2)})
                except Exception as exc:
                    checks.append({"error": type(exc).__name__})

            verified = (write_error is None and len(checks) == 2
                        and all("error_seconds" in c and
                                abs(c["error_seconds"]) <= VERIFY_TOLERANCE
                                for c in checks))
            # Operational audit is intentionally limited to clock deltas only;
            # no employee IDs, biometrics or attendance records are read.
            drift = (target - old_now).total_seconds()
            print(f"CLOCK_CHANGE source={p.source} delta_seconds={drift:.0f} "
                  f"sent={sent} verified={verified} write_error={write_error}",
                  flush=True)
            return {
                "ok": True,
                "status": "VERIFIED" if verified else "UNVERIFIED",
                "source": p.source,
                "requested_time": target.strftime("%Y-%m-%dT%H:%M:%S"),
                "offset_seconds": int(round(drift)),
                "checks": checks,
                "write_error": write_error,
            }


    def quick(self, doc: dict) -> dict:
        """One paired-phone action, one SDK command, one independent verification.

        No repeated confirmation dialogues and no auto-retry on ambiguous ACK.
        """
        with self.lock:
            if not self.enable_write:
                raise PermissionError("Clock writes not enabled")
            if not isinstance(doc, dict) or set(doc) != {"id", "client_epoch_ms"}:
                raise ValueError("Invalid shortcut invocation")
            now = time.monotonic()
            if self.last_quick and now - self.last_quick < 8.0:
                raise ValueError("Wait before another clock action")
            self.last_quick = now
            item = next((x for x in self.shortcuts.list()
                         if x["id"] == doc["id"]), None)
            if item is None:
                raise ValueError("Unknown shortcut")
            old = self.reader()
            # The clicked phone epoch is an instant, not an offset cached at page load.
            client_epoch = doc["client_epoch_ms"]
            if item["kind"] == "phone":
                proposed = baghdad_naive_from_epoch_ms(client_epoch)
            else:
                proposed = target_time(item, old, old)
            delta = (proposed - old).total_seconds()
            # Large shifts are dangerous to production attendance timelines.
            # Use the existing manual prepare/confirm flow for >24h corrections.
            if abs(delta) > 86400:
                raise ValueError("Large time change requires manual confirmation")
            before = time.monotonic()
            write_error = None
            try:
                self.setter(proposed)
            except Exception as exc:
                write_error = type(exc).__name__
            time.sleep(0.8)
            try:
                observed = self.reader()  # fresh connection, never same-session ACK
                expected = proposed + timedelta(seconds=time.monotonic() - before)
                error_seconds = round((observed - expected).total_seconds(), 2)
                verified = write_error is None and abs(error_seconds) <= VERIFY_TOLERANCE
                result_time = observed.strftime("%Y-%m-%dT%H:%M:%S")
            except Exception:
                error_seconds = None
                verified = False
                result_time = None
            print("QUICK_CLOCK_CHANGE id=%s delta_seconds=%d verified=%s write_error=%s" %
                  (item["id"], int(round(delta)), verified, write_error), flush=True)
            return {
                "ok": True, "status": "VERIFIED" if verified else "UNVERIFIED",
                "id": item["id"], "name": item["name"],
                "requested_time": proposed.strftime("%Y-%m-%dT%H:%M:%S"),
                "result_time": result_time, "error_seconds": error_seconds,
                "write_error": write_error,
            }


def build_live_page(csrf_token: str, enable_write: bool) -> bytes:
    html = dashboard_html()
    html = html.replace("نسخة M2 تجريبية: قراءة حقيقية ومعاينة التصحيح فقط. <b>لا تحتوي أي أمر لتغيير الساعة.</b>",
                        "بوابة الماك عبر HTTPS: قراءة ساعة البصمة والتحكم المصرّح به.")
    html = html.replace("⚠️ هذه نسخة DRY RUN: لا يوجد زر تطبيق، ولا API لضبط الساعة. تصحيح الوقت للخلف والأمام سيكون متاحاً بعد اختبار الجهاز وحماية عملية التنفيذ. تحقق من ساعة الهاتف؛ قد تكون خاطئة.",
                        "تأكد من صحة وقت الهاتف أو التاريخ اليدوي، ومن عدم وجود بصمات حضور أثناء التصحيح.")
    banner = ("التحكم الفعلي مفعّل (بعد الموافقة)" if enable_write
              else "قراءة حقيقية فقط — تعديل الساعة غير مفعّل")
    html = html.replace("<header>", '<header><p class="note">'
                        + banner + '</p>', 1)
    if enable_write:
        form = """
<section class="card">
<h2>ضبط ساعة جهاز البصمة الحقيقي</h2>
<p class="small">اقرأ الساعة أولاً، اختر مزامنة الهاتف أو الإدخال اليدوي، ثم اطلب التأكيد.</p>
<button id="livePrepare" class="primary" type="button">تحضير تصحيح فعلي</button>
<div id="liveConfirm" hidden>
<p>الوقت السابق: <b id="oldClock"></b></p>
<p>الوقت المقترح: <b id="newClock"></b></p>
<p>الفرق: <b id="shiftClock"></b></p>
<p class="note" id="liveWarning"></p>
<label><input id="backupAck" type="checkbox" style="display:inline;width:auto">
تحققت من الوقت الصحيح، والنسخة الاحتياطية، وعدم وجود بصمات حالياً</label>
<button id="liveApply" class="primary" type="button">تنفيذ التصحيح على جهاز البصمة</button>
</div>
<p id="liveStatus" class="small"></p>
</section>"""
        html = html.replace("</main>",form+"</main>",1)
        script = r"""
<script>
(function(){
const csrf=CSRF_TOKEN_PLACEHOLDER;
let nonce=null;
const e=id=>document.getElementById(id);
async function post(path, body){
  const res=await fetch(path,{method:'POST',headers:{
    'Content-Type':'application/json','X-CSRF-Token':csrf
  },body:JSON.stringify(body),cache:'no-store',credentials:'same-origin'});
  const answer=await res.json();
  if(!res.ok)throw Error(answer.error||'Request rejected');
  return answer;
}
e('livePrepare').onclick=async()=>{
  e('liveConfirm').hidden=true;nonce=null;
  if(!fresh()){e('liveStatus').textContent='اقرأ ساعة الجهاز أولاً';return;}
  const source=mode;
  let body={source};
  try{
    if(source==='manual'){
      const civil=e('manual').value;
      const epoch=parseBaghdadManual(civil);
      body.local_datetime=formatCivil(epoch).replace(' ','T');
    }else{
      body.client_epoch_ms=Date.now();
    }
    const v=await post('/api/prepare',body);
    nonce=v.nonce;
    e('oldClock').textContent=v.old_time.replace('T',' ');
    e('newClock').textContent=v.proposed_time.replace('T',' ');
    e('shiftClock').textContent=formatDiff(v.offset_seconds*1000);
    e('liveWarning').textContent=(v.backward
      ?'تحذير: هذا التغيير يرجع ساعة البصمة للخلف وقد تتداخل أوقات الحضور الجديدة مع السابقة. '
      :'')+'سيُرسل أمر تعديل واحد فقط ثم تُقرأ الساعة مرتين للتحقق.';
    e('backupAck').checked=false;
    e('liveConfirm').hidden=false;
    e('liveStatus').textContent='التأكيد صالح لمدة '+v.expires_in_seconds+' ثانية.';
  }catch(ex){e('liveStatus').textContent='فشل التحضير: '+ex.message;}
};
e('liveApply').onclick=async()=>{
  if(!nonce||!e('backupAck').checked){
    e('liveStatus').textContent='راجع المعلومات وفعّل مربع التأكيد أولاً';return;
  }
  if(!window.confirm('تأكيد نهائي: تغيير ساعة البصمة الحقيقية الآن؟'))return;
  const token=nonce;nonce=null;e('liveConfirm').hidden=true;
  e('liveStatus').textContent='أُرسل طلب التصحيح؛ جارٍ التحقق بعد إعادة الاتصال...';
  try{
    const r=await post('/api/apply',{nonce:token,confirmed:true,backup_confirmed:true});
    e('liveStatus').textContent=r.status==='VERIFIED'
       ?'نجحت المزامنة وتأكدت قراءتان جديدتان: '+r.requested_time
       :'تعذر تأكيد النتيجة (UNVERIFIED). افحص شاشة البصمة قبل المحاولة مرة أخرى.';
    measuredOffsetMs=null;measuredAtMs=0;
    e('device').textContent='—';e('delta').textContent='—';
  }catch(ex){e('liveStatus').textContent='لم يكتمل الطلب: '+ex.message+
    '. افحص ساعة البصمة قبل تكرار الأمر.';}
};
})();
</script>
""".replace("CSRF_TOKEN_PLACEHOLDER",json.dumps(csrf_token))
        html = html.replace("</body>",script+"</body>",1)
    html = html.replace("</main>", shortcut_panel(csrf_token, enable_write) + "</main>", 1)
    return html.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server: Gateway

    def log_message(self, format: str, *args: object) -> None:
        print("HTTPS_REQUEST", self.command, urlsplit(self.path).path, flush=True)

    def reply(self, code: int, obj: dict) -> None:
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.security_headers()
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; "
                         "connect-src 'self'; base-uri 'none'; form-action 'self'")

    def authorized(self) -> bool:
        authorization = self.headers.get("Authorization","")
        cookie = get_cookie(self.headers.get("Cookie", ""))
        if self.server.pairing.authorized(cookie):
            return True
        if not self.server.allow_basic:
            return False
        if not authorization.startswith("Basic "):
            return False
        try:
            raw = base64.b64decode(authorization[6:],validate=True)
            user, password = raw.decode("utf-8").split(":",1)
        except Exception:
            return False
        return user=="operator" and secrets.compare_digest(password,self.server.password)

    def require_auth(self) -> bool:
        if self.authorized():return True
        self.send_response(401)
        self.security_headers()
        self.send_header("WWW-Authenticate",'Basic realm="ZKTeco Mac Clock Control"')
        self.send_header("Content-Length","0")
        self.end_headers()
        return False

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/" and not self.authorized() and self.server.pairing.allow_new:
            page = """<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>إقران الهاتف</title></head>
<body style='font:18px system-ui;background:#152438;color:white;padding:20px;max-width:420px;margin:auto'>
<h2>إقران هذا الهاتف مرة واحدة</h2>
<p>أدخل الرمز المعروض على Terminal الماك. Safari راح يتذكر الهاتف لمدة 30 يوم بدون كلمة مرور يومية.</p>
<input id='pairCode' inputmode='numeric' maxlength='8' placeholder='رمز الإقران'
 style='padding:14px;font:inherit;width:90%'>
<button id='pair' style='display:block;margin:14px 0;padding:14px;font:inherit'>إقران الهاتف</button>
<p id='status'></p><script>
document.getElementById('pair').onclick=async()=>{
 const code=document.getElementById('pairCode').value;
 try{
  const r=await fetch('/api/pair',{method:'POST',
    headers:{'Content-Type':'application/json'},credentials:'same-origin',
    body:JSON.stringify({code})});
  const j=await r.json();
  if(!r.ok)throw Error(j.error||'Pairing refused');
  location.replace('/');
 }catch(e){document.getElementById('status').textContent=e.message;}
};
</script></body></html>""".encode("utf-8")
            self.send_response(200)
            self.security_headers()
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return
        if not self.require_auth():return
        if path=="/":
            payload=self.server.page
            self.send_response(200)
            self.security_headers()
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length",str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path=="/api/shortcuts":
            try:
                self.reply(200,{"ok":True,"items":self.server.shortcuts.list()})
            except Exception as exc:
                self.reply(503,{"ok":False,"error":"Cannot read shortcuts: "+
                                type(exc).__name__})
            return
        if path=="/api/read":
            try:
                start=time.monotonic()
                t=self.server.read_once()
                self.reply(200,{"ok":True,"device_time":t.strftime("%Y-%m-%dT%H:%M:%S"),
                                "duration_ms":int((time.monotonic()-start)*1000)})
            except Exception as exc:
                self.reply(503,{"ok":False,"error":"Device read failed: "+type(exc).__name__})
            return
        self.reply(404,{"ok":False,"error":"Not found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        # Pairing is the only unauthenticated POST. One-time 8-digit code is
        # shown on Mac console, 5 failed tries maximum, HTTPS mandatory.
        if path == "/api/pair":
            host=self.headers.get("Host","")
            origin=self.headers.get("Origin","")
            if not host or origin != "https://"+host:
                self.reply(403,{"ok":False,"error":"Pairing origin rejected"});return
            length=self.headers.get("Content-Length","")
            if (self.headers.get("Content-Type","").split(";")[0].strip()!="application/json"
                or not length.isdigit() or not 0 < int(length) <= 128):
                self.reply(400,{"ok":False,"error":"Invalid pairing request"});return
            try:
                doc=json.loads(self.rfile.read(int(length)))
                if not isinstance(doc,dict) or set(doc)!={"code"}:
                    raise ValueError("Invalid pairing shape")
                token=self.server.pairing.pair(doc["code"])
            except (ValueError, OSError):
                self.reply(403,{"ok":False,"error":"Invalid/expired pairing code"});return
            payload=b'{"ok":true}'
            self.send_response(200)
            self.security_headers()
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(payload)))
            self.send_header("Set-Cookie",cookie_header(token))
            self.end_headers()
            self.wfile.write(payload)
            return

        if not self.require_auth():return
        if path not in ("/api/shortcuts","/api/quick","/api/prepare","/api/apply"):
            self.reply(404,{"ok":False,"error":"Unknown operation"});return
        if path != "/api/shortcuts" and not self.server.enable_write:
            self.reply(404,{"ok":False,"error":"Live write unavailable"});return
        host=self.headers.get("Host","")
        origin=self.headers.get("Origin","")
        if not host or origin != "https://"+host or \
           not secrets.compare_digest(self.headers.get("X-CSRF-Token",""),
                                      self.server.csrf_token):
            self.reply(403,{"ok":False,"error":"Origin/CSRF check failed"});return
        if self.headers.get("Content-Type","").split(";")[0].strip() != "application/json":
            self.reply(415,{"ok":False,"error":"Expected JSON"});return
        length=self.headers.get("Content-Length","")
        if not length.isdigit() or not 0 < int(length) <= MAX_BODY:
            # Shortcut catalogs are limited to 12 entries; separate 4 KiB cap.
            if path != "/api/shortcuts" or not length.isdigit() or not 0 < int(length) <= 4096:
                self.reply(413,{"ok":False,"error":"Invalid body size"});return
        try:
            doc=json.loads(self.rfile.read(int(length)))
            if not isinstance(doc,dict):raise ValueError("JSON object required")
            if path=="/api/shortcuts":
                if set(doc)!={"items"}:raise ValueError("Invalid shortcut save")
                self.server.shortcuts.save(doc["items"])
                result={"ok":True,"items":self.server.shortcuts.list()}
            elif path=="/api/quick":
                result=self.server.quick(doc)
            elif path=="/api/prepare":
                result=self.server.prepare(doc)
            else:
                result=self.server.apply(doc)
            self.reply(200,result)
        except PermissionError:
            self.reply(403,{"ok":False,"error":"Write disabled"})
        except ValueError as exc:
            message = (str(exc) if path in ("/api/quick", "/api/shortcuts")
                       else "Invalid or expired request")
            self.reply(400,{"ok":False,"error":message})
        except (OverflowError,OSError):
            self.reply(400,{"ok":False,"error":"Invalid or expired request"})
        except Exception as exc:
            self.reply(503,{"ok":False,"error":"Operation not confirmed: "+
                            type(exc).__name__})


def main() -> None:
    parser=argparse.ArgumentParser(description="Mac HTTPS clock control gateway")
    parser.add_argument("--bind",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8766)
    parser.add_argument("--device-host",default="10.1.65.2")
    parser.add_argument("--device-port",type=int,default=4370)
    parser.add_argument("--cert",required=True,help="Local TLS certificate PEM")
    parser.add_argument("--key",required=True,help="Local TLS private key PEM")
    parser.add_argument("--paired-only",action="store_true",
                        help="Disable rotating Basic password; trust paired Safari only")
    parser.add_argument("--enable-pairing",action="store_true",
                        help="Show one-time phone pairing code for 5 minutes")
    parser.add_argument("--enable-write",action="store_true",
                        help="Explicitly permit live SET_TIME after authenticated confirmation")
    args=parser.parse_args()
    password=secrets.token_urlsafe(22)
    gateway=Gateway((args.bind,args.port),device_host=args.device_host,
                    device_port=args.device_port,password=password,
                    enable_write=args.enable_write,
                    allow_pairing=args.enable_pairing,
                    allow_basic=not args.paired_only)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=args.cert,keyfile=args.key)
    gateway.socket=context.wrap_socket(gateway.socket,server_side=True)
    print("Mac HTTPS ZKTeco gateway",flush=True)
    print("Mode:", "LIVE CLOCK WRITES ENABLED" if args.enable_write
          else "READ ONLY",flush=True)
    print(f"URL: https://{args.bind}:{args.port}/",flush=True)
    if gateway.pairing.code:
        print("PAIR THIS PHONE ONLY ONCE (valid 5 minutes):",gateway.pairing.code,
              flush=True)
    if args.paired_only:
        print("AUTH: paired iPhone sessions only; no rotating login password.")
    else:
        print("Login user (fallback): operator")
        print("Temporary password:",password,flush=True)
    print("Do not publish or share this password. Stop with Ctrl+C.",flush=True)
    try:
        gateway.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        gateway.server_close()


if __name__=="__main__":
    main()
