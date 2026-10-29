"""M8 fast single-page UX, physical arming, and protected editing contracts."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/"src/main.cpp").read_text(encoding="utf-8")
WEB=(ROOT/"include/m8_mobile_ui.h").read_text(encoding="utf-8")
ARM=(ROOT/"include/local_arm.h").read_text(encoding="utf-8")
NET=(ROOT/"include/network_setup.h").read_text(encoding="utf-8")

class M8Contracts(unittest.TestCase):
    def test_no_full_page_navigation_for_primary_tabs(self):
        self.assertIn("M8_HOME",SRC)
        for tab in ('home','presets','settings','rtc'):
            self.assertIn('data-tab="'+tab+'"',WEB)
        self.assertIn("showTab",WEB)
        self.assertIn("document.querySelectorAll('[data-tab]')", WEB)
        self.assertNotIn("location.reload", WEB)
        self.assertNotIn("https://", WEB)

    def test_shortcut_actions_on_home_but_no_remote_set_time(self):
        self.assertIn("id=\"homePresets\"",WEB)
        self.assertIn("/api/m8/select",WEB)
        self.assertIn('server.on("/api/m8/select", HTTP_POST',SRC)
        self.assertIn('selectedPreset=index;',SRC)
        self.assertIn("localArm.revoke();",SRC)
        self.assertIn('server.on("/api/m8/save", HTTP_POST',SRC)
        self.assertNotIn('server.on("/api/set_time"',SRC)
        self.assertIn("#define ZK_ENABLE_M5_TIME_WRITE 0",SRC)

    def test_physical_arm_is_required_for_station_edits(self):
        self.assertIn("M5.BtnA.pressedFor(1600)",SRC)
        self.assertIn("M5.BtnB.pressedFor(1600)",SRC)
        self.assertIn('server.collectHeaders(m8Headers,1)',SRC)
        self.assertIn('server.header("X-ZK-Edit") != "1"',SRC)
        self.assertIn("localArm.allowed() || net.setupClient(server)",SRC)
        self.assertIn('kWindowMs = 90000',ARM)
        self.assertIn('const bool editable = setupClient(server)',NET)

    def test_station_cannot_edit_secrets(self):
        self.assertIn('action=="settings"',SRC)
        self.assertIn('action=="presets"',SRC)
        self.assertNotIn('server.arg("pass")',SRC)
        self.assertIn("net.currentApName()",SRC)
        self.assertIn('currentApName() const',NET)
        self.assertIn('MDNS.begin("zkclock")',SRC)
        self.assertIn('MDNS.end(); mdnsRunning=false;',SRC)

    def test_no_auto_device_write(self):
        self.assertNotIn("setTimeout(()=>location", WEB)
        self.assertIn("server.send_P(200",SRC)
        self.assertIn("Connection","Connection")
        self.assertNotIn("CMD_SET_TIME",WEB)

if __name__=="__main__":
    unittest.main()
