"""Read-only four-day missing-punch review for ZK CLOCK.

Input records are normalized, verified device events for ONE selected employee.
This module never connects to the clock and never changes device time or records.
"""
from datetime import date, datetime, time, timedelta
from typing import Iterable, Mapping

ATTENDANCE_CUTOFF = time(8, 30)
DEPARTURE_START = time(14, 45)


def review_previous_four_days(
    employee_id: str,
    records: Iterable[Mapping],
    *,
    today: date,
    complete_days: Iterable[date] = (),
    workdays: Iterable[date] = (),
):
    """Return findings for the four *completed* days before today.

    records: dicts with employee_id, timestamp (datetime), kind ('in'/'out').
    complete_days: dates for which a complete, successful device-log read
      was verified. A missing record on any other date is UNKNOWN, not absent.
    workdays: explicitly scheduled dates; others are NOT_SCHEDULED.
    Do not infer direction from device status codes without model validation.
    """
    complete = set(complete_days)
    scheduled = set(workdays)
    by_day = {}
    for event in records:
        if str(event.get("employee_id")) != str(employee_id):
            continue
        stamp = event.get("timestamp")
        kind = event.get("kind")
        if not isinstance(stamp, datetime) or kind not in ("in", "out"):
            continue
        by_day.setdefault(stamp.date(), []).append((stamp.time(), kind))
    results = []
    for offset in range(4, 0, -1):
        day = today - timedelta(days=offset)
        base = {"employee_id": str(employee_id), "date": day.isoformat()}
        if day not in scheduled:
            results.append({**base, "status": "NOT_SCHEDULED", "missing": []})
            continue
        if day not in complete:
            results.append({**base, "status": "UNKNOWN_INCOMPLETE_READ", "missing": []})
            continue
        events = by_day.get(day, [])
        has_in = any(kind == "in" and t <= ATTENDANCE_CUTOFF for t, kind in events)
        has_out = any(kind == "out" and t >= DEPARTURE_START for t, kind in events)
        missing = []
        if not has_in:
            missing.append("attendance")
        if not has_out:
            missing.append("departure")
        results.append({**base, "status": "REVIEW_REQUIRED" if missing else "COMPLETE", "missing": missing})
    return results
