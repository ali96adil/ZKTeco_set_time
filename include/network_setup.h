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
  String ssid, password, secondarySsid, secondaryPassword, zkIp, apSsid, apPassword;
  bool secondaryEnabled = false;
  uint8_t nextNetwork = 0;
  String savedApName;
  bool apOn = false;
  bool ready = false;
  uint32_t lastAttempt = 0;

  void begin(const char* initialSsid, const char* initialPass, const char* initialIp) {
    Preferences p;
    p.begin("zk-net", false);
    ssid = p.getString("ssid", initialSsid);
    password = p.getString("pass", initialPass);
    secondarySsid = p.getString("ssid2", "StuAct");
    secondaryPassword = p.getString("pass2", "");
    secondaryEnabled = p.getBool("backupOn", false);
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
    // Firmware owns failover timing: the SDK must not race an auto-reconnect.
    WiFi.setAutoReconnect(false);
    ready = true;
  }

  String currentApName() const {
    if (savedApName.length()) return savedApName;
    if (apSsid.length()) return apSsid;
    String suffix=WiFi.macAddress();
    suffix.replace(":","");
    return "ZK-Setup-" + suffix.substring(suffix.length()>6 ? suffix.length()-6 : 0);
  }

  // SETUP is physically selected, AP-only WPA2, served by the SAME
  // HTTPS listener/certificate/hostname as CONNECT. No HTTP credential path.
  bool setupClient(WebServer& server) const {
    if (!apOn) return false;
    if (server.method() != HTTP_POST) return true;
    const String origin=server.header("Origin");
    return origin=="https://zkclock.local" ||
           origin=="https://192.168.4.1";
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
      if (!setupClient(server)) {
        server.send(403,"text/plain","SETUP AP only");return;
      }
      const bool editable = true;
      String page = zkPageBegin("إعدادات M5");
      page += "<p><b>https://192.168.4.1/setup</b> — الرابط الثابت بوضع SETUP على شبكة الـM5.</p>"
        "<p>رابط https://zkclock.local/setup يعتمد على Bonjour؛ إذا ما يفتح استعمل عنوان الـIP أعلاه.</p>"
        "<p><a href='/auth/setup'>إدارة حساب الدخول</a> | <a href='/presets'>الاختصارات</a> | "
        "<a href='/rtc'>RTC</a></p>";
      page += R"BATT(<p id="batteryStatus">بطارية M5: جاري القراءة…</p>
<script>
fetch('/api/battery',{cache:'no-store'}).then(r=>r.json()).then(b=>{
 const element=document.getElementById('batteryStatus');
 element.textContent=b.percent_approx>=0
  ? 'بطارية M5: حوالي '+b.percent_approx+'% ('+(b.voltage_mv/1000).toFixed(2)+'V)'+(b.usb_power?' • USB متصل':'')
  : 'بطارية M5: القراءة غير متاحة';
}).catch(()=>{document.getElementById('batteryStatus').textContent='تعذرت قراءة البطارية';});
</script>)BATT";
      page += "<p>الحالة: <b>" + String(editable ? "شبكة الإعداد الآمنة" : "الاتصال بالشبكة") + "</b></p>";
      page += "<p>الشبكة الأساسية: <b>" + safeHtml(ssid) + "</b></p>";
      page += "<p>الشبكة الاحتياطية: <b>" + safeHtml(secondarySsid) +
        (secondaryEnabled ? " (مفعّلة)" : " (غير مفعّلة — تحتاج كلمة المرور أو تحديد مفتوحة)") + "</b></p>";
      if (WiFi.status()==WL_CONNECTED)
        page += "<p>المتصلة الآن: <b>" + safeHtml(WiFi.SSID()) + "</b></p>";
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
          "<label>الشبكة الثانية (احتياطية)</label>"
          "<input name='ssid2' maxlength='32' value='" + safeHtml(secondarySsid) + "'>"
          "<label>كلمة مرور الشبكة الثانية (اتركها فارغة للاحتفاظ بها إذا نفس الاسم)</label>"
          "<input name='pass2' type='password' maxlength='63' autocomplete='new-password'>"
          "<label><input type='checkbox' name='open2' value='1' style='width:auto'"
          + String(secondaryEnabled && !secondaryPassword.length() ? " checked" : "") +
          "> الشبكة الثانية مفتوحة بدون كلمة مرور</label>"
          "<p>الأولوية للأولى. إذا تعذر اتصالها تُجرّب الثانية. شبكة StuAct تحتاج إعداد كلمة مرورها هنا إن كانت محمية.</p>"
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
          "الآمنة وافتح <b>https://zkclock.local/setup</b>. لا يمكن تعديل "
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
      String newSecondarySsid = server.arg("ssid2");
      String newSecondaryPass = server.arg("pass2");
      bool secondaryOpen = server.hasArg("open2");
      newSecondarySsid.trim();
      // Blank password preserves the previous secret for an unchanged SSID.
      if (!newSecondaryPass.length() && newSecondarySsid == secondarySsid) {
        newSecondaryPass = secondaryPassword;
        if (secondaryEnabled && !secondaryPassword.length()) secondaryOpen = true;
      }
      if (!newSecondarySsid.length()) {
        newSecondaryPass = "";
        secondaryOpen = false;
      }
      const bool enableSecondary = newSecondarySsid.length() &&
        (secondaryOpen || newSecondaryPass.length());
      if ((secondaryOpen && newSecondaryPass.length()) ||
          newSecondarySsid == newSsid) {
        server.send(400, "text/plain", "Invalid secondary WiFi settings");
        return;
      }
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
          newSecondarySsid.length()>32 || newSecondaryPass.length()>63 ||
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
      p.putString("ssid2", newSecondarySsid);
      p.putString("pass2", newSecondaryPass);
      p.putBool("backupOn", enableSecondary);
      p.putString("zkip", newIp);
      p.putString("apname", newName);
      p.end();
      if (!idle.save(timeoutValue)) {
        server.send(500,"text/plain","Screen timeout storage failed"); return;
      }
      ssid=newSsid;
      password=newPass;
      secondarySsid=newSecondarySsid;
      secondaryPassword=newSecondaryPass;
      secondaryEnabled=enableSecondary;
      nextNetwork=0;
      zkIp=newIp;
      savedApName=newName;
      // Keep the live AP name intact until the operator exits and reenters
      // SETUP mode; changing it mid-request would disconnect the browser.
      String page=zkPageBegin("تم الحفظ");
      page += "<p>تم حفظ الشبكتين واسم شبكة الإعداد والتوقيت. إذا تعذرت الأولى سيحاول M5 الشبكة الاحتياطية.</p>"
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
    if (WiFi.status() == WL_CONNECTED) {
      // Stay on the working network. Never interrupt an active operator session.
      return;
    }
    if (millis() - lastAttempt < 12000) return;
    lastAttempt = millis();
    const bool hasPrimary = ssid.length() > 0;
    const bool hasBackup = secondaryEnabled && secondarySsid.length() > 0;
    if (!hasPrimary && !hasBackup) return;

    // On startup try primary first; on failure alternate with secondary.
    bool backup = hasBackup && (!hasPrimary || (nextNetwork & 1u));
    if (hasPrimary && hasBackup) ++nextNetwork;
    else nextNetwork = 0;
    const String &targetSsid = backup ? secondarySsid : ssid;
    const String &targetPass = backup ? secondaryPassword : password;
    WiFi.mode(WIFI_STA);
    WiFi.disconnect(false, false);
    WiFi.setMinSecurity(WIFI_AUTH_OPEN);
    if (targetPass.length()) WiFi.begin(targetSsid.c_str(), targetPass.c_str());
    else WiFi.begin(targetSsid.c_str());
    Serial.println(String("WiFi attempting ") + (backup ? "backup: " : "primary: ") + targetSsid);

  }
};
