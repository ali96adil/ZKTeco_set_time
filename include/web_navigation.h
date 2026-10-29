#pragma once
// Simple local web UI navigation, no authentication or control actions.
#include <Arduino.h>
inline String zkNav() {
  return "<nav style='display:flex;gap:7px;flex-wrap:wrap;margin:0 0 14px'>"
    "<a href='/' style='padding:10px;color:white;background:#24517b;border-radius:8px'>الرئيسية</a>"
    "<a href='/presets' style='padding:10px;color:white;background:#24517b;border-radius:8px'>الاختصارات</a>"
    "<a href='/setup' style='padding:10px;color:white;background:#24517b;border-radius:8px'>إعدادات الشبكة</a>"
    "<a href='/rtc' style='padding:10px;color:white;background:#24517b;border-radius:8px'>الساعة RTC</a>"
    "</nav>";
}
inline String zkPageBegin(const String& title) {
  return "<!doctype html><html lang='ar' dir='rtl'><head>"
    "<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<meta name='color-scheme' content='dark'><title>"+title+"</title>"
    "<style>body{font:16px system-ui;max-width:560px;margin:20px auto;padding:14px;"
    "background:#0d192a;color:#f1f7ff;line-height:1.6}"
    "input,textarea,button{box-sizing:border-box;width:100%;font:inherit;padding:11px;margin:6px 0 12px}"
    "input,textarea{background:#132940;color:white;border:1px solid #42647c;border-radius:7px}"
    "button{background:#236eab;color:white;border:0;border-radius:9px}"
    "a{color:#bbdeff}small{color:#a9b9c8}fieldset{margin:10px 0;border-color:#42647c}"
    "</style></head><body>" + zkNav() + "<h2>"+title+"</h2>";
}
inline String zkPageEnd() { return "</body></html>"; }
