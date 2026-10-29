"""M10 migration regression: modern HTTPS UI preserves M8 fast UX, removes local A+B edit lock."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/"src/main.cpp").read_text()
WEB=(ROOT/"include/m9_secure_ui.h").read_text()
NET=(ROOT/"include/network_setup.h").read_text()

class M8Contracts(unittest.TestCase):
    def test_fast_single_page_works_on_https(self):
        self.assertIn("M9_HOME",SRC)
        for tab in ("home","presets","settings","rtc"):
            self.assertIn('data-tab="'+tab+'"',WEB)
        self.assertIn("showTab",WEB)
        self.assertNotIn("location.reload",WEB)
        self.assertIn("HTTPS", WEB)
    def test_phone_can_run_presets_independently(self):
        self.assertIn('id="homePresets"',WEB)
        self.assertIn("'/api/m9/run'",WEB)
        self.assertIn('secureServer.on("/api/m9/run",HTTP_POST',SRC)
        self.assertIn('secureServer.on("/api/m9/save",HTTP_POST',SRC)
        self.assertIn('secureServer.on("/api/m9/rtc",HTTP_POST',SRC)
        self.assertIn("confirm('تأكيد تعديل ساعة البصمة",WEB)
        self.assertIn("allowedMutation()",SRC)
        self.assertNotIn("X-ZK-Edit",SRC)
    def test_station_cannot_read_or_set_wifi_secret(self):
        self.assertIn('action=="settings"',SRC)
        station_api=SRC.split('secureServer.on("/api/m9/save",HTTP_POST')[1].split(
          'secureServer.on("/api/m9/rtc",HTTP_POST')[0]
        self.assertNotIn('secureServer.arg("pass")',station_api)
        self.assertIn('net.setupClient(secureServer)',SRC)
        self.assertIn("apOn",NET)
        self.assertIn('MDNS.begin("zkclock")',SRC)
    def test_no_automatic_write(self):
        self.assertNotIn("setInterval(()=>",WEB)
        self.assertIn("M5.BtnB.pressedFor(2200)",SRC)
        self.assertIn("if(screenMode==ScreenMode::SETUP && net.apOn)",SRC)
        self.assertIn('secureServer.send_P(200',SRC)

if __name__=="__main__":
    unittest.main()
