"""Pure offline tests; does not import pyzk or connect to attendance device."""
from collections import namedtuple
from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
from zkclock_manager import open_db, archive_read, fetch_punches, summary

Record=namedtuple('Record','user_id uid timestamp status punch')

def run():
    with tempfile.TemporaryDirectory() as root:
        dbpath=Path(root)/'local'/'archive.sqlite3'
        with open_db(dbpath) as db:
            assert summary(db)['archived_records']==0
            logs=[Record('1001',24,datetime(2026,11,8,8,23,11),15,1),
                  Record('1001',24,datetime(2026,11,8,8,23,11),15,1),
                  Record('1001',24,datetime(2026,11,8,14,46,17),15,1),
                  Record('1002',22,datetime(2026,11,9,14,46,00),15,1)]
            report=archive_read(db,logs,host='10.1.65.2',min_records=4,time_now='2026-11-09T11:00:00+00:00')
            assert report['archived_total']==4 and report['new_records']==4, report
            report=archive_read(db,logs,host='10.1.65.2',min_records=4,time_now='2026-11-09T12:00:00+00:00')
            assert report['archived_total']==4 and report['new_records']==0, report
            selected=fetch_punches(db,user_id='1001',date='2026-11-08')
            assert len(selected)==3,selected
            assert sorted(x['occurrence'] for x in selected)==[1,1,2]
            assert len(fetch_punches(db,user_id='1002'))==1
            try:
                archive_read(db,logs[:2],host='10.1.65.2',min_records=4)
            except ValueError:
                pass
            else:
                raise AssertionError('Missing dataset accepted')
            assert summary(db)['archived_records']==4
            try:
                fetch_punches(db,user_id='1002 OR 1=1')
            except ValueError:
                pass
            else:
                raise AssertionError('Bad filter accepted')
        assert (dbpath.stat().st_mode & 0o077)==0
        print('PASS: SQLite archive, duplicate preservation, idempotent rescan, safeguards')

if __name__=='__main__':
    run()
