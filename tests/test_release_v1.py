"""Release v1.0.0 production regression guards; offline only."""
from pathlib import Path
import unittest

R=Path(__file__).resolve().parents[1]
SRC=(R/"src/main.cpp").read_text()
UI=(R/"include/m9_secure_ui.h").read_text()
ZK=(R/"include/zk_wire.h").read_text()
WORKFLOW=(R/".github/workflows/m2-readonly.yml").read_text()
PLAT=(R/"platformio.ini").read_text()

class ReleaseSafety(unittest.TestCase):
    def test_secure_home_routes_and_public_pwa(self):
        self.assertIn("await api('/api/m9/read')",UI)
        self.assertNotIn("await api('/api/read')",UI)
        self.assertIn('secureServer.on("/api/m9/read",HTTP_GET',SRC)
        self.assertIn('secureServer.on("/manifest.webmanifest",HTTP_GET',SRC)
        self.assertIn('secureServer.on("/icon.svg",HTTP_GET',SRC)
        self.assertIn('secureServer.on("/",HTTP_GET',SRC)
        self.assertIn('M9_HOME',SRC)
        self.assertNotIn('<a href="/setup"',UI)
        self.assertNotIn('<a href="/rtc"',UI)

    def test_no_unqualified_auto_writes_and_cooldown(self):
        self.assertIn('#define ZK_ENABLE_M5_TIME_WRITE 0',SRC)
        self.assertIn('constexpr uint32_t kClockWriteCooldownMs = 2000',SRC)
        self.assertIn('hasClockWriteAttempt = true',SRC)
        self.assertIn('millis() - lastClockWriteAttempt < kClockWriteCooldownMs',SRC)
        self.assertIn('if (selectedPreset == stored.count && !rtcClock.trustworthy(target))',SRC)
        self.assertIn('verified = acknowledged && valid',SRC)
        self.assertIn('RunResult result=executeSelected();',SRC)
        self.assertNotIn('requires_large_confirmation',SRC)
        self.assertIn('statusLine = verified ? "CLOCK VERIFIED" : "UNVERIFIED: CHECK ZKTeco"',SRC)
        self.assertNotIn('setInterval(()=>api("/api/m9/run"',UI)
        self.assertIn('if (screenMode != ScreenMode::CONNECT || commandBusy)',SRC)

    def test_wire_matches_pyzk_semantics(self):
        self.assertIn('put16(zk + 2, checksum(zk, sizeof(zk)));',ZK)
        self.assertIn('put16(zk + 6, uint16_t(nextId));',ZK)
        self.assertIn('makeSetTimeFrame',ZK)
        self.assertIn('0xca,0x00,0xb2,0x6e', (R/"tests/zk_write_host.cpp").read_text())

    def test_release_compilation_targets_and_crypto(self):
        self.assertIn('board_build.partitions = huge_app.csv',PLAT)
        self.assertIn('default_envs = m5stickc-plus-production',PLAT)
        self.assertIn('[env:m5stickc-plus-production]',PLAT)
        self.assertIn('[env:m5stickc-plus-secure-write-lab]',PLAT)
        self.assertIn('test_release_v1.py',WORKFLOW)
        self.assertIn('release/v1.0.0-full-control',WORKFLOW)
        self.assertIn('m5_tls_local.h', (R/".gitignore").read_text())
        self.assertTrue((R/"docs/RELEASE_V1_RC1.md").exists())

if __name__=="__main__":
    unittest.main()
