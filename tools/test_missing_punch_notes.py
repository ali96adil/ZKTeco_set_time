import tempfile
from datetime import datetime, timezone
from pathlib import Path
from missing_punch_notes import MissingPunchNotes

def test_delete_and_rescan():
    with tempfile.TemporaryDirectory() as directory:
        notes = MissingPunchNotes(Path(directory) / "notes.json")
        finding = [{"employee_id":"24", "date":"2026-11-03",
                    "status":"REVIEW_REQUIRED", "missing":["attendance"]}]
        notes.rescan(finding, now=datetime(2026,11,6,tzinfo=timezone.utc))
        assert len(notes.load()) == 1
        assert notes.delete("24", "2026-11-03", "attendance")
        assert not notes.load()
        notes.rescan(finding, now=datetime(2026,11,6,tzinfo=timezone.utc))
        assert len(notes.load()) == 1
        notes.rescan([{"employee_id":"24","date":"2026-11-03",
                      "status":"UNKNOWN_INCOMPLETE_READ","missing":[]}])
        assert len(notes.load()) == 1
        notes.rescan([{"employee_id":"24","date":"2026-11-03",
                      "status":"COMPLETE","missing":[]}])
        assert not notes.load()

if __name__ == "__main__":
    test_delete_and_rescan()
    print("OK")
