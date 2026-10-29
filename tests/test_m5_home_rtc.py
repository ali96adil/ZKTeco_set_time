"""Offline M5 stable URL, iPhone Home Screen and RTC source checks."""
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from home_app import app_headers, manifest, png_icon

class HomeAndRTC(unittest.TestCase):
    def test_manifest_and_standalone_meta(self):
        doc=json.loads(manifest())
        self.assertEqual(doc["display"],"standalone")
        self.assertEqual(doc["start_url"],"/")
        self.assertIn("ZK",doc["short_name"])
        html=app_headers("<html><head></head><body>test</body></html>")
        self.assertIn("apple-mobile-web-app-capable",html)
        self.assertIn("manifest.webmanifest",html)

    def test_real_png_encoding(self):
        b=png_icon()
        self.assertTrue(b.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(b),100)

    def test_m5_uses_calibrated_rtc_and_local_mdns(self):
        main=(ROOT/"src/main.cpp").read_text(encoding="utf-8")
        rtc=(ROOT/"include/m5_rtc.h").read_text(encoding="utf-8")
        self.assertIn("MDNS.begin(\"zkclock\")",main)
        self.assertIn("SYNC FROM M5 RTC",main)
        self.assertIn("rtcClock.trustworthy(target)",main)
        self.assertIn('rtcClock.routes(server, net)',main)
        self.assertIn("M5.Rtc.GetDate",rtc)
        self.assertIn("M5.Rtc.GetTime",rtc)
        self.assertIn("M5.Rtc.SetDate",rtc)
        self.assertIn("M5.Rtc.SetTime",rtc)
        self.assertIn("kMaxAgeSeconds",rtc)
        self.assertIn("net.setupClient(server)",rtc)
        self.assertNotIn('server.on("/api/set-time"',main)

if __name__=="__main__":
    unittest.main()
