"""No-hardware integration tests for the Mac M5 UI simulator."""
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import mac_simulator as sim  # noqa: E402


class MacSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.server = sim.MacSimulator(("127.0.0.1", 0), mode="mock",
                                       offset_seconds=152.0)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()

    def get(self, path):
        with urlopen(self.url + path, timeout=3) as response:
            return response.status, response.read(), response.headers

    def post(self, path, document):
        body = json.dumps(document).encode("utf-8")
        request = Request(self.url + path, method="POST", data=body,
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, json.load(exc)

    def test_exact_embedded_ui_mock_mode(self):
        status, page, headers = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"no-store", headers["Cache-Control"].encode())
        self.assertIn("api/mock/set", page.decode("utf-8"))
        self.assertIn("id=\"preview\"", page.decode("utf-8"))
        self.assertIn("ZKTeco Clock", page.decode("utf-8"))

    def test_mock_time_is_approximately_152_seconds_fast(self):
        before = sim.datetime.now(sim.BAGHDAD).replace(tzinfo=None)
        status, raw, _ = self.get("/api/read")
        after = sim.datetime.now(sim.BAGHDAD).replace(tzinfo=None)
        body = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertTrue(body["simulated"])
        clock = sim.parse_local_datetime(body["device_time"])
        self.assertTrue(150 <= (clock - before).total_seconds() <= 154)
        self.assertTrue(150 <= (clock - after).total_seconds() <= 154)

    def test_simulation_changes_virtual_clock_only(self):
        new_time = "2026-10-29T08:15:12"
        status, body = self.post("/api/mock/set", {"local_datetime": new_time})
        self.assertEqual(status, 200)
        self.assertTrue(body["simulated"])
        self.assertTrue(body["device_time"].startswith(new_time[:-2]))
        self.assertEqual(self.server.clock.get_time().year, 2026)

        new_time = "2030-01-01T09:10:11"
        status, body = self.post("/api/mock/set", {"local_datetime": new_time})
        self.assertEqual(status, 200)
        self.assertEqual(body["device_time"][:16], new_time[:16])

    def test_reject_bad_dates(self):
        for value in ["2026-02-29T12:00:00", "2024-13-01T12:00:00",
                      "2026-10-29T24:00:00", "1999-10-29T12:00:00",
                      "2026-10-29T12:00"]:
            with self.subTest(value=value):
                status, response = self.post("/api/mock/set",
                                             {"local_datetime": value})
                self.assertEqual(status, 400)
                self.assertFalse(response["ok"])

    def test_unlisted_http_write_route_is_not_available(self):
        status, body = self.post("/api/set", {"local_datetime": "2026-10-29T12:00:00"})
        self.assertEqual(status, 404)
        self.assertFalse(body["ok"])

    def test_live_readonly_has_no_setting_endpoints(self):
        live = sim.MacSimulator(("127.0.0.1", 0), mode="live-readonly")
        thread = threading.Thread(target=live.serve_forever, daemon=True)
        thread.start()
        try:
            address = "http://127.0.0.1:%d" % live.server_address[1]
            request = Request(address + "/api/mock/set", method="POST",
                              data=b'{"local_datetime":"2026-10-29T12:00:00"}',
                              headers={"Content-Type": "application/json"})
            with self.assertRaises(HTTPError) as error:
                urlopen(request, timeout=3)
            self.assertEqual(error.exception.code, 404)
            with patch.object(sim, "live_device_time",
                              return_value=sim.datetime(2026,10,29,12,30,0)):
                with urlopen(address + "/api/read", timeout=3) as response:
                    self.assertEqual(json.load(response)["device_time"],
                                     "2026-10-29T12:30:00")
            with urlopen(address, timeout=3) as response:
                page = response.read().decode("utf-8")
                self.assertNotIn("api/mock/set", page)
        finally:
            live.shutdown()
            thread.join(timeout=3)
            live.server_close()

    def test_source_stays_read_only(self):
        # Neither simulator nor embedded firmware should have an actual
        # ZKTeco SET_TIME call/command.
        source = (ROOT / "tools" / "mac_simulator.py").read_text()
        m5_source = (ROOT / "src" / "main.cpp").read_text()
        self.assertNotIn("conn.set_time(", source)
        self.assertNotIn("CMD_SET_TIME =", m5_source)
        self.assertNotIn("conn.set_time", m5_source)


if __name__ == "__main__":
    unittest.main()
