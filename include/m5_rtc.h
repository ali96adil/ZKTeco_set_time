#pragma once
// BM8563 RTC calibration and trusted local read for M5StickC Plus (original).
// Never assume power-on RTC is correct. Calibration is explicitly triggered
// from a phone connected to the protected M5 setup AP; persisted max age 7 days.
#include <Arduino.h>
#include <M5StickCPlus.h>
#include <Preferences.h>
#include <WebServer.h>
#include "m5_presets.h"
#include "web_navigation.h"
#include "zk_wire.h"

class M5Clock {
 public:
  String lastCalibration;
  static constexpr int64_t kMaxAgeSeconds = 7LL * 86400;

  void begin() {
    Preferences pref;
    pref.begin("zk-rtc", true);
    lastCalibration = pref.getString("calib", "");
    pref.end();
  }

  static String asString(const zkwire::CivilTime& t) {
    char result[24];
    snprintf(result, sizeof(result), "%04u-%02u-%02uT%02u:%02u:%02u",
      unsigned(t.year), unsigned(t.month), unsigned(t.day),
      unsigned(t.hour), unsigned(t.minute), unsigned(t.second));
    return result;
  }

  bool get(zkwire::CivilTime& result) const {
    RTC_TimeTypeDef tm = {};
    RTC_DateTypeDef date = {};
    M5.Rtc.GetTime(&tm);
    M5.Rtc.GetDate(&date);
    zkwire::CivilTime t;
    t.year = date.Year;
    t.month = date.Month;
    t.day = date.Date;
    t.hour = tm.Hours;
    t.minute = tm.Minutes;
    t.second = tm.Seconds;
    if (!M5Presets::validDateTime(asString(t))) return false;
    result = t;
    return true;
  }

  bool trustworthy(zkwire::CivilTime& t) const {
    if (!M5Presets::validDateTime(lastCalibration) || !get(t)) return false;
    zkwire::CivilTime calibrated;
    calibrated.year = lastCalibration.substring(0,4).toInt();
    calibrated.month = lastCalibration.substring(5,7).toInt();
    calibrated.day = lastCalibration.substring(8,10).toInt();
    calibrated.hour = lastCalibration.substring(11,13).toInt();
    calibrated.minute = lastCalibration.substring(14,16).toInt();
    calibrated.second = lastCalibration.substring(17,19).toInt();
    const int64_t age = zkwire::civilSeconds(t) - zkwire::civilSeconds(calibrated);
    // A lost RTC backup battery may reset time; this catches resets and stale
    // calibration. Validity doesn't guarantee accuracy: user must check drift.
    return age >= 0 && age <= kMaxAgeSeconds;
  }

  bool setFromPhone(const String& value) {
    if (!M5Presets::validDateTime(value)) return false;
    RTC_DateTypeDef date = {};
    RTC_TimeTypeDef tm = {};
    date.Year = value.substring(0,4).toInt();
    date.Month = value.substring(5,7).toInt();
    date.Date = value.substring(8,10).toInt();
    // Sunday=0..Saturday=6, using civil day algorithm. Library accepts 0..6.
    int year = date.Year, month = date.Month, day = date.Date;
    static const int offset[] = {0,3,2,5,0,3,5,1,4,6,2,4};
    if (month < 3) --year;
    date.WeekDay = (year+year/4-year/100+year/400+offset[month-1]+day)%7;
    tm.Hours = value.substring(11,13).toInt();
    tm.Minutes = value.substring(14,16).toInt();
    tm.Seconds = value.substring(17,19).toInt();
    M5.Rtc.SetDate(&date);
    M5.Rtc.SetTime(&tm);
    zkwire::CivilTime check;
    if (!get(check)) return false;
    // Clock write and read can cross one-second boundary.
    zkwire::CivilTime expected;
    expected.year=date.Year;expected.month=date.Month;expected.day=date.Date;
    expected.hour=tm.Hours;expected.minute=tm.Minutes;expected.second=tm.Seconds;
    if (llabs(zkwire::civilSeconds(check)-zkwire::civilSeconds(expected)) > 2)
      return false;
    Preferences pref;
    if (!pref.begin("zk-rtc",false)) return false;
    lastCalibration = asString(check);
    pref.putString("calib",lastCalibration);
    pref.end();
    return true;
  }

  void routes(WebServer& server, NetworkSetup& net) {
    server.on("/rtc",HTTP_GET,[this,&server,&net]() {
      const bool canCalibrate = net.setupClient(server);
      zkwire::CivilTime t;
      bool good = trustworthy(t);
      String current = get(t) ? asString(t) : "RTC INVALID";
      String page = zkPageBegin("ساعة M5 الداخلية RTC");
      page += "<p>ساعة M5: <b dir='ltr'>" + current + "</b></p>"
        "<p>حالة المعايرة: <b>" +
        String(good ? "صالحة خلال آخر 7 أيام" : "غير صالحة أو تحتاج تحديث") +
        "</b></p>";
      if (canCalibrate) {
        page += "<p>تأكد أن وقت الآيفون صحيح قبل مزامنته مع M5.</p>"
          "<button id='sync'>مزامنة ساعة M5 من الهاتف</button><p id='status'></p><script>"
          "document.getElementById('sync').onclick=async()=>{"
          "const p=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Baghdad',"
          "year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',"
          "minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date());"
          "const m=Object.fromEntries(p.filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));"
          "const v=m.year+'-'+m.month+'-'+m.day+'T'+m.hour+':'+m.minute+':'+m.second;"
          "const r=await fetch('/rtc/calibrate',{method:'POST',"
          "headers:{'Content-Type':'application/x-www-form-urlencoded'},"
          "body:new URLSearchParams({datetime:v})});"
          "document.getElementById('status').textContent="
          "r.ok?'تم ضبط الساعة؛ أعد فتح الصفحة للتأكد':'فشل ضبط ساعة M5';"
          "};</script>";
      } else {
        page += "<p>هاي الصفحة للعرض فقط في CONNECT. لمزامنة RTC من الموبايل، "
          "ارجع إلى SETUP واتصل بشبكة إعداد M5 المحمية، ثم افتح /rtc.</p>";
      }
      page += zkPageEnd();
      server.sendHeader("Cache-Control","no-store");
      server.send(200,"text/html; charset=utf-8",page);
    });
    server.on("/rtc/calibrate",HTTP_POST,[this,&server,&net]() {
      if (!net.setupClient(server)) {
        server.send(403,"text/plain","Requires protected M5 setup AP");
        return;
      }
      String value = server.arg("datetime");
      if (!setFromPhone(value)) {
        server.send(400,"text/plain","Invalid M5 RTC calibration");
        return;
      }
      server.sendHeader("Cache-Control","no-store");
      server.send(200,"text/plain","M5 RTC calibrated");
    });
  }
};
