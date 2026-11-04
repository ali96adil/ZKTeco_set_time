"""Import explicitly mapped ZKTime CSV exports without changing terminal records.

Usage: load_csv(path, employee_column='User ID', timestamp_column='Date/Time',
                direction_column='Punch State', direction_map={'Check In':'in','Check Out':'out'})
A source without a trustworthy IN/OUT field must be reviewed manually.
"""
import csv
from datetime import datetime


def load_csv(path, *, employee_column, timestamp_column, direction_column,
             direction_map, datetime_format="%Y-%m-%d %H:%M:%S"):
    if not direction_map or not set(direction_map.values()) <= {"in", "out"}:
        raise ValueError("Explicit IN/OUT mapping required")
    records = []
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {employee_column, timestamp_column, direction_column}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Export missing required columns: " +
                             ", ".join(sorted(required - set(reader.fieldnames or []))))
        for line, row in enumerate(reader, start=2):
            if not any(row.values()):
                continue
            direction = direction_map.get((row[direction_column] or "").strip())
            if direction is None:
                raise ValueError(f"Unrecognized punch state on CSV line {line}")
            try:
                stamp = datetime.strptime(row[timestamp_column].strip(), datetime_format)
            except (ValueError, AttributeError) as exc:
                raise ValueError(f"Invalid timestamp on CSV line {line}") from exc
            records.append({"employee_id": str(row[employee_column]).strip(),
                            "timestamp": stamp, "kind": direction})
    return records
