"""M6 readability and QR setup screen regression, no hardware connected."""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/"src/main.cpp").read_text(encoding="utf-8")
PIO=(ROOT/"platformio.ini").read_text(encoding="utf-8")

class SetupDisplayTests(unittest.TestCase):
    def test_wpa2_wifi_qr_is_local_and_has_quiet_zone(self):
        self.assertIn("ricmoo/QRCode@0.0.1",PIO)
        self.assertIn("#include <qrcode.h>",SRC)
        self.assertIn("WIFI:T:WPA;S:",SRC)
        self.assertIn('";P:" + net.apPassword + ";;"',SRC)
        self.assertIn("qrcode_initText(&qr, data, 4, ECC_MEDIUM",SRC)
        self.assertIn("const int quiet = 4;",SRC)
        self.assertIn("const int unit = 3;",SRC)
        self.assertIn("M5.Lcd.fillRect(left, top, side, side, WHITE)",SRC)

    def test_setup_has_two_legible_pages_and_button_toggle(self):
        self.assertIn("drawSetupQr()",SRC)
        self.assertIn("drawSetupPassword()",SRC)
        self.assertIn("showSetupQr = !showSetupQr",SRC)
        self.assertIn('M5.Lcd.drawString("A: PASS"',SRC)
        self.assertIn('M5.Lcd.drawString("A: QR',SRC)
        self.assertIn("net.apPassword.substring(0,mid)",SRC)
        self.assertIn("net.apPassword.substring(mid)",SRC)
        self.assertNotIn("M5.Lcd.println(net.apPassword);",SRC)

    def test_safe_default_and_boot_selection_remain(self):
        self.assertIn("#define ZK_ENABLE_M5_TIME_WRITE 0",SRC)
        self.assertIn("if (screenMode == ScreenMode::BOOT)",SRC)
        self.assertIn("if (M5.BtnA.wasPressed())",SRC)
        self.assertIn("screenMode = ScreenMode::CONNECT;",SRC)
        self.assertNotIn("startedAt >= 30000",SRC)

if __name__ == "__main__":
    unittest.main()
