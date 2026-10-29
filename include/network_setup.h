#pragma once
// M5StickC Plus network provisioning ONLY. Does not implement terminal writes.
// Setup AP is WPA2 and shows a newly generated password on M5 display.
// Its webpage can only be accessed through the M5 AP, not campus Wi-Fi.
#include <Arduino.h>
#include <WiFi.h>
#include <ESPWebServer.hpp>
using WebServer = ESPWebServer;
#include <Preferences.h>
#include <esp_system.h>
#include "web_navigation.h"
#include "screen_idle.h"

class NetworkSetup {
public:
  String ssid, password, zkIp, apSsid, apPassword;
  String savedApName;
  bool apOn = false;
  bool ready = false;
  uint32_t lastAttempt = 0;

  void begin(const char* initialSsid, const char* initialPass, const char* initialIp) {
    Preferences p;
    p.begin("zk-net", false);
    ssid = p.getString("ssid", initialSsid);
    password = p.getString("pass", initialPass);
    zkIp = p.getString("zkip", initialIp);
    savedApName = p.getString("apname", "");
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
    lastAttempt = millis() - 15000;
    WiFi.setAutoReconnect(true);
    ready = true;
  }

  String currentApName() const {
    if (savedApName.length()) return savedApName;
    if (apSsid.length()) return apSsid;
    String suffix=WiFi.macAddress();
    suffix.replace(":","");
    return "ZK-Setup-" + suffix.substring(suffix.length()>6 ? suffix.length()-6 : 0);
  }

  bool setupClient(WebServer& server) const {
    // Port 80 is started only while physically selected SETUP AP is active.
    // HTTPS station is a separate TLS-only listener on port 443.
    (void)server;
    return apOn;
  }

  static String safeHtml(String str) {
    str.replace("&", "&amp;");
    str.replace("<", "&lt;");
    str.replace(">", "&gt;");
    str.replace("\"", "&quot;");
    str.replace("'", "&#39;");
    return str;
  }

