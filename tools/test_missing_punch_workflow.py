"""Offline end-to-end regression tests for the employee review workflow.

No device connection or attendance writes. Run from repository root:
PYTHONPATH=tools python3 tools/test_missing_punch_workflow.py
"""
import csv
import json
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from missing_punch_review import review_previous_four_days
from missing_punch_notes import MissingPunchNotes
from zktime_csv_import import load_csv


def run():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        source = root / "test.attendance.csv"
        with source.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["Employee", "DateTime", "State"])
            writer.writeheader()
            writer.writerows([
                {"Employee": "1723", "DateTime": "2026-11-03 08:15:00", "State": "IN"},
                {"Employee": "1723", "DateTime": "2026-11-03 14:46:00", "State": "OUT"},
                {"Employee": "1723", "DateTime": "2026-11-04 14:46:00", "State": "OUT"},
                {"Employee": "1723", "DateTime": "2026-11-05 08:20:00", "State": "IN"},
                {"Employee": "9999", "DateTime": "2026-11-05 14:50:00", "State": "OUT"},
            ])
        records = load_csv(source, employee_column="Employee",
                           timestamp_column="DateTime", direction_column="State",
                           direction_map={"IN": "in", "OUT": "out"})
        assert len(records) == 5
        complete = {date(2026, 11, x) for x in (3, 4, 5)}
        workdays = complete | {date(2026, 11, 6)}
        findings = review_previous_four_days("1723", records,
                                              today=date(2026, 11, 7),
                                              complete_days=complete,
                                              workdays=workdays)
        assert [item["status"] for item in findings] == [
            "COMPLETE", "REVIEW_REQUIRED", "REVIEW_REQUIRED", "UNKNOWN_INCOMPLETE_READ"
        ]
        assert findings[1]["missing"] == ["attendance"]
        assert findings[2]["missing"] == ["departure"]
        store = MissingPunchNotes(root / "notes.json")
        fixed_scan_time = datetime(2026, 11, 7, tzinfo=timezone.utc)
        first = store.rescan(findings, now=fixed_scan_time)
        assert len(first) == 2
        assert store.delete("1723", "2026-11-04", "attendance")
        assert len(store.load()) == 1
        assert len(store.rescan(findings, now=fixed_scan_time)) == 2, "Rescan must recreate deleted finding"
        assert store.delete_all("1723") == 2
        assert not store.load()
        assert len(store.rescan(findings, now=fixed_scan_time)) == 2
        assert store.delete_older_than(days=7, now=datetime(2026, 11, 16, tzinfo=timezone.utc)) == 2
        assert not store.load()
        # A fully complete scan now finds the previously missing punch.
        repaired = list(findings)
        repaired[1] = {"employee_id": "1723", "date": "2026-11-04",
                       "status": "COMPLETE", "missing": []}
        assert len(store.rescan(repaired)) == 1
        try:
            load_csv(source, employee_column="Employee",
                     timestamp_column="DateTime", direction_column="State",
                     direction_map={"IN": "in"})
        except ValueError:
            pass
        else:
            raise AssertionError("Unknown OUT state must not be silently inferred")
        print(json.dumps({"result": "PASS", "employee_id": "1723",
                          "tested": ["CSV", "four-day scan", "incomplete read",
                                     "employee isolation", "delete", "rescan",
                                     "seven-day cleanup", "unknown state"]}))


if __name__ == "__main__":
    run()
