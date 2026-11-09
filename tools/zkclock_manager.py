"""ZK CLOCK Manager v0.3: private read-only ZKTeco archive, Mac + optional iPhone HTTPS.

Only reads device records/users using pyzk; never writes to the device or fabricates punches.
The application database is a COPY of device data for search and historical analysis.
"""
import argparse
import base64
import collections
from datetime import date as date_cls, datetime, timezone
import getpass
import hashlib
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import ssl
from urllib.parse import parse_qs, urlsplit, urlencode
import time as time_module

from zkclock_manager_reports import (employee_directory, employee_month,
                                     render_employee_page, render_directory_page)

DEFAULT_DB = Path('local/zkclock_manager.sqlite3')
DEFAULT_DEVICE = '10.1.65.2'
NEAR_SECONDS = 10


def open_db(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    db = sqlite3.connect(str(path), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=30000')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS device_punches (
            source_key TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            occurred TEXT NOT NULL,
            uid TEXT NOT NULL,
            status INTEGER NOT NULL,
            punch INTEGER NOT NULL,
            occurrence INTEGER NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_punches_date ON device_punches(occurred DESC);
        CREATE INDEX IF NOT EXISTS ix_punches_user_date ON device_punches(user_id, occurred DESC);
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imported_at TEXT NOT NULL,
            device_host TEXT NOT NULL,
            record_count INTEGER NOT NULL,
            inserted_count INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS device_users (
            user_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            last_seen TEXT NOT NULL
        );
    ''')
    db.commit()
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return db


def archive_read(db, logs, *, host, min_records=1, time_now=None):
    """Archive a complete read, preserving identical events with occurrence indices."""
    if logs is None:
        raise ValueError('Device returned no attendance dataset')
    if len(logs) < min_records:
        raise ValueError(f'Incomplete or smaller read: {len(logs)} < minimum {min_records}')
    if not re.fullmatch(r'[0-9A-Za-z.:-]{1,100}', host):
        raise ValueError('Unexpected device hostname')
    when = time_now or datetime.now(timezone.utc).isoformat()
    counts = collections.defaultdict(int)
    prepared = []
    for item in logs:
        if not isinstance(item.timestamp, datetime):
            raise ValueError('Device returned malformed timestamp')
        user_id, uid = str(item.user_id), str(item.uid)
        stamp = item.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        status, punch = int(item.status), int(item.punch)
        attrs = (host, uid, user_id, stamp, status, punch)
        counts[attrs] += 1
        occurrence = counts[attrs]
        raw = json.dumps((*attrs, occurrence), ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
        prepared.append((hashlib.sha256(raw).hexdigest(), user_id, stamp, uid,
                         status, punch, occurrence, when, when))
    before = db.execute('SELECT COUNT(*) FROM device_punches').fetchone()[0]
    with db:
        db.executemany('''INSERT INTO device_punches
            (source_key,user_id,occurred,uid,status,punch,occurrence,first_seen,last_seen)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_key) DO UPDATE SET last_seen=excluded.last_seen''', prepared)
        after = db.execute('SELECT COUNT(*) FROM device_punches').fetchone()[0]
        inserted = after - before
        db.execute('''INSERT INTO imports
            (imported_at,device_host,record_count,inserted_count) VALUES (?,?,?,?)''',
                   (when, host, len(logs), inserted))
    return {'imported_at': when, 'device_host': host, 'record_count': len(logs),
            'new_records': inserted, 'archived_total': after}


def archive_users(db, users, *, time_now=None):
    """Names/IDs read from device, no passwords, templates or access credentials."""
    when = time_now or datetime.now(timezone.utc).isoformat()
    prepared = []
    for user in users or []:
        uid = str(user.user_id)
        if not uid or not re.fullmatch(r'[0-9]{1,32}', uid):
            continue
        prepared.append((uid, str(user.name or '').strip()[:120], when))
    with db:
        db.executemany('''INSERT INTO device_users(user_id,display_name,last_seen)
            VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE
            SET display_name=excluded.display_name,last_seen=excluded.last_seen''', prepared)
    return len(prepared)


def validate_filters(user_id='', date='', date_from='', date_to=''):
    if user_id and not re.fullmatch(r'[0-9A-Za-z\u0600-\u06FF .-]{1,120}', user_id):
        raise ValueError('Invalid employee filter')
    bounds = [date, date_from, date_to]
    for value in bounds:
        if not value:
            continue
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('Date must be YYYY-MM-DD')
        if date_cls.fromisoformat(value).isoformat() != value:
            raise ValueError('Invalid calendar date')
    if date_from and date_to and date_from > date_to:
        raise ValueError('Start date exceeds end date')


def build_where(*, user_id='', date='', date_from='', date_to=''):
    validate_filters(user_id, date, date_from, date_to)
    clauses, args = [], []
    if user_id:
        if user_id.isascii() and user_id.isdecimal():
            clauses.append('p.user_id=?')
            args.append(user_id)
        else:
            clauses.append('p.user_id IN (SELECT user_id FROM device_users WHERE display_name LIKE ?)')
            args.append('%' + user_id + '%')
    if date:
        date_from, date_to = date, date
    if date_from:
        clauses.append('p.occurred >= ?')
        args.append(date_from + ' 00:00:00')
    if date_to:
        clauses.append('p.occurred <= ?')
        args.append(date_to + ' 23:59:59')
    return (' WHERE ' + ' AND '.join(clauses)) if clauses else '', args


def fetch_punches(db, *, user_id='', date='', date_from='', date_to='', limit=100):
    where, args = build_where(user_id=user_id, date=date,
                              date_from=date_from, date_to=date_to)
    limit = max(1, min(int(limit), 200))
    return [dict(r) for r in db.execute('''SELECT p.user_id,p.occurred,p.uid,p.status,
                 p.punch,p.occurrence,p.first_seen,p.last_seen,
                 COALESCE(u.display_name,'') AS display_name
                 FROM device_punches p LEFT JOIN device_users u ON p.user_id=u.user_id'''
                 + where + ' ORDER BY p.occurred DESC,p.source_key LIMIT ?', (*args, limit))]


def count_matching(db, **filters):
    where, args = build_where(**filters)
    return db.execute('SELECT COUNT(*) FROM device_punches p' + where, args).fetchone()[0]


def daily_summary(db, *, user_id='', date='', date_from='', date_to='', limit=50):
    """Daily first/last punches + near repeats, without inferring IN/OUT."""
    where, args = build_where(user_id=user_id, date=date,
                              date_from=date_from, date_to=date_to)
    limit = max(1, min(int(limit), 100))
    days = [dict(r) for r in db.execute('''
        SELECT p.user_id,substr(p.occurred,1,10) AS day,
               MIN(p.occurred) AS first_punch,MAX(p.occurred) AS last_punch,
               COUNT(*) AS total_punches,COALESCE(MAX(u.display_name),'') AS display_name
        FROM device_punches p LEFT JOIN device_users u ON u.user_id=p.user_id
        ''' + where + ''' GROUP BY p.user_id,substr(p.occurred,1,10)
        ORDER BY day DESC,p.user_id LIMIT ?''', (*args, limit))]
    for row in days:
        stamps = [r[0] for r in db.execute('''SELECT occurred FROM device_punches
            WHERE user_id=? AND occurred>=? AND occurred<=? ORDER BY occurred''',
            (row['user_id'], row['day'] + ' 00:00:00', row['day'] + ' 23:59:59'))]
        near = 0
        for left, right in zip(stamps, stamps[1:]):
            if (datetime.strptime(right, '%Y-%m-%d %H:%M:%S') -
                datetime.strptime(left, '%Y-%m-%d %H:%M:%S')).total_seconds() <= NEAR_SECONDS:
                near += 1
        row['near_repeats'] = near
    return days


def summary(db):
    last = db.execute('''SELECT imported_at,device_host,record_count,inserted_count
        FROM imports ORDER BY id DESC LIMIT 1''').fetchone()
    return {
        'archived_records': db.execute('SELECT COUNT(*) FROM device_punches').fetchone()[0],
        'known_users': db.execute('SELECT COUNT(*) FROM device_users').fetchone()[0],
        'last_import': dict(last) if last else None,
    }


def read_device_and_archive(db_path, *, host=DEFAULT_DEVICE, port=4370,
                            min_records=37812):
    """Only pyzk device reads. Never disable or set device, change clocks or logs."""
    from zk import ZK
    conn = None
    try:
        conn = ZK(host, port=port, timeout=15, password=0,
                  force_udp=False, ommit_ping=True).connect()
        logs = conn.get_attendance()
        # Optional user metadata read only. Failure does not invalidate punch read.
        try:
            users = conn.get_users()
        except Exception:
            users = []
    finally:
        if conn is not None:
            conn.disconnect()
    with open_db(db_path) as db:
        result = archive_read(db, logs, host=host, min_records=min_records)
        result['user_names_read'] = archive_users(db, users)
    return result


CSS = '''
:root{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text",system-ui,sans-serif;color-scheme:dark}
*{box-sizing:border-box}body{background:#0d1420;color:#eef2fa;margin:0;line-height:1.5}
main{max-width:1190px;margin:auto;padding:24px 18px 48px}h1{font-size:clamp(1.4rem,2.4vw,2rem);margin:.1em 0}
h2{font-size:1.13rem;margin:0 0 15px}p,.muted{color:#aab8ce}.top{display:flex;justify-content:space-between;align-items:center;gap:15px;flex-wrap:wrap;margin:0 0 22px}
.top p{margin:.2em 0}section{background:#152237;border:1px solid #2b3c54;border-radius:16px;padding:18px;margin:15px 0}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.stat{background:#18283f;border:1px solid #2a3b52;border-radius:14px;padding:15px}
.stat strong{display:block;font-size:clamp(1.25rem,2vw,1.7rem);color:#fff;font-variant-numeric:tabular-nums}.stat small{color:#aab8ce}
.form{display:flex;gap:10px;flex-wrap:wrap;align-items:end}.field{display:flex;flex-direction:column;gap:5px;flex:1 1 170px}
label{color:#d2dded;font-size:.9rem}input,button{font:inherit;min-height:43px;padding:9px 12px;border-radius:10px;border:1px solid #58708d;background:#0c192b;color:#f7f9ff}
input{width:100%}input:focus,button:focus{outline:2px solid #7aa4fa;outline-offset:2px}button{cursor:pointer;background:#355b93;border-color:#507db5;font-weight:650}
button:hover{background:#416dae}.secondary{background:#253651;border-color:#475c7b}button[disabled]{opacity:.5;cursor:not-allowed}
.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:.92rem}th,td{padding:10px 9px;text-align:right;border-bottom:1px solid #354861;white-space:nowrap}
th{color:#aebfda;font-weight:650}td{font-variant-numeric:tabular-nums}tr:hover td{background:#1c3049} a{color:#accfff;text-underline-offset:3px}.count{color:#c5d8f7}
.tag{background:#2d4060;color:#d8e6ff;border-radius:20px;padding:3px 10px;font-size:.8rem;display:inline-block}
.warn{color:#ffe0a0}.notice{background:#1b3351;border-radius:10px;padding:10px 14px;margin-bottom:16px}
.foot{font-size:.82rem;color:#b3c3d9;padding-top:7px}.grouphead{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}
.actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.small{font-size:.88rem}.ltr{direction:ltr;unicode-bidi:isolate;display:inline-block}
@media(max-width:640px){main{padding:15px 11px 35px}.stats{grid-template-columns:repeat(2,1fr)}.stat:last-child{grid-column:span 2}.form{display:grid;grid-template-columns:1fr 1fr}.field:first-child{grid-column:span 2}
.form button{grid-column:span 2}section{padding:13px}table{font-size:.82rem}td,th{padding:9px 7px}}
'''


def _h(value):
    return html.escape(str(value), quote=True)


def _as_local_timestamp(stamp):
    try:
        dt = datetime.fromisoformat(stamp)
        return dt.astimezone().strftime('%Y-%m-%d %H:%M:%S') if dt.tzinfo else stamp
    except (ValueError, TypeError):
        return stamp


def render_page(s, punches, days, match_count, *, user='', date_from='', date_to='',
                csrf='', web_sync=False, notice=''):
    last = s['last_import']
    last_str = _as_local_timestamp(last['imported_at']) if last else 'لم تتم مزامنة بعد'
    last_host = last['device_host'] if last else '—'
    last_new = last['inserted_count'] if last else 0
    daily_rows = ''.join('''<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td>
       <td>{}</td><td>{}</td><td>{}</td></tr>'''.format(
        '<a href="/employee?{}">{}</a>'.format(urlencode({'user': r['user_id']}), _h(r['user_id'])), _h(r['display_name'] or '—'), _h(r['day']),
        _h(r['first_punch'][11:]), _h(r['last_punch'][11:]),
        _h(r['total_punches']), _h(r['near_repeats'])) for r in days)
    raw_rows = ''.join('''<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td>
       <td>{}</td><td>{}</td></tr>'''.format(
        '<a href="/employee?{}">{}</a>'.format(urlencode({'user': r['user_id']}), _h(r['user_id'])), _h(r['display_name'] or '—'), _h(r['occurred']),
        _h(r['status']), _h(r['punch']), _h(r['occurrence'])) for r in punches)
    if not daily_rows:
        daily_rows = '<tr><td colspan="7">لا توجد حركات مطابقة</td></tr>'
    if not raw_rows:
        raw_rows = '<tr><td colspan="6">لا توجد سجلات مطابقة</td></tr>'
    sync_form = ('''<form method="post" action="/sync"><input type="hidden"
        name="csrf" value="{}"><button type="submit" class="secondary">مزامنة من الجهاز</button></form>'''.format(_h(csrf))
                 if web_sync else '<span class="muted small">المزامنة بالأمر من Terminal</span>')
    message = '<div class="notice">{}</div>'.format(_h(notice)) if notice else ''
    return '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#0d1420"><title>ZK CLOCK Manager</title>
<style>{css}</style></head><body><main>
<div class="top"><div><h1>ZK CLOCK Manager</h1>
<p>أرشيف الجهاز الحقيقي · نسخة تجريبية للقراءة فقط</p><p><a href="/employees">دليل الموظفين وصفحاتهم الشهرية</a></p></div><span class="tag">بيانات أصلية</span></div>
{notice}<div class="stats"><div class="stat"><small>كل السجلات المؤرشفة</small><strong>{count}</strong></div>
<div class="stat"><small>الموظفون المعروفون</small><strong>{users}</strong></div>
<div class="stat"><small>سجلات البحث الحالي</small><strong>{matched}</strong></div></div>
<section><div class="grouphead"><div><h2>آخر مزامنة</h2><p class="small">{last} · الجهاز <span class="ltr">{host}</span> · إضافات جديدة: {new}</p></div>
<div class="actions">{sync_form}</div></div></section>
<section><h2>بحث السجلات</h2><form class="form" method="get" action="/">
<div class="field"><label for="user">رقم الموظف أو اسمه</label><input id="user" name="user" value="{user}" placeholder="1001 أو اسم الموظف"></div>
<div class="field"><label for="from">من تاريخ</label><input id="from" name="from" type="date" value="{from_date}"></div>
<div class="field"><label for="to">إلى تاريخ</label><input id="to" name="to" type="date" value="{to_date}"></div>
<button type="submit">بحث</button></form></section>
<section><div class="grouphead"><h2>الملخص اليومي</h2><span class="muted small">أول حركة وآخر حركة لكل يوم · أحدث 50 يوم/موظف</span></div>
<div class="scroll"><table><thead><tr><th>ID</th><th>الاسم</th><th>التاريخ</th><th>الأولى</th><th>الأخيرة</th><th>عدد الحركات</th><th>متقاربة ≤10 ثوانٍ</th></tr></thead>
<tbody>{daily_rows}</tbody></table></div></section>
<section><div class="grouphead"><h2>الحركات الأصلية</h2><span class="muted small">أحدث 100 سجل مطابق</span></div>
<div class="scroll"><table><thead><tr><th>ID</th><th>الاسم</th><th>التوقيت</th><th>Status</th><th>Punch</th><th>تكرار مطابق</th></tr></thead>
<tbody>{raw_rows}</tbody></table></div></section>
<p class="foot">الأرشيف نسخة مقروءة من الجهاز فقط. لا يسمح بإضافة أو تعديل أو حذف سجل أصلي. الحركات المتقاربة معروضة للتحقق، ولم تُحذف. «أول/آخر حركة» ليست حكماً تلقائياً بالحضور أو الانصراف.</p>
</main></body></html>'''.format(css=CSS, notice=message, count=f"{s['archived_records']:,}", users=s['known_users'],
        matched=f'{match_count:,}', last=_h(last_str), host=_h(last_host), new=last_new,
        sync_form=sync_form, user=_h(user), from_date=_h(date_from), to_date=_h(date_to),
        daily_rows=daily_rows, raw_rows=raw_rows)


def build_server(path, *, bind='127.0.0.1', port=8768, phone_password=None,
                 allow_web_sync=True, device_host=DEFAULT_DEVICE):
    """Create private HTTP server, return it to tests or run via serve()."""
    path = Path(path)
    if not path.exists():
        raise RuntimeError('Database missing. Run sync first.')
    if bind != '127.0.0.1' and not phone_password:
        raise ValueError('LAN access requires a password and HTTPS')
    # Upgrade an existing v0.1 SQLite archive without touching its raw events.
    with open_db(path):
        pass
    token = secrets.token_urlsafe(32)
    allowed_host = {f'{bind}:{port}'}
    if bind == '127.0.0.1':
        allowed_host.add(f'localhost:{port}')

    class Handler(BaseHTTPRequestHandler):
        def _validate(self):
            if self.headers.get('Host') not in allowed_host:
                self.send_error(403, 'Unexpected Host')
                return False
            if phone_password is not None:
                auth = self.headers.get('Authorization', '')
                encoded = 'Basic ' + base64.b64encode(
                    ('zkclock:' + phone_password).encode('utf-8')).decode('ascii')
                if not secrets.compare_digest(auth, encoded):
                    self.send_response(401)
                    self.send_header('WWW-Authenticate', 'Basic realm="ZK CLOCK Manager"')
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    return False
            return True

        def _respond(self, code, body, content_type='text/html; charset=utf-8', *, location=None):
            if isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(code)
            if location is not None:
                self.send_header('Location', location)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy',
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                "frame-ancestors 'none'; base-uri 'none'")
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._validate():
                return
            url = urlsplit(self.path)
            allowed = ('/', '/api/summary', '/api/records', '/api/days',
                       '/employees', '/employee', '/api/employees', '/api/employee')
            if url.path not in allowed:
                return self._respond(404, 'Not found', 'text/plain; charset=utf-8')
            q = parse_qs(url.query)
            if url.path in ('/employees', '/employee', '/api/employees', '/api/employee'):
                try:
                    with sqlite3.connect(f'file:{path.resolve()}?mode=ro', uri=True) as db:
                        db.row_factory = sqlite3.Row
                        if url.path in ('/employees', '/api/employees'):
                            search = q.get('search', [''])[0].strip()
                            result = employee_directory(db, search=search)
                        else:
                            result = employee_month(db,
                                q.get('user', [''])[0].strip(),
                                month=q.get('month', [''])[0].strip() or None,
                                morning=q.get('morning', ['08:30'])[0].strip(),
                                evening=q.get('evening', ['14:45'])[0].strip())
                except (ValueError, sqlite3.Error) as exc:
                    return self._respond(400, str(exc), 'text/plain; charset=utf-8')
                if url.path.startswith('/api/'):
                    return self._respond(200, json.dumps(result, ensure_ascii=False),
                                         'application/json; charset=utf-8')
                return self._respond(200, render_directory_page(result, search=search)
                                     if url.path == '/employees'
                                     else render_employee_page(result))
            user = q.get('user', [''])[0].strip()
            date = q.get('date', [''])[0]
            start = q.get('from', [''])[0]
            end = q.get('to', [''])[0]
            filt = dict(user_id=user, date=date, date_from=start, date_to=end)
            try:
                with sqlite3.connect(f'file:{path.resolve()}?mode=ro', uri=True) as db:
                    db.row_factory = sqlite3.Row
                    s = summary(db)
                    records = fetch_punches(db, **filt)
                    days = daily_summary(db, **filt)
                    n = count_matching(db, **filt)
            except (ValueError, sqlite3.Error) as exc:
                return self._respond(400, str(exc), 'text/plain; charset=utf-8')
            if url.path.startswith('/api/'):
                payload = {'/api/summary': s, '/api/records': records,
                           '/api/days': days}[url.path]
                return self._respond(200, json.dumps(payload, ensure_ascii=False),
                                     'application/json; charset=utf-8')
            notice = {'done': 'تمت المزامنة بنجاح.',
                      'failed': 'تعذرت المزامنة. راجع Terminal وتأكد من اتصال الجهاز.'}.get(
                          q.get('sync', [''])[0], '')
            page = render_page(s, records, days, n, user=user, date_from=start,
                               date_to=end, csrf=token, web_sync=allow_web_sync, notice=notice)
            self._respond(200, page)

        def do_POST(self):
            if not self._validate():
                return
            if urlsplit(self.path).path != '/sync' or not allow_web_sync:
                return self._respond(405, 'Not allowed', 'text/plain; charset=utf-8')
            scheme = 'https' if phone_password is not None else 'http'
            origin = self.headers.get('Origin')
            expected = f'{scheme}://{bind}:{port}'
            if origin and origin != expected and not (bind == '127.0.0.1' and
                  origin == f'http://localhost:{port}'):
                return self._respond(403, 'Origin rejected', 'text/plain; charset=utf-8')
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0 or length > 4096:
                    raise ValueError('Bad post size')
                form = parse_qs(self.rfile.read(length).decode('utf-8'))
                if form.get('csrf') != [token]:
                    return self._respond(403, 'CSRF rejected', 'text/plain; charset=utf-8')
            except (ValueError, UnicodeError):
                return self._respond(400, 'Bad POST', 'text/plain; charset=utf-8')
            try:
                with sqlite3.connect(f'file:{path.resolve()}?mode=ro', uri=True) as db:
                    minimum = max(1, summary(db)['last_import']['record_count'])
                read_device_and_archive(path, host=device_host, min_records=minimum)
                return self._respond(303, b'', location='/?sync=done')
            except Exception as exc:
                # Avoid including device records or private information in HTTP errors.
                print('READ-ONLY SYNC FAILED:', type(exc).__name__, flush=True)
                return self._respond(303, b'', location='/?sync=failed')

    server = ThreadingHTTPServer((bind, port), Handler)
    allowed_host.add(f'{bind}:{server.server_address[1]}')
    if bind == '127.0.0.1':
        allowed_host.add(f'localhost:{server.server_address[1]}')
    return server


def serve(path, port, *, bind='127.0.0.1', cert=None, key=None, phone_password=None,
          allow_web_sync=True, device_host=DEFAULT_DEVICE):
    if bind != '127.0.0.1':
        # Only explicit private/local IPs, never 0.0.0.0 or public Internet.
        address = ipaddress.ip_address(bind)
        lan_ranges = tuple(ipaddress.ip_network(x) for x in
                           ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
        if address.version != 4 or not any(address in n for n in lan_ranges):
            raise ValueError('Phone mode requires a specific private LAN IPv4 address')
        if not (cert and key and phone_password and len(phone_password) >= 12):
            raise ValueError('Phone mode requires --cert, --key and password >= 12 characters')
    elif phone_password:
        raise ValueError('Use serve-phone for protected LAN mode')
    server = build_server(path, bind=bind, port=port,
                          phone_password=phone_password, allow_web_sync=allow_web_sync,
                          device_host=device_host)
    if bind != '127.0.0.1':
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(str(cert), str(key))
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    url = f"{'https' if phone_password else 'http'}://{bind}:{port}/"
    print('ZK CLOCK Manager:', url, flush=True)
    server.serve_forever()


def watch_device(db_path, *, host=DEFAULT_DEVICE, port=4370,
                 min_records=37812, interval_minutes=30, max_reads=None,
                 reader=None, pause=None):
    """Opt-in foreground read-only synchronization; Ctrl+C exits.

    No background daemon, no device writes, and no silent retry within a read.
    Import failure is reported, then next interval can retry.
    """
    if interval_minutes < 10 or interval_minutes > 1440:
        raise ValueError('Interval must be 10–1440 minutes')
    if max_reads is not None and max_reads < 1:
        raise ValueError('max_reads must be positive')
    reader = reader or read_device_and_archive
    pause = pause or time_module.sleep
    # If an earlier device read counted more records than the caller's minimum,
    # never silently accept a smaller live dataset on the first polling cycle.
    if Path(db_path).exists():
        with sqlite3.connect(f'file:{Path(db_path).resolve()}?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            previous = summary(db)['last_import']
            if previous:
                min_records = max(min_records, previous['record_count'])
    iterations = 0
    while max_reads is None or iterations < max_reads:
        iterations += 1
        try:
            result = reader(db_path, host=host, port=port, min_records=min_records)
            print('READ-ONLY SYNC', json.dumps(result, ensure_ascii=False), flush=True)
            min_records = max(min_records, result.get('record_count', 0))
        except Exception as exc:
            print('READ-ONLY SYNC ERROR:', type(exc).__name__, str(exc), flush=True)
        if max_reads is None or iterations < max_reads:
            pause(interval_minutes * 60)


def backup_database(path):
    path = Path(path)
    if not path.exists():
        raise RuntimeError('Database missing')
    backup_path = path.with_name(path.stem + '_backup_' +
        datetime.now().strftime('%Y%m%d_%H%M%S_%f') + path.suffix)
    with sqlite3.connect(path) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)
    os.chmod(backup_path, 0o600)
    return backup_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=str(DEFAULT_DB))
    sub = parser.add_subparsers(dest='action', required=True)
    sync = sub.add_parser('sync', help='Read device attendance and employee names, no writes')
    sync.add_argument('--host', default=DEFAULT_DEVICE)
    sync.add_argument('--port', type=int, default=4370)
    sync.add_argument('--min-records', type=int, default=37812)
    web = sub.add_parser('serve', help='Private Mac localhost dashboard')
    web.add_argument('--port', type=int, default=8768)
    web.add_argument('--no-web-sync', action='store_true')
    phone = sub.add_parser('serve-phone', help='Authenticated HTTPS on private LAN for iPhone')
    phone.add_argument('--bind', required=True, help='Mac private LAN IPv4, NOT 0.0.0.0')
    phone.add_argument('--port', type=int, default=8769)
    phone.add_argument('--cert', required=True)
    phone.add_argument('--key', required=True)
    phone.add_argument('--no-web-sync', action='store_true')
    phone.add_argument('--host', default=DEFAULT_DEVICE)
    watch = sub.add_parser('watch', help='Foreground periodic read-only sync; Ctrl+C stops')
    watch.add_argument('--host', default=DEFAULT_DEVICE)
    watch.add_argument('--port', type=int, default=4370)
    watch.add_argument('--min-records', type=int, default=37812)
    watch.add_argument('--interval-minutes', type=int, default=30)
    sub.add_parser('status')
    sub.add_parser('backup')
    args = parser.parse_args()
    if args.action == 'sync':
        print(json.dumps(read_device_and_archive(args.db, host=args.host,
            port=args.port, min_records=args.min_records), ensure_ascii=False, indent=2))
    elif args.action == 'watch':
        try:
            watch_device(args.db, host=args.host, port=args.port,
                         min_records=args.min_records,
                         interval_minutes=args.interval_minutes)
        except KeyboardInterrupt:
            print('Periodic read-only sync stopped.', flush=True)
    elif args.action == 'serve':
        serve(args.db, args.port, allow_web_sync=not args.no_web_sync)
    elif args.action == 'serve-phone':
        password = getpass.getpass('ZK CLOCK Manager phone password (12+ chars): ')
        serve(args.db, args.port, bind=args.bind, cert=args.cert, key=args.key,
              phone_password=password, device_host=args.host,
              allow_web_sync=not args.no_web_sync)
    elif args.action == 'status':
        with open_db(args.db) as db:
            print(json.dumps(summary(db), ensure_ascii=False, indent=2))
    elif args.action == 'backup':
        print('BACKUP:', backup_database(args.db))


if __name__ == '__main__':
    main()