  void attachRoutes(WebServer& server, ScreenIdle& idle) {
    server.on("/setup", HTTP_GET, [this, &server, &idle]() {
      const bool editable = setupClient(server);
      String page = zkPageBegin("إعدادات M5");
      page += "<p>الحالة: <b>" + String(editable ? "شبكة الإعداد الآمنة" : "الاتصال بالشبكة") + "</b></p>";
      page += "<p>الشبكة الحالية: <b>" + safeHtml(ssid) + "</b></p>";
      page += "<p>عنوان البصمة: <b dir='ltr'>" + safeHtml(zkIp) + "</b></p>";
      page += "<p>اسم شبكة إعداد M5: <b dir='ltr'>" + safeHtml(
        currentApName()) + "</b></p>";
      page += "<p>إطفاء الشاشة بعد: <b>" + String(idle.timeout()) +
        " ثانية (0 = دائماً مضاءة)</b></p>";
      if (editable) {
        page += "<p>التعديلات الحساسة متاحة فقط عند اتصالك بشبكة إعداد M5 المحمية بكلمة مرور.</p>"
          "<form method='post' action='/setup'>"
          "<label>اسم Wi-Fi اللي يتصل بيها M5</label><input name='ssid' maxlength='32' required value='"
          + safeHtml(ssid) + "'>"
          "<label>كلمة مرور Wi-Fi (اتركها فارغة للاحتفاظ بالقديمة إذا نفس الشبكة)</label>"
          "<input name='pass' type='password' maxlength='63' autocomplete='new-password'>"
          "<label><input type='checkbox' name='open' value='1' style='width:auto'>"
          " شبكة مفتوحة بدون كلمة مرور</label>"
          "<label>عنوان IP جهاز البصمة</label><input name='zkip' maxlength='15' value='"
          + safeHtml(zkIp) + "' required>"
          "<label>اسم شبكة إعداد M5 (حروف إنكليزية أو أرقام أو - أو _)</label>"
          "<input name='apname' maxlength='24' value='" +
          safeHtml(currentApName()) +
          "' required>"
          "<label>نوم الشاشة بعد فترة عدم استخدام</label>"
          "<select id='idle' name='idle' style='display:block;width:100%;padding:12px'>"
          "<option value='15'>15 ثانية</option><option value='30'>30 ثانية</option>"
          "<option value='60'>دقيقة</option><option value='120'>دقيقتين</option>"
          "<option value='0'>بدون نوم</option></select>"
          "<button type='submit'>حفظ الإعدادات</button></form>";
        page += "<script>document.getElementById('idle').value='" +
          String(idle.timeout()) + "';</script>";
      } else {
        page += "<p style='background:#393023;padding:12px'>للتعديل: اضغط A مطولاً "
          "على M5 للعودة لقائمة البداية، ثم A لاختيار SETUP، واتصل بشبكته "
          "الآمنة وافتح <b>192.168.4.1/setup</b>. لا يمكن تعديل "
          "بيانات Wi-Fi عبر شبكة الجامعة المفتوحة.</p>";
      }
      page += zkPageEnd();
      server.sendHeader("Cache-Control","no-store");
      server.send(200,"text/html; charset=utf-8",page);
    });
    server.on("/setup", HTTP_POST, [this, &server, &idle]() {
      if (!setupClient(server)) {
        server.send(403, "text/plain", "Changes require protected M5 setup WiFi"); return;
      }
      String newSsid = server.arg("ssid");
      String newPass = server.arg("pass");
      bool useOpenNetwork = server.hasArg("open");
      if (!newPass.length() && !useOpenNetwork && newSsid == ssid)
        newPass = password;
      if ((!newPass.length() && !useOpenNetwork && newSsid != ssid) ||
          (useOpenNetwork && newPass.length())) {
        server.send(400, "text/plain",
                    "Provide password or mark new network as open");
        return;
      }
      String newIp = server.arg("zkip");
      String newName = server.arg("apname");
      String timeoutText = server.arg("idle");
      IPAddress checkedIp;
      bool validName = newName.length() >= 4 && newName.length() <= 24;
      for (unsigned i=0; i<newName.length(); ++i) {
        char c=newName[i];
        if (!((c>='A'&&c<='Z') || (c>='a'&&c<='z') ||
              (c>='0'&&c<='9') || c=='-' || c=='_'))
          validName=false;
      }
      uint16_t timeoutValue = 65535;
      if (timeoutText=="0") timeoutValue=0;
      else if (timeoutText=="15") timeoutValue=15;
      else if (timeoutText=="30") timeoutValue=30;
      else if (timeoutText=="60") timeoutValue=60;
      else if (timeoutText=="120") timeoutValue=120;
      if (!newSsid.length() || newSsid.length()>32 || newPass.length()>63 ||
          !checkedIp.fromString(newIp) || !validName ||
          !ScreenIdle::valid(timeoutValue)) {
        server.send(400, "text/plain", "Invalid WiFi / AP name / timeout"); return;
      }
      Preferences p;
      if (!p.begin("zk-net", false)) {
        server.send(500, "text/plain", "Storage unavailable"); return;
      }
      p.putString("ssid", newSsid);
      p.putString("pass", newPass);
      p.putString("zkip", newIp);
      p.putString("apname", newName);
      p.end();
      if (!idle.save(timeoutValue)) {
        server.send(500,"text/plain","Screen timeout storage failed"); return;
      }
      ssid=newSsid;
      password=newPass;
      zkIp=newIp;
      savedApName=newName;
      // Keep the live AP name intact until the operator exits and reenters
      // SETUP mode; changing it mid-request would disconnect the browser.
      String page=zkPageBegin("تم الحفظ");
      page += "<p>تم حفظ شبكة الاتصال واسم شبكة الإعداد والتوقيت.</p>"
              "<p>اسم شبكة الإعداد الجديد يتفعّل بعد إيقاف SETUP وإعادة الدخول إليه "
              "من أزرار M5. إذا تغيّر الاسم، اختاره مجدداً من Wi-Fi في الآيفون.</p>"
              "<a href='/setup'>رجوع للإعدادات</a>" + zkPageEnd();
      server.sendHeader("Cache-Control","no-store");
      server.send(200,"text/html; charset=utf-8",page);
      lastAttempt=millis()-15000;
    });

  }

  void startAP() {
    if (apOn) return;
    WiFi.mode(WIFI_AP);
    String suffix = WiFi.macAddress();
    suffix.replace(":", "");
    apSsid = savedApName.length() ? savedApName :
      "ZK-Setup-" + suffix.substring(
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
    WiFi.mode(WIFI_STA);
    lastAttempt = millis() - 15000;
    Serial.println("M5 setup AP disabled");
  }

  void tick() {
    if (!ready || apOn) return;
    if (WiFi.status() == WL_CONNECTED) return;
    if (millis() - lastAttempt >= 15000) {
      lastAttempt = millis();
      if (ssid.length()) {
        WiFi.mode(WIFI_STA);
        if (password.length() == 0) {
          WiFi.setMinSecurity(WIFI_AUTH_OPEN);
          WiFi.begin(ssid.c_str());
        } else {
          WiFi.begin(ssid.c_str(), password.c_str());
        }
      }
    }
  }
};
