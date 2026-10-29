"""Offline validation of the Mac gateway. No device connection is opened."""
import sys
import unittest
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from mac_live_control import Gateway, baghdad_naive_from_epoch_ms

class GatewayTests(unittest.TestCase):
    def test_timezone_conversion(self):
        value = baghdad_naive_from_epoch_ms(1793278800000)
        self.assertEqual(value.year, 2026)
        self.assertIsNone(value.tzinfo)

    def test_read_only_default(self):
        gateway = Gateway(("127.0.0.1", 0), device_host="192.0.2.10",
                          device_port=4370, password="local-test",
                          enable_write=False,
                          reader=lambda: datetime(2026, 10, 29, 12, 0),
                          setter=lambda t: None)
        try:
            self.assertEqual(gateway.read_once(), datetime(2026, 10, 29, 12, 0))
            self.assertNotIn(b"liveApply", gateway.page)
            with self.assertRaises(PermissionError):
                gateway.prepare({"source": "manual",
                                 "local_datetime": "2026-10-29T10:00:00"})
        finally:
            gateway.server_close()

if __name__ == "__main__":
    unittest.main()
