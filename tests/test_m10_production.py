"""M10 production contract. Offline only; no physical time changes."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/"src/main.cpp").read_text()
NET=(ROOT/"include/network_setup.h").read_text()
PRE=(ROOT/"include/m5_presets.h").read_text()
RTC=(ROOT/"include/m5_rtc.h").read_text()
UI=(ROOT/"include/m9_secure_ui.h").read_text()
PIO=(ROOT/"platformio.ini").read_text()
TLS=(ROOT/"tools/create_m5_tls.sh").read_text()
SESS=(ROOT/"include/zk_sessions.h").read_text()

class ProductionContracts(unittest.TestCase):
    def test_full_write_default(self):
        self.assertIn("default_envs = m5stickc-plus-production",PIO)
        self.assertIn("[env:m5stickc-plus-production]",PIO)
        self.assertIn("build_flags = -DZK_ENABLE_M5_TIME_WRITE=1",PIO)
        self.assertIn('secureServer.on("/api/m9/run",HTTP_POST',SRC)
        self.assertIn('executeSelected()',SRC)
        self.assertIn('M5.BtnB.pressedFor(700)',SRC)
        self.assertIn('makeSetTimeFrame(session, reply.replyId, encoded, frame)',SRC)
        self.assertIn("verified = acknowledged && valid",SRC)
        self.assertIn("if (selectedPreset == stored.count && !rtcClock.trustworthy(target))",SRC)
        self.assertNotIn("setInterval(()=>",UI)
        self.assertNotIn("confirm(",UI.split("function drawHome()",1)[1].split("function drawEditor()",1)[0])

    def test_cooldown_two_seconds_after_attempt_completion(self):
        self.assertIn("kClockWriteCooldownMs = 2000",SRC)
        self.assertIn("millis() - lastClockWriteAttempt < kClockWriteCooldownMs",SRC)
        self.assertIn("struct AttemptFinished",SRC)
        self.assertIn("~AttemptFinished() { stamp=millis(); }",SRC)
        self.assertIn("WRITE COOLDOWN 2S",SRC)
        self.assertNotIn("WRITE COOLDOWN 10S",SRC)

    def test_identical_https_name_and_cert_station_and_setup(self):
        self.assertIn('ESPWebServerSecure secureServer(443)',SRC)
        self.assertNotIn('WebServer server(80)',SRC)
        self.assertNotIn('startHttpOnce',SRC)
        self.assertIn('MDNS.addService("https","tcp",443)',SRC)
        self.assertIn('MDNS.addService("https", "tcp", 443)',SRC)
        self.assertIn("screenMode==ScreenMode::SETUP && net.apOn",SRC)
        self.assertIn("screenMode==ScreenMode::CONNECT && WiFi.status()==WL_CONNECTED",SRC)
        self.assertIn('secureServer.on("/auth/setup",HTTP_GET',SRC)
        self.assertIn('secureServer.on("/auth/setup",HTTP_POST',SRC)
        self.assertIn('secureServer.sendHeader("Location","/setup")',SRC)
        self.assertIn('net.attachRoutes(secureServer,screenIdle)',SRC)
        self.assertIn('https://zkclock.local/setup',NET)
        self.assertIn('https://192.168.4.1',NET)
        self.assertIn("subjectAltName=DNS:zkclock.local,IP:192.168.4.1",TLS)
        self.assertIn('M5.Lcd.drawString("https://zkclock.local"',SRC)

    def test_setup_mutations_physically_bound_and_origin_guarded(self):
        self.assertIn('if (!apOn) return false;',NET)
        self.assertIn('origin=="https://zkclock.local"',NET)
        self.assertIn('origin=="https://192.168.4.1"',NET)
        self.assertIn("if (!setupClient(server))",NET)
        self.assertIn("if (!net.setupClient(server))",PRE)
        self.assertIn("if (!net.setupClient(server))",RTC)
        self.assertIn("if(!net.setupClient(server))",PRE)
        self.assertNotIn("localArm.grant()",SRC)
        self.assertIn('secureServer.header("X-ZK-CSRF")!=csrfToken',SRC)
        self.assertIn('Max-Age=31536000; Secure; HttpOnly; SameSite=Strict',SESS)
        self.assertIn('revokeAll()',SESS)

    def test_pwa_and_session_persist(self):
        self.assertIn('secureServer.on("/manifest.webmanifest",HTTP_GET',SRC)
        self.assertIn('secureServer.on("/icon.svg",HTTP_GET',SRC)
        self.assertIn("await api('/api/m9/read')",UI)
        self.assertIn("await api('/api/m9/run'",UI)
        self.assertIn("'/api/m9/rtc'",UI)
        self.assertIn("location.replace('/login')",UI)
        self.assertIn("syncRtc",UI)

if __name__=="__main__":unittest.main()
