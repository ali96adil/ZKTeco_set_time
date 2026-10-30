"""M13 regression: AXP192 battery estimate, protected endpoints and AP IP fallback."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src/main.cpp").read_text(encoding="utf-8")
SETUP = (ROOT / "include/network_setup.h").read_text(encoding="utf-8")
PHONE = (ROOT / "include/m9_secure_ui.h").read_text(encoding="utf-8")


class BatteryAndDiscovery(unittest.TestCase):
    def test_battery_is_approximate_and_read_only(self):
        self.assertIn("M5.Axp.GetBatVoltage()", MAIN)
        self.assertIn("M5.Axp.GetVBusVoltage()", MAIN)
        self.assertIn("BatteryStatus readBattery()", MAIN)
        self.assertIn('secureServer.on("/api/battery",HTTP_GET', MAIN)
        self.assertIn("if (!(screenMode==ScreenMode::SETUP && net.apOn) && !allowedHttps())", MAIN)
        self.assertNotIn('secureServer.on("/api/battery",HTTP_POST', MAIN)
        self.assertIn("percent_approx", MAIN)
        self.assertIn("battery_percent", MAIN)

    def test_setup_ip_fallback_not_dependent_on_mdns(self):
        self.assertIn('M5.Lcd.drawString("192.168.4.1"', MAIN)
        self.assertIn("https://192.168.4.1/setup", SETUP)
        self.assertIn("https://zkclock.local/setup", SETUP)
        self.assertIn("fetch('/api/battery'", SETUP)
        self.assertIn('MDNS.begin("zkclock")', MAIN)
        self.assertIn("lastMdnsRetryAt", MAIN)
        self.assertIn("canServe && !mdnsRunning", MAIN)
        self.assertIn('ESPWebServerSecure secureServer(443)', MAIN)

    def test_iphone_battery_and_attendance_safety(self):
        self.assertIn('id="batteryState"', PHONE)
        self.assertIn("state.battery_percent>=0", PHONE)
        self.assertIn("state.usb_power", PHONE)
        self.assertIn('M5.BtnB.pressedFor(700)', MAIN)
        self.assertIn("kClockWriteCooldownMs = 2000", MAIN)
        self.assertIn("wakeBlockUntilRelease = true;", MAIN)


if __name__ == "__main__":
    unittest.main()
