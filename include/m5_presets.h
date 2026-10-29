#pragma once
// Exact civil date+time button presets, stored locally in ESP32 Preferences.
// The editor is available only from the M5 WPA2 provisioning AP.
// It does not expose a remote write endpoint to the campus Wi-Fi.
#include <Arduino.h>
#include <Preferences.h>
#include <ESPWebServer.hpp>
#include "network_setup.h"
#include "web_navigation.h"

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
      // All network clients can read shortcut labels/timestamps; only the
      // physically protected WPA2 setup network can modify their catalog.
      load();
      const bool editable = net.setupClient(server);
      String page = zkPageBegin("الأوامر المحفوظة");
      page += "<p>عدد الاختصارات: <b>" + String(count) +
        "</b> من 8. الأوامر تحتوي التاريخ والساعة معاً.</p>";
      if (count == 0)
        page += "<p>ماكو اختصارات محفوظة حالياً.</p>";
      for (uint8_t i=0; i<count; ++i) {
        page += "<div style='padding:12px;margin:9px 0;border-radius:10px;"
          "background:#1b3249'><b>" + String(i+1) + ". " +
          NetworkSetup::safeHtml(items[i].name) +
          "</b><div dir='ltr' style='text-align:right;font-variant-numeric:tabular-nums'>" +
          NetworkSetup::safeHtml(items[i].datetime) + "</div></div>";
      }
      page += "<div style='padding:12px;background:#1b3249;border-radius:10px'>"
        "<b>مزامنة من ساعة M5 RTC</b><p>تستخدم الساعة الداخلية بعد معايرتها من الهاتف.</p>"
        "</div>";
      page += "<p>للتنفيذ من الجهاز: اختر الاختصار بالزر A ثم اضغط B مطولاً. "
        "نسخة القراءة فقط تعرض الاختصارات ولكن لا تغيّر ساعة البصمة.</p>";
      if (editable) {
        page += "<h3>تعديل الأوامر</h3>"
          "<form method='post' action='/presets'>";
        for (uint8_t i=0; i<kMax; ++i) {
          page += "<fieldset><legend>اختصار " + String(i+1) + "</legend>"
            "<input name='n" + String(i) + "' maxlength='24' placeholder='اسم الأمر' value='" +
            NetworkSetup::safeHtml(items[i].name) + "'>"
            "<input name='v" + String(i) + "' type='datetime-local' step='1' value='" +
            NetworkSetup::safeHtml(items[i].datetime) + "'></fieldset>";
        }
        page += "<button type='submit'>حفظ الاختصارات على M5</button></form>"
          "<h3>استيراد من الماك</h3>"
          "<p>كل سطر: اسم|YYYY-MM-DDTHH:MM:SS</p>"
          "<form action='/presets/import' method='post'>"
          "<textarea name='bulk' rows='8' maxlength='1600'></textarea>"
          "<button type='submit'>استيراد الأوامر</button></form>";
      } else {
        page += "<p style='background:#393023;padding:12px'>التعديل متاح فقط "
          "من شبكة إعداد M5 الخاصة (SETUP)، مو من واي فاي الجامعة المفتوح.</p>";
      }
      page += zkPageEnd();
      server.sendHeader("Cache-Control", "no-store");
      server.send(200, "text/html; charset=utf-8", page);
    });
    server.on("/presets/import", HTTP_POST, [this, &server, &net]() {
      if (!net.setupClient(server)) {
        server.send(403, "text/plain", "Connect to physical M5 setup AP");
        return;
      }
      String bulk = server.arg("bulk");
      if (!bulk.length() || bulk.length() > 1600) {
        server.send(400, "text/plain", "No shortcuts to import"); return;
      }
      M5Preset values[kMax];
      uint8_t n = 0;
      int cursor = 0;
      while (cursor < int(bulk.length())) {
        int newline = bulk.indexOf('\n', cursor);
        if (newline == -1) newline = bulk.length();
        String row = bulk.substring(cursor, newline);
        row.trim();
        cursor = newline + 1;
        if (!row.length()) continue;
        if (n >= kMax) {
          server.send(400, "text/plain", "Maximum eight M5 presets"); return;
        }
        int sep = row.indexOf('|');
        if (sep <= 0 || row.lastIndexOf('|') != sep) {
          server.send(400, "text/plain", "Expected name|full datetime"); return;
        }
        String name = row.substring(0, sep);
        String value = row.substring(sep + 1);
        name.trim(); value.trim();
        if (!name.length() || name.length() > 24 || !validDateTime(value)) {
          server.send(400, "text/plain",
                      "Preset label 1-24 bytes; valid full date and time required");
          return;
        }
        values[n++] = {name, value};
      }
      if (!n || !save(values, n)) {
        server.send(400, "text/plain", "Could not save imported commands"); return;
      }
      String page=zkPageBegin("تم استيراد الاختصارات");
      page += "<p>تم حفظ الأوامر على M5. افتح وضع CONNECT لعرضها.</p>"
              "<a href='/presets'>عرض الاختصارات</a>" + zkPageEnd();
      server.send(200,"text/html; charset=utf-8",page);
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
      String page=zkPageBegin("تم حفظ الأوامر");
      page += "<p>الأوامر انحفظت على M5. افتح CONNECT للتصفح.</p>"
              "<a href='/presets'>رجوع للاختصارات</a>" + zkPageEnd();
      server.send(200,"text/html; charset=utf-8",page);
    });
  }
};
