"""M12 physical feedback regression: AP domain DNS, rich delete UI, 700ms B."""
from pathlib import Path
import unittest

R=Path(__file__).resolve().parents[1]
SRC=(R/"src/main.cpp").read_text()
PRE=(R/"include/m5_presets.h").read_text()
NAV=(R/"include/web_navigation.h").read_text()
PIO=(R/"platformio.ini").read_text()
NET=(R/"include/network_setup.h").read_text()

class M12HardwareFeedback(unittest.TestCase):
    def test_setup_dns_is_ap_only_and_https_is_unchanged(self):
        self.assertIn("#include <DNSServer.h>",SRC)
        self.assertIn("DNSServer setupDns;",SRC)
        self.assertIn('setupDns.start(53,"zkclock.local",WiFi.softAPIP())',SRC)
        self.assertIn("setupDns.processNextRequest()",SRC)
        self.assertIn("if (screenMode==ScreenMode::SETUP && net.apOn && setupDnsRunning)",SRC)
        self.assertIn("stopSetupDns();",SRC)
        self.assertIn('MDNS.begin("zkclock")',SRC)
        self.assertIn('MDNS.addService("https","tcp",443)',SRC)
        self.assertIn("ESPWebServerSecure secureServer(443)",SRC)
        self.assertNotIn("WebServer server(80)",SRC)
        self.assertIn('https://192.168.4.1',NET)

    def test_shortcuts_have_real_delete_add_save_with_no_blank_required_inputs(self):
        self.assertIn('if(!net.setupClient(server))',PRE)
        self.assertIn('class=\'shortcut-row\' data-shortcut=',PRE)
        self.assertIn("deleteShortcut(this)",PRE)
        self.assertIn("function deleteShortcut(btn)",PRE)
        self.assertIn("function addShortcut()",PRE)
        self.assertIn("updateShortcutCount()",PRE)
        self.assertIn("input.value='';input.disabled=true;",PRE)
        self.assertIn("input.disabled=false",PRE)
        self.assertIn("حفظ الاختصارات",PRE)
        self.assertIn("if (name.isEmpty() && value.isEmpty()) continue;",PRE)
        self.assertIn("values[n++] = {name, value};",PRE)

    def test_setup_looks_like_connect(self):
        self.assertIn(".tabs{position:sticky",NAV)
        self.assertIn(".shortcut",PRE)
        self.assertIn("button.danger",NAV)
        self.assertIn("fieldset[hidden]{display:none}",NAV)
        self.assertIn("class='tabs'",NAV)
        self.assertIn("href='/auth/setup'",NAV)

    def test_short_b_press_still_requires_held_not_tap_or_wake(self):
        self.assertIn("M5.BtnB.pressedFor(700)",SRC)
        self.assertNotIn("M5.BtnB.pressedFor(2200)",SRC)
        self.assertIn("wakeBlockUntilRelease = true;",SRC)
        self.assertIn("if (wakeBlockUntilRelease)",SRC)
        self.assertIn("if (!buttonBLatched && M5.BtnB.pressedFor(700))",SRC)
        self.assertIn("buttonBLatched = true;",SRC)
        self.assertIn("executeSelected();",SRC)
        self.assertIn("kClockWriteCooldownMs = 2000",SRC)
        self.assertIn("default_envs = m5stickc-plus-production",PIO)

if __name__=="__main__":
    unittest.main()
