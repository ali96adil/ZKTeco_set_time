"""Regression: full datetime commands, explicit boot choice and M5 safety."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from clock_presets import validate_shortcut

class M4Contract(unittest.TestCase):
    def test_only_complete_datetime_or_phone(self):
        for kind,value in [("date","2026-11-01"),("time","08:00:00")]:
            with self.assertRaises(ValueError):
                validate_shortcut({"id":"x","name":"Old shortcut",
                                   "kind":kind,"value":value})
        self.assertEqual(validate_shortcut({
            "id":"full","name":"Complete","kind":"datetime",
            "value":"2026-11-01T08:00:00"})["kind"],"datetime")
        self.assertEqual(validate_shortcut({
            "id":"sync","name":"Phone sync","kind":"phone",
            "value":""})["kind"],"phone")

    def test_explicit_start_menu_not_30_second_fallback(self):
        main=(ROOT/"src/main.cpp").read_text(encoding="utf-8")
        network=(ROOT/"include/network_setup.h").read_text(encoding="utf-8")
        self.assertIn('M5.Lcd.drawString("SETUP WIFI"',main)
        self.assertIn('M5.Lcd.drawString("CONNECT WIFI"',main)
        self.assertIn('M5.Lcd.drawString("A"',main)
        self.assertIn('M5.Lcd.drawString("B"',main)
        self.assertIn("ScreenMode::BOOT",main)
        self.assertIn("M5.BtnB.pressedFor(2200)",main)
        self.assertIn("M5.BtnB.pressedFor(4200)",main)
        self.assertNotIn("startedAt >= 30000",network)
        self.assertNotIn("millis() - startedAt",network)
        self.assertNotIn("if (!apOn && millis()",network)

    def test_lcd_preset_run_requires_physical_hold_and_default_disabled(self):
        main=(ROOT/"src/main.cpp").read_text(encoding="utf-8")
        self.assertIn("#define ZK_ENABLE_M5_TIME_WRITE 0",main)
        self.assertIn("executeSelected(false)",main)
        self.assertIn("executeSelected(true)",main)
        self.assertIn("WRITE LAB DISABLED",main)
        self.assertIn("stored.routes(server, net)",main)
        self.assertNotIn('server.on("/api/set"',main)

if __name__=="__main__":
    unittest.main()
