"""Persistent *hashed* browser-pairing tokens (trusted HTTPS only).

The operator types a short code displayed on the Mac ONCE. Safari retains an
HttpOnly Secure SameSite=Strict cookie for subsequent sessions. The code is
not the session credential; the browser receives a separate random token.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time

COOKIE_NAME = "__Host-zk_operator"
VALID_DAYS = 30
MAX_PAIRED = 5


class PairingStore:
    def __init__(self, path: Path, allow_new: bool = False, lifetime_seconds: int = 300):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.allow_new = allow_new
        self.code = f"{secrets.randbelow(100000000):08d}" if allow_new else None
        self.deadline = time.monotonic() + lifetime_seconds if allow_new else 0
        self.failed = 0

    @staticmethod
    def digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        obj = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(obj, list) or len(obj) > MAX_PAIRED:
            raise ValueError("Invalid pairing file")
        return obj

    def _save(self, obj: list[dict]) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=self.path.parent, prefix=".paired-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(obj, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp, 0o600)
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def authorized(self, token: str | None) -> bool:
        if not isinstance(token, str) or len(token) < 32:
            return False
        hashed = self.digest(token)
        now = time.time()
        with self.lock:
            try:
                return any(
                    secrets.compare_digest(str(row.get("hash", "")), hashed)
                    and float(row.get("expires", 0)) > now
                    for row in self._load()
                )
            except (ValueError, OSError):
                return False

    def pair(self, code: str) -> str:
        with self.lock:
            if not self.allow_new or self.code is None or time.monotonic() > self.deadline:
                raise ValueError("Pairing window is closed")
            if self.failed >= 5:
                raise ValueError("Pairing attempts exhausted")
            if not isinstance(code, str) or not secrets.compare_digest(code, self.code):
                self.failed += 1
                raise ValueError("Invalid pairing code")
            now = time.time()
            existing = [row for row in self._load()
                        if isinstance(row, dict) and float(row.get("expires", 0)) > now]
            if len(existing) >= MAX_PAIRED:
                raise ValueError("Pairing device limit reached")
            token = secrets.token_urlsafe(48)
            existing.append({"hash": self.digest(token),
                             "expires": int(now + 86400 * VALID_DAYS)})
            self._save(existing)
            # Single-use: restart explicitly with --enable-pairing to add another.
            self.code = None
            self.allow_new = False
            return token

    def revoke_all(self) -> None:
        with self.lock:
            self._save([])


def get_cookie(raw_header: str, name: str = COOKIE_NAME) -> str | None:
    for part in (raw_header or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.strip().split("=", 1)
        if key == name:
            return value
    return None


def cookie_header(token: str) -> str:
    return f"{COOKIE_NAME}={token}; Path=/; Max-Age={VALID_DAYS * 86400}; Secure; HttpOnly; SameSite=Strict"
