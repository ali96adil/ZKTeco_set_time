"""No-device tests for shortcuts and remembered phone pairing."""
from datetime import datetime
from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from clock_presets import ShortcutStore, target_time, validate_shortcut
from phone_pairing import PairingStore, get_cookie, cookie_header


class ShortcutTests(unittest.TestCase):
    def test_target_clock_compositions(self):
        current = datetime(2026, 10, 29, 14, 25, 31)
        cases = [
            ({"id": "a", "name": "Morning", "kind": "time", "value": "08:10:00"},
             datetime(2026, 10, 29, 8, 10)),
            ({"id": "b", "name": "Date", "kind": "date", "value": "2026-11-01"},
             datetime(2026, 11, 1, 14, 25, 31)),
            ({"id": "c", "name": "Full", "kind": "datetime", "value": "2027-01-01T01:02:03"},
             datetime(2027, 1, 1, 1, 2, 3)),
            ({"id": "d", "name": "Sync", "kind": "phone", "value": ""},
             datetime(2026, 10, 29, 15, 0)),
        ]
        for item, expected in cases:
            with self.subTest(kind=item["kind"]):
                self.assertEqual(target_time(item, current,
                    datetime(2026, 10, 29, 15, 0)), expected)

    def test_invalid_dates_and_duplicate_ids(self):
        for kind, value in [("date", "2026-02-29"), ("time", "25:00:00"),
                            ("datetime", "1990-01-01T12:00:00")]:
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    validate_shortcut({"id": "x", "name": "Test", "kind": kind,
                                       "value": value})
        with tempfile.TemporaryDirectory() as temp:
            store = ShortcutStore(Path(temp) / "shortcuts.json")
            item={"id": "same", "name": "A", "kind": "phone", "value": ""}
            with self.assertRaises(ValueError):
                store.save([item, item])
            store.save([item])
            self.assertEqual(store.list(), [item])


class PairingTests(unittest.TestCase):
    def test_pairing_token_persists_across_restarts(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp) / "phones.json"
            p=PairingStore(path, allow_new=True)
            with self.assertRaises(ValueError):
                p.pair("00000000" if p.code != "00000000" else "99999999")
            token=p.pair(p.code)
            self.assertTrue(p.authorized(token))
            self.assertFalse(p.authorized(token + "x"))
            self.assertNotIn(token, path.read_text())
            self.assertEqual(get_cookie(cookie_header(token)), token)
            self.assertTrue(PairingStore(path, allow_new=False).authorized(token))
            p.revoke_all()
            self.assertFalse(p.authorized(token))

    def test_incorrect_codes_lock_out(self):
        with tempfile.TemporaryDirectory() as temp:
            p=PairingStore(Path(temp) / "phones.json", allow_new=True)
            bad = "00000000" if p.code != "00000000" else "11111111"
            for i in range(5):
                with self.assertRaises(ValueError):
                    p.pair(bad)
            with self.assertRaises(ValueError):
                p.pair(p.code)


if __name__ == "__main__":
    unittest.main()
