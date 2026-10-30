"""One-tap production acceptance: no dialogs, no large-shift gate, no automatic retry."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/"src/main.cpp").read_text()
UI=(ROOT/"include/m9_secure_ui.h").read_text()
PIO=(ROOT/"platformio.ini").read_text()
DOC=(ROOT/"docs/V1_FULL_CONTROL_HTTPS_SETUP.md").read_text()

class OneTap(unittest.TestCase):
    def test_single_authenticated_https_command_no_dialog(self):
        self.assertIn("btn.onclick=async()=>{", UI)
        self.assertIn("const r=await api('/api/m9/run','POST',{index:String(i)});",UI)
        self.assertNotIn("confirm(",UI)
        self.assertNotIn("requires_large_confirmation",UI)
        self.assertNotIn("confirm:'large'",UI)
        self.assertIn("busy=true;btn.disabled=true;",UI)
        self.assertIn("finally{busy=false;btn.disabled=false;",UI)
        self.assertIn("message(r.message||'تم إرسال الأمر وفحص ساعة البصمة'",UI)

    def test_single_physical_b_hold_any_datetime(self):
        self.assertIn("M5.BtnB.pressedFor(2200)",SRC)
        self.assertNotIn("M5.BtnB.pressedFor(4200)",SRC)
        self.assertNotIn("longShiftHold",SRC)
        self.assertIn("executeSelected();",SRC)
        self.assertNotIn("executeSelected(true)",SRC)
        self.assertNotIn("NEED_LONG_HOLD",SRC)
        self.assertNotIn("LARGE SHIFT",SRC)

    def test_no_second_server_confirm_for_large_shifts(self):
        self.assertIn('secureServer.on("/api/m9/run",HTTP_POST',SRC)
        self.assertIn('RunResult result=executeSelected();',SRC)
        self.assertNotIn('secureServer.arg("confirm")',SRC)
        self.assertNotIn("requires_large_confirmation",SRC)
        self.assertNotIn("allowLargeShift",SRC)
        self.assertIn("zkwire::encodeTime(target, encoded)",SRC)
        self.assertIn("verified = acknowledged && valid",SRC)

    def test_write_remains_explicit_with_verification_and_guard(self):
        self.assertIn("default_envs = m5stickc-plus-production",PIO)
        self.assertIn("ZK_ENABLE_M5_TIME_WRITE=1",PIO)
        self.assertIn("kClockWriteCooldownMs = 2000",SRC)
        self.assertIn("if (screenMode != ScreenMode::CONNECT || commandBusy)",SRC)
        self.assertIn("if (!readDeviceClock(current, error, readingMs))",SRC)
        self.assertIn("client.write(frame, sizeof(frame))",SRC)
        self.assertIn("const bool readOk = readDeviceClock(confirmed, verifyError, verifyMs);",SRC)
        self.assertIn("One tap on **Execute**",DOC)
        self.assertNotIn("on boot write",SRC)

if __name__=="__main__":unittest.main()
