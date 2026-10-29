#pragma once
// M5StickC Plus network provisioning ONLY. Does not implement terminal writes.
// Setup AP is WPA2 and shows a newly generated password on M5 display.
// Its webpage can only be accessed through the M5 AP, not campus Wi-Fi.
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <esp_system.h>

class NetworkSetup {
public:
  String ssid, password, zkIp, apSsid, apPassword;
  bool apOn = false;
  bool ready = false;
  uint32_t startedAt = 0;
  uint32_t lastAttempt = 0;

  void begin(const char* initialSsid, const char* initialPass, const char* initialIp) {
    Preferences p;
    p.begin("zk-net", false);
    ssid = p.getString("ssid", initialSsid);
    password = p.getString("pass", initialPass);
    zkIp = p.getString("zkip", initialIp);
    apPassword = p.getString("apkey", "");
    if (apPassword.length() != 14) {
      // Generate the WPA2 setup password only once, then retain it in NVS.
      // The user's iPhone can remember the same protected M5 setup SSID.
      static const char characters[] =
        "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";
      apPassword = "";
      for (int i = 0; i < 14; ++i)
        apPassword += characters[esp_random() % (sizeof(characters) - 1)];
      p.putString("apkey", apPassword);
    }
    p.end();
    startedAt = millis();
    lastAttempt = millis() - 15000;
    WiFi.setAutoReconnect(true);
    ready = true;
  }

  bool setupClient(WebServer& server) const {
    return apOn && server.client().localIP() == WiFi.softAPIP();
  }

  static String safeHtml(String str) {
    str.replace("&", "&amp;");
    str.replace("<", "&lt;");
    str.replace(">", "&gt;");
    str.replace("\"", "&quot;");
    str.replace("'", "&#39;");
    return str;
  }

  void attachRoutes(WebServer& server) {
    server.on("/setup", HTTP_GET, [this, &server]() {
      if (!setupClient(server)) {
        server.send(403, "text/plain", "Requires physical M5 setup WiFi");
        return;
      }
      String page = "<!doctype html><html lang='ar' dir='rtl'><head>"
        "<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>M5 WiFi Setup</title><style>body{font:16px system-ui;max-width:480px;"
        "margin:2em auto;padding:1em;background:#152438;color:white}"
        "input,button{display:block;width:100%;padding:12px;margin:10px 0;font:inherit}"
        "button{background:#2786bb;color:white;border:0;border-radius:8px}"
        "</style></head><body><h2>إعداد شبكة M5</h2>"
        "<p>الإعدادات فقط؛ لا يغيّر هذا الوضع ساعة جهاز البصمة.</p>"
        "<form method='post' action='/setup'>"
        "<label>اسم شبكة Wi-Fi</label><input name='ssid' maxlength='32' required value='"
        + safeHtml(ssid) + "'>"
        "<label>كلمة مرور الشبكة (فارغة للشبكة المفتوحة)</label>"
        "<input name='pass' type='password' maxlength='63' autocomplete='off'>"
        "<label>عنوان جهاز البصمة IP</label><input name='zkip' maxlength='15' required value='"
        + safeHtml(zkIp) + "'>"
        "<button type='submit'>حفظ إعدادات الاتصال</button></form>"
        "<p>تنحفظ الإعدادات حتى لو شبكة الدوام مو موجودة حالياً.</p></body></html>";
      server.sendHeader("Cache-Control", "no-store");
      server.send(200, "text/html; charset=utf-8", page);
    });
    server.on("/setup", HTTP_POST, [this, &server]() {
      if (!setupClient(server)) {
        server.send(403, "text/plain", "Requires M5 setup WiFi");
        return;
      }
      String newSsid = server.arg("ssid");
      String newPass = server.arg("pass");
      String newIp = server.arg("zkip");
      IPAddress checkedIp;
      if (!newSsid.length() || newSsid.length() > 32 ||
          newPass.length() > 63 || !checkedIp.fromString(newIp)) {
        server.send(400, "text/plain", "Invalid network settings");
        return;
      }
      Preferences p;
      p.begin("zk-net", false);
      p.putString("ssid", newSsid);
      p.putString("pass", newPass);
      p.putString("zkip", newIp);
      p.end();
      ssid = newSsid;
      password = newPass;
      zkIp = newIp;
      server.send(200, "text/html; charset=utf-8",
                  "<meta charset='utf-8'><h3>تم الحفظ</h3>"
                  "<p>معلومات الشبكة محفوظة؛ الجهاز يحاول الاتصال عند توفرها.</p>");
      WiFi.disconnect(false, false);
      lastAttempt = millis() - 15000;
    });
  }

  void startAP() {
    if (apOn) return;
    WiFi.mode(WIFI_AP_STA);
    String suffix = WiFi.macAddress();
    suffix.replace(":", "");
    apSsid = "ZK-Setup-" + suffix.substring(
      suffix.length() > 6 ? suffix.length() - 6 : 0);
    // The 14-character WPA2 secret is fixed per M5 and saved in Preferences.
    // It is displayed only on the physical M5 and never sent to campus Wi-Fi.
    if (WiFi.softAP(apSsid.c_str(), apPassword.c_str(), 6, false, 2)) {
      apOn = true;
      Serial.println("WPA2 setup AP enabled; password is on physical M5 screen.");
    } else {
      apPassword = "";
      Serial.println("ERROR: failed to activate setup AP");
    }
  }

  void stopAP() {
    if (!apOn) return;
    WiFi.softAPdisconnect(true);
    apOn = false;
    Serial.println("M5 setup AP disabled");
  }

  void tick() {
    if (!ready) return;
    if (WiFi.status() == WL_CONNECTED) return;
    if (millis() - lastAttempt >= 15000) {
      lastAttempt = millis();
      if (ssid.length()) {
        WiFi.mode(apOn ? WIFI_AP_STA : WIFI_STA);
        if (password.length() == 0) {
          WiFi.setMinSecurity(WIFI_AUTH_OPEN);
          WiFi.begin(ssid.c_str());
        } else {
          WiFi.begin(ssid.c_str(), password.c_str());
        }
      }
    }
    if (!apOn && millis() - startedAt >= 30000) startAP();
  }
};
