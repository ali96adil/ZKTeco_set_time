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
    def test_secure_setup_routes_restricted_to_physical_ap(self):
        self.assertIn('secureServer.on("/auth/setup",HTTP_GET', SRC)
        self.assertIn('secureServer.on("/auth/setup",HTTP_POST', SRC)
        self.assertIn("net.attachRoutes(secureServer,screenIdle)", SRC)
        self.assertIn("stored.routes(secureServer,net)", SRC)
        self.assertIn("rtcClock.routes(secureServer,net)", SRC)
        self.assertIn('server.on("/setup", HTTP_GET', NET)
        self.assertIn("if (!setupClient(server))",NET)
        self.assertIn("if (!net.setupClient(server))",PRESETS)
        self.assertIn("if (!net.setupClient(server))",RTC)
        self.assertIn("origin==\"https://zkclock.local\"",NET)
        self.assertIn("origin==\"https://192.168.4.1\"",NET)
        self.assertIn('p.putString("apname", newName)',NET)
        self.assertIn("apSsid = savedApName.length() ? savedApName",NET)

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
        self.assertIn("secureServer.handleClient()",SRC)

if __name__=="__main__":
    unittest.main()
