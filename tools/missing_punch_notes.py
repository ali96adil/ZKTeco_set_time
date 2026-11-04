"""Local review-note lifecycle for missing punch findings.

Delete clears *notes only*, never device logs. A subsequent scan can recreate
the same finding. JSON is stored locally on the gateway, not in GitHub.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _key(employee_id, day, kind):
    return f"{employee_id}|{day}|{kind}"


class MissingPunchNotes:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Invalid notes database")
        return data

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def rescan(self, findings, *, now=None):
        """Replace current review notes with verified scan findings.

        Unknown/incomplete reads MUST NOT erase earlier notes or create new ones.
        Complete days remove notes if the previously missing event is now present.
        """
        now = now or datetime.now(timezone.utc)
        data = self.load()
        for day in findings:
            status = day["status"]
            if status == "UNKNOWN_INCOMPLETE_READ":
                continue
            employee, date = str(day["employee_id"]), day["date"]
            if status in ("COMPLETE", "REVIEW_REQUIRED", "NOT_SCHEDULED"):
                for kind in ("attendance", "departure"):
                    key = _key(employee, date, kind)
                    if status == "REVIEW_REQUIRED" and kind in day["missing"]:
                        data.setdefault(key, {
                            "employee_id": employee,
                            "date": date,
                            "kind": kind,
                            "first_seen": now.isoformat(),
                        })
                    else:
                        data.pop(key, None)
        self._save(data)
        return data

    def delete(self, employee_id, day, kind):
        data = self.load()
        removed = data.pop(_key(str(employee_id), day, kind), None) is not None
        self._save(data)
        return removed

    def delete_all(self, employee_id=None):
        data = self.load()
        if employee_id is None:
            count = len(data)
            data.clear()
        else:
            keys = [k for k, v in data.items()
                    if v["employee_id"] == str(employee_id)]
            count = len(keys)
            for key in keys:
                del data[key]
        self._save(data)
        return count

    def delete_older_than(self, *, days=7, now=None):
        if days < 0:
            raise ValueError("days must be nonnegative")
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)
        data = self.load()
        keys = [k for k, v in data.items()
                if datetime.fromisoformat(v["first_seen"]) < cutoff]
        for key in keys:
            del data[key]
        self._save(data)
        return len(keys)
