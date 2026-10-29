"""Offline M7 UI and safety contract; hardware not connected."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/"src/main.cpp").read_text(encoding="utf-8")
NET=(ROOT/"include/network_setup.h").read_text(encoding="utf-8")
PRESETS=(ROOT/"include/m5_presets.h").read_text(encoding="utf-8")
RTC=(ROOT/"include/m5_rtc.h").read_text(encoding="utf-8")
NAV=(ROOT/"include/web_navigation.h").read_text(encoding="utf-8")
IDLE=(ROOT/"include/screen_idle.h").read_text(encoding="utf-8")

class M7UiContracts(unittest.TestCase):
    def test_shortcuts_readable_both_modes_but_edits_protected(self):
        self.assertIn('server.on("/api/presets", HTTP_GET', SRC)
        self.assertIn('id="m5Shortcuts"', SRC)
        self.assertIn("fetch('/api/presets'", SRC)
        self.assertIn('server.on("/presets", HTTP_GET', PRESETS)
        self.assertIn("const bool editable = net.setupClient(server);", PRESETS)
        self.assertIn('server.on("/presets", HTTP_POST', PRESETS)
        self.assertIn("if (!net.setupClient(server))", PRESETS)
        self.assertIn('server.on("/presets/import", HTTP_POST', PRESETS)
        self.assertNotIn('server.on("/api/set"',SRC)
        self.assertIn("#define ZK_ENABLE_M5_TIME_WRITE 0",SRC)

    def test_network_pages_are_viewable_in_connect_and_mutations_protected(self):
        self.assertIn('server.on("/setup", HTTP_GET', NET)
        self.assertIn("const bool editable = setupClient(server)", NET)
        self.assertIn('server.on("/setup", HTTP_POST', NET)
        self.assertIn("if (!setupClient(server))", NET)
        self.assertIn('p.putString("apname", newName)',NET)
        self.assertIn("apSsid = savedApName.length() ? savedApName",NET)
        self.assertIn("net.setupClient(server)",RTC)
        self.assertIn('server.on("/rtc",HTTP_GET',RTC)

    def test_unified_navigation(self):
        for target in ["/presets", "/setup", "/rtc"]:
            self.assertIn(target,NAV)
        self.assertIn("zkNav()",NAV)
        self.assertIn("zkPageBegin",NET)
        self.assertIn("zkPageBegin",PRESETS)
        self.assertIn("zkPageBegin",RTC)

    def test_display_sleep_backlight_not_full_deep_sleep(self):
        self.assertIn("M5.Axp.ScreenSwitch(false)",IDLE)
        self.assertIn("M5.Axp.ScreenSwitch(true)",IDLE)
        self.assertIn('p.putUShort("timeout", secs)',IDLE)
        self.assertNotIn("esp_deep_sleep",IDLE)
        self.assertIn("if (screenIdle.sleeping())",SRC)
        self.assertIn("screenIdle.touch()",SRC)
        self.assertIn("wakeBlockUntilRelease = true",SRC)
        self.assertIn("if (wakeBlockUntilRelease)",SRC)
        self.assertIn("!M5.BtnA.isPressed() && !M5.BtnB.isPressed()",SRC)
        self.assertIn("if (screenMode == ScreenMode::CONNECT) connectWifiIfNeeded()",SRC)
        self.assertIn("server.handleClient()",SRC)

if __name__=="__main__":
    unittest.main()
