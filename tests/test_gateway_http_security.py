"""HTTPS authorization/CSRF regression; local fake clock only."""
import base64
from datetime import datetime
import http.client
from pathlib import Path
import ssl
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from mac_live_control import Gateway


class LocalHttpSecurityTests(unittest.TestCase):
    def test_https_authentication_and_csrf(self):
        def unavailable_write(value):
            self.fail("No device clock write should occur during this test")
        server = Gateway(("127.0.0.1", 0), device_host="192.0.2.10",
                         device_port=4370, password="testing", enable_write=True,
                         reader=lambda: datetime(2026, 10, 29, 12, 0),
                         setter=unavailable_write)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(ROOT / ".secrets/mac.crt"),
                            str(ROOT / ".secrets/mac.key"))
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        def req(method, path, headers=None, body=None):
            client = http.client.HTTPSConnection(
                "127.0.0.1", port, timeout=5,
                context=ssl._create_unverified_context())
            try:
                client.request(method, path, body=body, headers=headers or {})
                response = client.getresponse()
                response.read()
                return response.status
            finally:
                client.close()
        auth = "Basic " + base64.b64encode(b"operator:testing").decode()
        try:
            self.assertEqual(req("GET", "/"), 401)
            self.assertEqual(req("GET", "/", {"Authorization": auth}), 200)
            self.assertEqual(req("POST", "/api/prepare", {
                "Authorization": auth,
                "Origin": "https://127.0.0.1:%d" % port,
                "Content-Type": "application/json",
            }, '{"source":"manual"}'), 403)
            self.assertEqual(req("POST", "/api/apply", {
                "Authorization": auth,
                "Origin": "https://127.0.0.1:%d" % port,
                "X-CSRF-Token": "incorrect",
                "Content-Type": "application/json",
            }, "{}"), 403)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
