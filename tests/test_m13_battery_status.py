"""M13 approximate original-M5StickC-Plus battery and setup network checks."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
MAIN=(ROOT/"src/main.cpp").read_text()
WEB=(ROOT/"include/m9_secure_ui.h").read_text()
SETUP=(ROOT/"include/web_navigation.h").read_text()
BATTERY=(ROOT/"include/m5_battery_estimate.h").read_text()

class BatteryUiTest(unittest.TestCase):
    def test_original_axp192_reading_and_no_fake_precision(self):
        self.assertIn("M5.Axp.GetBatVoltage()",MAIN)
        self.assertIn("M5.Axp.GetVBusVoltage()",MAIN)
        self.assertIn("m5battery::estimatePercent",MAIN)
        self.assertIn("m5battery::hasUsbPower",MAIN)
        self.assertIn("battery.percent>=0",MAIN)
        self.assertIn("millis()-battery.at<10000",MAIN)
        self.assertIn("NO calibrated battery % fuel-gauge",BATTERY)
        self.assertIn("std::isfinite(v)",BATTERY)
        self.assertIn("voltage_v",MAIN)
        self.assertIn("percent_estimate",MAIN)
        self.assertNotIn("GetBatteryLevel()",MAIN)

    def test_no_secret_exposure_from_battery_http(self):
        self.assertIn('secureServer.on("/api/battery",HTTP_GET',MAIN)
        self.assertIn("if(!(screenMode==ScreenMode::SETUP && net.apOn) && !allowedHttps())return;",MAIN)
        self.assertIn('secureJson(200,batteryJson())',MAIN)
        self.assertIn("estimated",MAIN)

    def test_visible_m5_and_both_phone_modes(self):
        self.assertIn("M5.Lcd.drawString(batteryLabel()",MAIN)
        self.assertIn("id=\"batteryTop\"",WEB)
        self.assertIn("id=\"batteryDetail\"",WEB)
        self.assertIn("setInterval(refreshBattery,30000)",WEB)
        self.assertIn("id='batteryMini'",SETUP)
        self.assertIn("/api/battery",SETUP)
        self.assertIn("setInterval(updateSetupBattery,30000)",SETUP)
        self.assertIn("تقريبية",SETUP)

    def test_hostname_best_effort_with_proven_https_fallback(self):
        self.assertIn('MDNS.begin("zkclock")',MAIN)
        self.assertIn('setupDns.start(53,"zkclock.local",WiFi.softAPIP())',MAIN)
        self.assertIn('WiFi.setSleep(false);',MAIN)
        self.assertIn('WiFi.setSleep(true);',MAIN)
        self.assertIn('M5.Lcd.drawString("https://192.168.4.1"',MAIN)
        self.assertIn('M5.Lcd.drawString("https://zkclock.local"',MAIN)
        self.assertIn("ESPWebServerSecure secureServer(443)",MAIN)
        self.assertNotIn("WebServer server(80)",MAIN)
        self.assertIn('kClockWriteCooldownMs = 2000',MAIN)
        self.assertIn('M5.BtnB.pressedFor(700)',MAIN)

if __name__=="__main__":
    unittest.main()
