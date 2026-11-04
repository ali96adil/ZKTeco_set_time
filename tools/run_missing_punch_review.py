"""Build a read-only four-day review report from a validated ZKTime CSV export.

Does not connect to the terminal, change clock time, or mutate attendance data.
CSV column/state mapping must be supplied by the operator after inspecting export.
"""
import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from missing_punch_review import review_previous_four_days
from missing_punch_notes import MissingPunchNotes
from zktime_csv_import import load_csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--employee-id", default="1723")
    parser.add_argument("--employee-column", required=True)
    parser.add_argument("--timestamp-column", required=True)
    parser.add_argument("--direction-column", required=True)
    parser.add_argument("--in-value", required=True)
    parser.add_argument("--out-value", required=True)
    parser.add_argument("--datetime-format", default="%Y-%m-%d %H:%M:%S")
    parser.add_argument("--today", default=date.today().isoformat(),
                        help="Local date YYYY-MM-DD, not UTC")
    parser.add_argument("--workdays", required=True,
                        help="Comma-separated ISO dates scheduled for work")
    parser.add_argument("--complete-days", required=True,
                        help="Comma-separated ISO dates with verified complete export")
    parser.add_argument("--notes", default="local/missing_punch_notes.json")
    parser.add_argument("--output", default="local/missing_punch_report.json")
    args = parser.parse_args()

    def parse_days(raw):
        return {date.fromisoformat(value.strip()) for value in raw.split(",") if value.strip()}

    today = date.fromisoformat(args.today)
    allowed = {today - timedelta(days=n) for n in range(1, 5)}
    workdays = parse_days(args.workdays)
    complete = parse_days(args.complete_days)
    if not workdays <= allowed or not complete <= allowed:
        parser.error("workdays and complete-days must be within the previous four completed dates")
    if args.in_value == args.out_value:
        parser.error("IN and OUT values must differ")

    records = load_csv(
        args.csv, employee_column=args.employee_column,
        timestamp_column=args.timestamp_column,
        direction_column=args.direction_column,
        direction_map={args.in_value: "in", args.out_value: "out"},
        datetime_format=args.datetime_format,
    )
    findings = review_previous_four_days(
        args.employee_id, records, today=today,
        complete_days=complete, workdays=workdays,
    )
    notes = MissingPunchNotes(args.notes)
    current = notes.rescan(findings)
    report = {
        "employee_id": args.employee_id,
        "scan_date": today.isoformat(),
        "findings": findings,
        "notes": sorted(current.values(), key=lambda n: (n["date"], n["kind"])),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "findings": len(findings),
                      "review_notes": len(report["notes"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
