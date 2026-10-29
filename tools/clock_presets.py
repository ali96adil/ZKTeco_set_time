"""Local-only clock shortcuts. No ZKTeco I/O; model and validation only."""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import tempfile
import threading

MAX_PRESETS = 12
MAX_NAME_LEN = 32
ALLOWED_KINDS = {"datetime", "date", "time", "phone"}


def validate_shortcut(item: dict) -> dict:
    if not isinstance(item, dict) or set(item) != {"id", "name", "kind", "value"}:
        raise ValueError("Invalid shortcut fields")
    ident, name, kind, value = (item[k] for k in ("id", "name", "kind", "value"))
    if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,24}", ident):
        raise ValueError("Invalid shortcut id")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= MAX_NAME_LEN:
        raise ValueError("Invalid shortcut label")
    if any(ord(ch) < 32 or ch in "<>" for ch in name):
        raise ValueError("Invalid shortcut label")
    if kind not in ALLOWED_KINDS or not isinstance(value, str):
        raise ValueError("Invalid shortcut kind/value")
    if kind == "phone" and value != "":
        raise ValueError("Phone shortcut value must be empty")
    if kind == "date":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Invalid date")
        dt = datetime.strptime(value, "%Y-%m-%d")
        if dt.strftime("%Y-%m-%d") != value:
            raise ValueError("Invalid date")
        if not 2000 <= dt.year <= 2099:
            raise ValueError("Date outside supported range")
    if kind == "time":
        if not re.fullmatch(r"\d{2}:\d{2}:\d{2}", value):
            raise ValueError("Invalid time")
        datetime.strptime(value, "%H:%M:%S")
    if kind == "datetime":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value):
            raise ValueError("Invalid datetime")
        dt = datetime.fromisoformat(value)
        if not 2000 <= dt.year <= 2099:
            raise ValueError("Datetime outside supported range")
    return {"id": ident, "name": name.strip(), "kind": kind, "value": value}


def target_time(shortcut: dict, device_now: datetime, phone_now: datetime) -> datetime:
    p = validate_shortcut(shortcut)
    kind, value = p["kind"], p["value"]
    if kind == "phone":
        return phone_now.replace(microsecond=0)
    if kind == "datetime":
        return datetime.fromisoformat(value)
    if kind == "date":
        return datetime.fromisoformat(value).replace(
            hour=device_now.hour, minute=device_now.minute, second=device_now.second)
    if kind == "time":
        hour, minute, second = map(int, value.split(":"))
        return device_now.replace(hour=hour, minute=minute, second=second)
    raise ValueError("Unsupported shortcut")


class ShortcutStore:
    """Crash-safe local JSON store. No secrets, credentials or staff records."""
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.RLock()

    def list(self) -> list[dict]:
        with self.lock:
            if not self.path.exists():
                return [{"id": "sync", "name": "مزامنة الهاتف",
                         "kind": "phone", "value": ""}]
            obj = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(obj, list) or len(obj) > MAX_PRESETS:
                raise ValueError("Invalid saved shortcut file")
            items = [validate_shortcut(item) for item in obj]
            if len({x["id"] for x in items}) != len(items):
                raise ValueError("Duplicate ids in shortcut file")
            return items

    def save(self, items: list[dict]) -> None:
        with self.lock:
            if not isinstance(items, list) or not 1 <= len(items) <= MAX_PRESETS:
                raise ValueError("Save 1 to 12 shortcuts")
            checked = [validate_shortcut(x) for x in items]
            if len({x["id"] for x in checked}) != len(checked):
                raise ValueError("Duplicate shortcut ids")
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor, temp = tempfile.mkstemp(dir=self.path.parent, prefix=".shortcuts-")
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as writer:
                    json.dump(checked, writer, ensure_ascii=False, indent=2)
                    writer.flush()
                    os.fsync(writer.fileno())
                os.chmod(temp, 0o600)
                os.replace(temp, self.path)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
