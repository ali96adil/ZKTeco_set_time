"""TLS phone enrollment and saved shortcut API test; no ZKTeco I/O."""
import http.client
import json
from datetime import datetime
from pathlib import Path
import ssl
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from mac_live_control import Gateway


class PhoneWebTests(unittest.TestCase):
    def test_pair_once_and_restore_cookie(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            gate=Gateway(("127.0.0.1",0),device_host="192.0.2.10",
                device_port=4370,password="fallback",
                enable_write=False,allow_pairing=True,
                pairing_path=p/"phones.json",
                shortcut_path=p/"shortcuts.json",
                reader=lambda:datetime(2026,10,29,14,0,0),
                setter=lambda dt:self.fail("Read-only gate should never set time"))
            tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(str(ROOT/".secrets/mac.crt"),
                                str(ROOT/".secrets/mac.key"))
            gate.socket=tls.wrap_socket(gate.socket,server_side=True)
            thread=threading.Thread(target=gate.serve_forever,daemon=True)
            thread.start()
            port=gate.server_address[1]
            origin=f"https://127.0.0.1:{port}"
            def request(method,path,body=None,cookie=None,csrf=None):
                c=http.client.HTTPSConnection("127.0.0.1",port,
                         context=ssl._create_unverified_context(),timeout=5)
                headers={"Origin":origin}
                if cookie:headers["Cookie"]=cookie
                if csrf:headers["X-CSRF-Token"]=csrf
                if body is not None:headers["Content-Type"]="application/json"
                try:
                    c.request(method,path,body=None if body is None else json.dumps(body),
                              headers=headers)
                    r=c.getresponse()
                    return r.status,r.read(),r.getheader("Set-Cookie")
                finally:
                    c.close()
            try:
                status,html,_=request("GET","/")
                self.assertEqual(status,200)
                self.assertIn(b"/api/pair",html)
                status,_,cookie=request("POST","/api/pair",{"code":gate.pairing.code})
                self.assertEqual(status,200)
                self.assertIn("__Host-zk_operator",cookie)
                self.assertIn("HttpOnly",cookie)
                self.assertIn("SameSite=Strict",cookie)
                status,html,_=request("GET","/",cookie=cookie)
                self.assertEqual(status,200)
                self.assertIn(b"quickPanel",html)
                status,raw,_=request("GET","/api/shortcuts",cookie=cookie)
                self.assertEqual(status,200)
                self.assertEqual(json.loads(raw)["items"][0]["kind"],"phone")
                status,_,_=request("POST","/api/shortcuts",
                    {"items":[{"id":"sync","name":"Sync","kind":"phone","value":""}]},
                    cookie=cookie)
                self.assertEqual(status,403) # CSRF header missing
                status,_,_=request("POST","/api/shortcuts",
                    {"items":[{"id":"sync","name":"Sync","kind":"phone","value":""}]},
                    cookie=cookie,csrf=gate.csrf_token)
                self.assertEqual(status,200)
            finally:
                gate.shutdown()
                thread.join(timeout=5)
                gate.server_close()


if __name__=="__main__":
    unittest.main()
