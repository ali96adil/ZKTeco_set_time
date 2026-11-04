"""Delete local review notes; subsequent scans may recreate missing findings."""
import argparse
from missing_punch_notes import MissingPunchNotes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--notes", default="local/missing_punch_notes.json")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--one", nargs=3, metavar=("EMPLOYEE_ID", "YYYY-MM-DD", "KIND"))
    action.add_argument("--all", action="store_true")
    action.add_argument("--older-than-seven-days", action="store_true")
    args = parser.parse_args()
    notes = MissingPunchNotes(args.notes)
    if args.one:
        employee, day, kind = args.one
        if kind not in ("attendance", "departure"):
            parser.error("KIND must be attendance or departure")
        print("deleted" if notes.delete(employee, day, kind) else "not found")
    elif args.all:
        print(f"deleted {notes.delete_all()} notes")
    else:
        print(f"deleted {notes.delete_older_than(days=7)} notes")


if __name__ == "__main__":
    main()
