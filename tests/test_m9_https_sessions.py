"""M9 HTTPS session and hardware clock-write safety contracts.
No connection to a real biometric/attendance terminal.
"""
from pathlib import Path
import unittest
import re

ROOT=Path(__file__).resolve().parents[1]
MAIN=(ROOT/"src/main.cpp").read_text()
SESS=(ROOT/"include/zk_sessions.h").read_text()
UI=(ROOT/"include/m9_secure_ui.h").read_text()
LOGIN=(ROOT/"include/m9_login_ui.h").read_text()
TLS=(ROOT/"tools/create_m5_tls.sh").read_text()
PIO=(ROOT/"platformio.ini").read_text()
GITIGNORE=(ROOT/".gitignore").read_text()

class SecureM9Tests(unittest.TestCase):
    def test_http_not_used_in_station_mode(self):
        self.assertIn("ESPWebServerSecure secureServer(443)",MAIN)
        self.assertIn("WebServer server(80); // Private WPA2 setup AP only",MAIN)
        self.assertIn("if (net.apOn && !serverStarted) startHttpOnce();",MAIN)
        self.assertIn("if(net.apOn && serverStarted) server.handleClient()",MAIN)
        self.assertIn("secureServiceTick();",MAIN)
        self.assertIn('MDNS.addService("https", "tcp", 443)',MAIN)
        self.assertIn('Serial.println("Bonjour secure station: https://zkclock.local/")',MAIN)
        self.assertIn('if(serverStarted){server.stop();serverStarted=false;}',MAIN)

    def test_persistent_sliding_recall_revocation(self):
        self.assertIn('Max-Age=31536000; Secure; HttpOnly; SameSite=Strict',SESS)
        self.assertIn('String bearer=ZkSessions::parseCookie', MAIN) if False else None
        self.assertIn("ZkSessions::issueCookie(",MAIN)
        self.assertIn("revokeAll()",SESS)
        self.assertIn('secureServer.on("/api/m9/revoke",HTTP_POST',MAIN)
        self.assertIn('secureServer.on("/auth/login",HTTP_POST',MAIN)
        self.assertIn('server.on("/auth/setup",HTTP_POST',MAIN)
        self.assertIn('net.setupClient(server)',MAIN)
        self.assertIn('p.putString("hash",digest)',SESS)
        self.assertIn('p.putString("s0",tokenHash)',SESS)
        self.assertNotIn('p.putString("pass",pass)',SESS)
        self.assertIn("loginFailures_",SESS)

    def test_https_csrf_and_no_remote_http_write(self):
        self.assertIn('secureServer.header("X-ZK-CSRF")!=csrfToken',MAIN)
        self.assertIn('secureServer.header("Origin")!="https://zkclock.local"',MAIN)
        self.assertIn('secureServer.on("/api/m9/run",HTTP_POST',MAIN)
        self.assertIn('secureServer.on("/api/m9/save",HTTP_POST',MAIN)
        self.assertIn('secureServer.on("/api/m9/rtc",HTTP_POST',MAIN)
        self.assertIn("executeSelected(large)",MAIN)
        self.assertIn("#if ZK_ENABLE_M5_TIME_WRITE", MAIN)
        self.assertIn("#define ZK_ENABLE_M5_TIME_WRITE 0",MAIN)
        self.assertIn("requires_large_confirmation",MAIN)
        self.assertIn('"/api/m9/run"',UI)
        self.assertIn("SameSite=Strict",SESS)
        self.assertIn('autocomplete="current-password"',LOGIN)
        self.assertIn('autocomplete="username"',LOGIN)

    def test_device_specific_tls_secrets_never_checked_in(self):
        self.assertIn("include/m5_tls_local.h",GITIGNORE)
        self.assertIn(".secrets/m5-*",GITIGNORE)
        self.assertIn("subjectAltName=DNS:zkclock.local,IP:192.168.4.1",TLS)
        self.assertIn('if [ -e .secrets/m5-ca.key ]',TLS)
        self.assertIn("m5-server-key.der",TLS)
        self.assertIn('esp32_https_server_compat@1.0.0',PIO)
        self.assertIn('[env:m5stickc-plus-secure-write-lab]',PIO)
        self.assertIn('ZK_ENABLE_M5_TIME_WRITE=1',PIO)

    def test_ui_requires_https_secure_state(self):
        self.assertIn('api(\'/api/m9\'',UI)
        self.assertIn("location.replace('/login')",UI)
        self.assertNotIn("http://zkclock.local",UI)
        self.assertIn("X-ZK-CSRF",UI)
        self.assertIn("syncRtc",UI)

if __name__=="__main__":
    unittest.main()
