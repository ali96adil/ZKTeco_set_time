"""Offline tests for v0.3: employee pages, time-only rules, authenticated APIs.

Never connects to a device and never fabricates attendance records in production.
"""
import base64
from collections import namedtuple
from datetime import date, datetime
import json
from pathlib import Path
import sqlite3
from threading import Thread
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from zkclock_manager import (archive_read, archive_users, build_server,
                             open_db, summary, watch_device)
from zkclock_manager_reports import (employee_directory, employee_month,
                                     render_employee_page, render_directory_page)

Record = namedtuple('Record', 'user_id uid timestamp status punch')
User = namedtuple('User', 'user_id name')


def get_status(url, *, authorization=None):
    headers = {'Authorization': authorization} if authorization else {}
    try:
        with urlopen(Request(url, headers=headers), timeout=3) as response:
            return response.status, response.read().decode('utf-8')
    except HTTPError as exc:
        return exc.code, exc.read().decode('utf-8')


def run():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'archive.sqlite3'
        with open_db(path) as db:
            logs = [
                Record('1001', 24, datetime(2026, 11, 8, 8, 10, 0), 15, 1),
                Record('1001', 24, datetime(2026, 11, 8, 8, 10, 2), 15, 1),
                Record('1001', 24, datetime(2026, 11, 8, 14, 50, 0), 15, 1),
                Record('1002', 22, datetime(2025, 9, 22, 8, 0, 10), 15, 0),
                Record('1002', 22, datetime(2025, 9, 22, 14, 50, 10), 15, 1),
                Record('1002', 22, datetime(2025, 9, 11, 7, 58, 38), 15, 0),
                Record('1002', 22, datetime(2025, 9, 11, 7, 58, 40), 15, 0),
                Record('1002', 22, datetime(2025, 9, 10, 14, 50, 0), 15, 1),
            ]
            assert archive_read(db, logs, host='10.1.65.2', min_records=8)['archived_total'] == 8
            archive_users(db, [User('1001', 'موظف تجريبي'), User('1002', '<script>alert(1)</script>')])
            known = employee_directory(db)
            assert len(known) == 2
            assert known[0]['user_id'] == '1001'
            assert employee_directory(db, search='1002')[0]['total_punches'] == 5
            assert '<script>' not in render_directory_page(known)

            # Nov 5 was not worked and has no movements; Friday/Saturday are weekend.
            report = employee_month(db, '1001', month='2026-11',
                                    today=date(2026, 11, 9))
            days = {item['date']: item for item in report['days']}
            assert days['2026-11-05']['classification'] == 'no_events'
            assert days['2026-11-06']['classification'] == 'weekend'
            assert days['2026-11-07']['classification'] == 'weekend'
            assert days['2026-11-08']['classification'] == 'morning_and_evening'
            assert days['2026-11-08']['near_repeats'] == 1
            assert days['2026-11-10']['classification'] == 'future'
            assert report['raw_total'] == 3
            assert 'لا توجد حركات (ليس إثبات غياب)' in render_employee_page(report)

            # A historical account's default month is the latest in its archive.
            historical = employee_month(db, '1002', today=date(2026, 11, 9))
            assert historical['month'] == '2025-09'
            historical_days = {x['date']: x for x in historical['days']}
            assert historical_days['2025-09-22']['classification'] == 'morning_and_evening'
            assert historical_days['2025-09-11']['classification'] == 'morning_only'
            assert historical_days['2025-09-10']['classification'] == 'evening_only'
            assert '<script>' not in render_employee_page(historical)
            assert '&lt;script&gt;alert(1)&lt;/script&gt;' in render_employee_page(historical)
            adjusted = employee_month(db, '1002', month='2025-09',
                                      morning='07:30', evening='15:30')
            assert {r['date']: r['classification'] for r in adjusted['days']}['2025-09-22'] == 'uncategorized'
            for kwargs in [
                {'employee_id': '1002 OR 1=1'},
                {'employee_id': '1002\n'},
                {'employee_id': '1002', 'month': '2025-13'},
                {'employee_id': '1002', 'month': '2025-09', 'morning': '99:99'},
                {'employee_id': '1002', 'month': '2025-09', 'morning': '15:30', 'evening': '08:30'},
            ]:
                try:
                    employee_month(db, **kwargs)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f'Unvalidated filter: {kwargs}')
            assert summary(db)['archived_records'] == 8

        # The sync watcher is injectable, foreground only, and never writes to the device.
        calls, pauses = [], []
        def fake_read(path_arg, *, host, port, min_records):
            calls.append((host, min_records))
            return {'record_count': 8 + len(calls), 'new_records': 0}
        watch_device(path, max_reads=2, interval_minutes=10, min_records=8,
                     reader=fake_read, pause=pauses.append)
        assert calls == [('10.1.65.2', 8), ('10.1.65.2', 9)]
        assert pauses == [600]
        for interval in (0, 9, 1441):
            try:
                watch_device(path, interval_minutes=interval, max_reads=1, reader=fake_read)
            except ValueError:
                pass
            else:
                raise AssertionError('Out-of-bounds polling accepted')

        server = build_server(path, port=0, allow_web_sync=False)
        host, port = server.server_address
        base = f'http://{host}:{port}'
        t = Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            code, body = get_status(base + '/employees')
            assert code == 200 and 'دليل الموظفين' in body
            code, body = get_status(base + '/employee?user=1001&month=2026-11')
            assert code == 200 and '2026-11-08' in body
            code, body = get_status(base + '/api/employee?user=1001&month=2026-11')
            parsed = json.loads(body)
            assert code == 200 and parsed['employee_id'] == '1001'
            code, body = get_status(base + '/api/employees?search=1002')
            assert code == 200 and json.loads(body)[0]['user_id'] == '1002'
            assert get_status(base + '/employee?user=1002%20OR%201%3D1')[0] == 400
            assert get_status(base + '/api/employee?user=1002&month=2025-13')[0] == 400
            assert get_status(base + '/api/employees?search=%25')[0] == 400
            assert get_status(base + '/delete?user=1002')[0] == 404
            assert get_status(base + '/sync')[0] == 404
        finally:
            server.shutdown()
            server.server_close()
            t.join(timeout=3)

        secured = build_server(path, bind='127.0.0.1', port=0,
                               phone_password='private-for-unit-tests',
                               allow_web_sync=False)
        _, port = secured.server_address
        url = f'http://127.0.0.1:{port}/api/employee?user=1001'
        t = Thread(target=secured.serve_forever, daemon=True)
        t.start()
        try:
            assert get_status(url)[0] == 401
            auth = 'Basic ' + base64.b64encode(b'zkclock:private-for-unit-tests').decode('ascii')
            assert get_status(url, authorization=auth)[0] == 200
        finally:
            secured.shutdown()
            secured.server_close()
            t.join(timeout=3)

        with sqlite3.connect(path) as db:
            assert db.execute('SELECT COUNT(*) FROM device_punches').fetchone()[0] == 8
        print('PASS v0.3: employee profile, weekend calendar, no false absences, editable view rules, APIs, auth, watcher')


if __name__ == '__main__':
    run()
