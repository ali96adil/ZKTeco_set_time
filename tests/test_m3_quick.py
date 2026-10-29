"""Offline one-button quick adjustment test. Uses fake device only."""
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
import tempfile
import threading
import time
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from mac_live_control import Gateway


class QuickTests(unittest.TestCase):
    def test_quick_clock_is_one_attempt_and_one_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            now = {"base": datetime(2026,10,29,12,0), "since": time.monotonic()}
            calls = []
            def clock():
                return now["base"] + timedelta(seconds=time.monotonic() - now["since"])
            def change(value):
                calls.append(value)
                now["base"] = value
                now["since"] = time.monotonic()
            gate=Gateway(("127.0.0.1", 0), device_host="192.0.2.10",
                device_port=4370, password="test", enable_write=True,
                shortcut_path=Path(temp)/"shortcuts.json",
                pairing_path=Path(temp)/"phones.json",
                reader=clock, setter=change)
            try:
                gate.shortcuts.save([
                    {"id":"morning","name":"Morning","kind":"datetime","value":"2026-10-29T11:30:00"},
                    {"id":"sync","name":"Sync","kind":"phone","value":""}
                ])
                with patch("mac_live_control.time.sleep", return_value=None):
                    result=gate.quick({"id":"morning","client_epoch_ms":0})
                self.assertEqual(result["status"], "VERIFIED")
                self.assertEqual(len(calls), 1)
                self.assertEqual(result["requested_time"],"2026-10-29T11:30:00")
                with self.assertRaises(ValueError):
                    gate.quick({"id":"morning","client_epoch_ms":0})
                self.assertEqual(len(calls), 1)
            finally:
                gate.server_close()

    def test_shortcut_large_shift_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            writes=[]
            gate=Gateway(("127.0.0.1",0),device_host="192.0.2.10",
                device_port=4370,password="test",enable_write=True,
                shortcut_path=Path(temp)/"shortcuts.json",
                pairing_path=Path(temp)/"phones.json",
                reader=lambda:datetime(2026,10,29,12,0),
                setter=lambda t:writes.append(t))
            try:
                gate.shortcuts.save([
                    {"id":"old","name":"Old","kind":"datetime","value":"2020-01-01T12:00:00"}])
                with self.assertRaises(ValueError):
                    gate.quick({"id":"old","client_epoch_ms":0})
                self.assertEqual(writes,[])
            finally:
                gate.server_close()

if __name__=="__main__":
    unittest.main()
