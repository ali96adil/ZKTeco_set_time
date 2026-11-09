"""Offline regression of v0.2 archive/dashboard and local HTTP security."""
import base64
from collections import namedtuple
from datetime import datetime
import json
from pathlib import Path
import re
import tempfile
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from zkclock_manager import (open_db, archive_read, archive_users, daily_summary,
                             fetch_punches, count_matching, summary,
                             render_page, build_server, backup_database)

Record = namedtuple('Record', 'user_id uid timestamp status punch')
User = namedtuple('User','user_id name')


def get(base, path='/', *, host=None, auth=None):
    headers = {}
    if host is not None:
        headers['Host'] = host
    if auth is not None:
        headers['Authorization'] = auth
    return urlopen(Request(base + path, headers=headers), timeout=3)


def status_of(req):
    try:
        with urlopen(req, timeout=3) as r:
            return r.status
    except HTTPError as e:
        return e.code


def run():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / 'archive.sqlite3'
        with open_db(db_path) as db:
            logs = [
                Record('1002', 22, datetime(2025, 9, 22, 8, 0, 10), 15, 0),
                Record('1002', 22, datetime(2025, 9, 22, 8, 0, 12), 15, 0),
                Record('1002', 22, datetime(2025, 9, 22, 14, 50, 10), 15, 1),
                Record('1002', 22, datetime(2025, 9, 22, 14, 50, 10), 15, 1),
                Record('1001', 24, datetime(2026, 11, 8, 8, 10, 0), 15, 1),
            ]
            assert archive_read(db, logs, host='10.1.65.2', min_records=5)['new_records'] == 5
            assert archive_users(db, [User('1002', '<script>bad</script>'),
                                      User('1001', 'موظف آخر')]) == 2
            assert count_matching(db, user_id='1002') == 4
            assert count_matching(db, user_id='موظف') == 1
            assert count_matching(db, date_from='2025-09-01', date_to='2025-09-30') == 4
            assert len(fetch_punches(db, user_id='1002', date='2025-09-22')) == 4
            assert count_matching(db, user_id='1002', date='2026-11-09') == 0
            days = daily_summary(db, user_id='1002')
            assert days[0]['total_punches'] == 4
            assert days[0]['near_repeats'] == 2, days
            assert days[0]['first_punch'].endswith('08:00:10')
            assert days[0]['last_punch'].endswith('14:50:10')
            page = render_page(summary(db), fetch_punches(db, user_id='1002'), days, 4)
            assert '<script>' not in page
            assert '&lt;script&gt;bad&lt;/script&gt;' in page
            assert 'مزامنة من الجهاز' not in page
            for kwargs in ({'date_from': '2025-02-30'}, {'date_from': '2026-11-09', 'date_to': '2025-09-01'},
                           {'user_id': '1002 OR 1=1'}, {'user_id': '%'}, {'date_to': 'not-a-date'}):
                try:
                    count_matching(db, **kwargs)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f'Invalid filter accepted: {kwargs!r}')
        backup = backup_database(db_path)
        assert backup.exists() and (backup.stat().st_mode & 0o077) == 0
        assert backup.read_bytes() != b''

        server = build_server(db_path, port=0, allow_web_sync=True)
        host, port = server.server_address
        base = f'http://{host}:{port}'
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with get(base, '/?user=1002&from=2025-09-01&to=2025-09-30') as resp:
                html = resp.read().decode('utf-8')
                assert resp.status == 200
                assert 'الملخص اليومي' in html
                assert 'مزامنة من الجهاز' in html
                assert '2025-09-22' in html
                csrf = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
            with get(base, '/api/days?user=1002') as resp:
                assert json.load(resp)[0]['near_repeats'] == 2
            with get(base, '/api/summary') as resp:
                assert json.load(resp)['archived_records'] == 5
            assert status_of(Request(base + '/', headers={'Host': 'attacker.example'})) == 403
            assert status_of(Request(base + '/', method='POST', data=b'csrf=wrong')) == 405  # POST / forbidden
            assert status_of(Request(base + '/sync', method='POST', data=b'csrf=wrong')) == 403
            body = urlencode({'csrf': csrf}).encode('utf-8')
            assert status_of(Request(base + '/sync', method='POST', data=body,
                                    headers={'Origin': 'https://evil.example'})) == 403
            assert status_of(Request(base + '/?user=1002%20OR%201%3D1')) == 400
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

        # Basic authentication gate for the explicit HTTPS-facing handler.
        secure = build_server(db_path, port=0, bind='127.0.0.1',
                              phone_password='sufficiently-long-secret', allow_web_sync=False)
        port = secure.server_address[1]
        base = f'http://127.0.0.1:{port}'
        t = Thread(target=secure.serve_forever, daemon=True)
        t.start()
        try:
            assert status_of(Request(base + '/api/summary')) == 401
            token = 'Basic ' + base64.b64encode(b'zkclock:sufficiently-long-secret').decode('ascii')
            with get(base, '/api/summary', auth=token) as resp:
                assert json.load(resp)['archived_records'] == 5
            assert status_of(Request(base + '/sync', method='POST', data=b'a=1',
                                    headers={'Authorization': token})) == 405
        finally:
            secure.shutdown()
            secure.server_close()
            t.join(timeout=3)
        print('PASS: daily summaries, name search, date filters, mobile UI, duplicate counts, localhost access, auth, CSRF, backups')


if __name__ == '__main__':
    run()
