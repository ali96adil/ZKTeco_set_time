#pragma once
// Exact civil date+time button presets, stored locally in ESP32 Preferences.
// The editor is available only from the M5 WPA2 provisioning AP.
// It does not expose a remote write endpoint to the campus Wi-Fi.
#include <Arduino.h>
#include <Preferences.h>
#include <WebServer.h>
#include "network_setup.h"

struct M5Preset {
  String name;
  String datetime;
};

class M5Presets {
 public:
  static constexpr uint8_t kMax = 8;
  M5Preset items[kMax];
  uint8_t count = 0;

  static bool validDateTime(const String& dt) {
    if (dt.length() != 19 || dt[4] != '-' || dt[7] != '-' ||
        dt[10] != 'T' || dt[13] != ':' || dt[16] != ':') return false;
    for (uint8_t i = 0; i < 19; ++i) {
      if (i == 4 || i == 7 || i == 10 || i == 13 || i == 16) continue;
      if (dt[i] < '0' || dt[i] > '9') return false;
    }
    int year = dt.substring(0, 4).toInt();
    int month = dt.substring(5, 7).toInt();
    int day = dt.substring(8, 10).toInt();
    int hour = dt.substring(11, 13).toInt();
    int minute = dt.substring(14, 16).toInt();
    int second = dt.substring(17, 19).toInt();
    if (year < 2000 || year > 2099 || month < 1 || month > 12 ||
        hour > 23 || minute > 59 || second > 59) return false;
    const uint8_t days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
    bool leap = (year % 4 == 0 && (year % 100 != 0 || year % 400 == 0));
    int maximum = month == 2 && leap ? 29 : days[month - 1];
    return day >= 1 && day <= maximum;
  }

  void load() {
    Preferences p;
    p.begin("zk-presets", true);
    count = min(p.getUChar("count", 0), kMax);
    for (uint8_t i=0; i<kMax; ++i) {
      items[i].name = "";
      items[i].datetime = "";
    }
    for (uint8_t i=0; i<count; ++i) {
      String n = String("name") + i, v = String("when") + i;
      items[i].name = p.getString(n.c_str(), "");
      items[i].datetime = p.getString(v.c_str(), "");
      if (!validDateTime(items[i].datetime)) {
        count = i;
        break;
      }
    }
    p.end();
  }

  bool save(M5Preset* proposed, uint8_t n) {
    if (n > kMax) return false;
    for (uint8_t i=0; i<n; ++i) {
      if (proposed[i].name.length() < 1 || proposed[i].name.length() > 24 ||
          !validDateTime(proposed[i].datetime)) return false;
    }
    Preferences p;
    if (!p.begin("zk-presets", false)) return false;
    for (uint8_t i=0; i<kMax; ++i) {
      String keyName = String("name") + i, keyValue = String("when") + i;
      p.putString(keyName.c_str(), i<n ? proposed[i].name : "");
      p.putString(keyValue.c_str(), i<n ? proposed[i].datetime : "");
    }
    p.putUChar("count", n);
    p.end();
    load();
    return true;
  }

  void routes(WebServer& server, NetworkSetup& net) {
    server.on("/presets", HTTP_GET, [this, &server, &net]() {
      if (!net.setupClient(server)) {
        server.send(403, "text/plain", "Connect to M5 setup AP"); return;
      }
      String page = "<!doctype html><html lang='ar' dir='rtl'><head>"
        "<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>M5 commands</title><style>body{font:16px system-ui;max-width:500px;"
        "margin:2em auto;padding:1em;background:#142338;color:white}"
        "input,button{display:block;width:100%;padding:10px;margin:9px 0;font:inherit}"
        "button{background:#2984bb;color:white;border:0}</style></head><body>"
        "<h2>أوامر التاريخ والوقت</h2><p>كل زر يحفظ التاريخ والساعة معاً."
        " لا توجد أوامر تاريخ فقط أو ساعة فقط.</p>"
        "<form method='post' action='/presets'>";
      for (uint8_t i=0; i<kMax; ++i) {
        page += "<fieldset><legend>اختصار " + String(i+1) + "</legend>"
          "<input name='n" + String(i) + "' maxlength='24' placeholder='اسم الأمر' value='"
          + NetworkSetup::safeHtml(items[i].name) + "'>"
          "<input name='v" + String(i) + "' type='datetime-local' step='1' value='"
          + NetworkSetup::safeHtml(items[i].datetime) + "'></fieldset>";
      }
      page += "<button type='submit'>حفظ الاختصارات على M5</button></form>"
        "<p>هذه إعدادات محلية على الجهاز، وليست تشغيل أوامر الساعة من المتصفح."
        " للتنفيذ اختر الاختصار من أزرار M5 بعد الاتصال بالشبكة.</p></body></html>";
      server.sendHeader("Cache-Control", "no-store");
      server.send(200, "text/html; charset=utf-8", page);
    });
    server.on("/presets", HTTP_POST, [this, &server, &net]() {
      if (!net.setupClient(server)) {
        server.send(403, "text/plain", "Connect to M5 setup AP"); return;
      }
      M5Preset values[kMax];
      uint8_t n = 0;
      for (uint8_t i=0; i<kMax; ++i) {
        String name = server.arg("n"+String(i));
        String value = server.arg("v"+String(i));
        name.trim();
        if (name.isEmpty() && value.isEmpty()) continue;
        if (value.length() == 16) value += ":00"; // browser may omit seconds
        if (name.isEmpty() || !validDateTime(value) || name.length()>24) {
          server.send(400, "text/plain", "Each command needs full valid date and time");
          return;
        }
        values[n++] = {name, value};
      }
      if (!save(values, n)) {
        server.send(500, "text/plain", "Could not persist presets");
        return;
      }
      server.send(200, "text/html; charset=utf-8",
        "<meta charset='utf-8'><h3>تم حفظ الأوامر</h3>"
        "<p>ارجع إلى M5 واختر الاتصال بالشبكة لتصفح الاختصارات.</p>"
        "<a href='/presets'>تعديل الاختصارات</a>");
    });
  }
};
