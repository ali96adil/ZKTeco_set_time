#pragma once
// Consistent HTTPS SETUP pages, visually matched to CONNECT's mobile cards.
#include <Arduino.h>

inline String zkJsonEscape(const String& input) {
  String result;
  for (unsigned i=0; i<input.length(); ++i) {
    const unsigned char c = input[i];
    if (c=='\\') result += "\\\\";
    else if (c=='"') result += "\\\"";
    else if (c < 0x20) {
      char code[7];
      snprintf(code,sizeof(code),"\\u%04x",unsigned(c));
      result += code;
    } else result += char(c);
  }
  return result;
}

inline String zkNav() {
  return "<nav class='tabs'>"
    "<a href='/setup'>الإعدادات</a>"
    "<a href='/presets'>الأوامر</a>"
    "<a href='/rtc'>RTC</a>"
    "<a href='/auth/setup'>الحساب</a>"
    "</nav>";
}

inline String zkPageBegin(const String& title) {
  return "<!doctype html><html lang='ar' dir='rtl'><head>"
    "<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>"
    "<meta name='theme-color' content='#0c1725'><title>"+title+" | ZK Clock</title>"
    "<style>"
    ":root{color-scheme:dark;font:15px system-ui,-apple-system,Tahoma,Arial,sans-serif}"
    "*{box-sizing:border-box}"
    "body{margin:0;background:#0c1725;color:#f3f7ff;line-height:1.55}"
    ".wrap{max-width:590px;padding:16px 14px 32px;margin:0 auto}"
    ".brand{font-size:12px;color:#aebdd0;margin:2px 0 2px}"
    "h1{font-size:23px;margin:0 0 12px}h2{font-size:18px;margin:12px 0}"
    "h3{font-size:16px;margin:9px 0}"
    ".tabs{position:sticky;top:0;display:flex;gap:5px;background:#0c1725;"
      "padding:8px 0 13px;z-index:3;overflow-x:auto}"
    ".tabs a{flex:1;text-align:center;white-space:nowrap;background:#1c3045;"
      "border-radius:10px;padding:11px 7px;color:white;text-decoration:none;font-size:13px}"
    "form,.card{display:block;background:#17283c;border:1px solid #294157;"
      "border-radius:16px;padding:15px;margin:12px 0}"
    "fieldset{border:1px solid #365169;border-radius:12px;margin:10px 0;padding:11px}"
    "fieldset[hidden]{display:none}"
    "label{display:block;color:#c2d2e5;font-size:13px;margin:12px 0 5px}"
    "input,select,textarea{width:100%;border:1px solid #426380;background:#0d1e2e;"
      "color:white;border-radius:9px;padding:12px;font:inherit}"
    "input:focus,select:focus,textarea:focus{outline:2px solid #4f9edd}"
    "textarea{min-height:85px}button{border:0;border-radius:10px;background:#2979b8;"
      "color:white;padding:12px;font:inherit;font-weight:650;cursor:pointer}"
    "button:disabled{opacity:.5}button.alt{background:#334962}"
    "button.danger{background:#5f3340;padding:8px 15px;font-size:13px}"
    "button.action{width:100%;margin-top:12px}"
    ".toolbar{display:flex;gap:10px;align-items:center;justify-content:space-between}"
    ".muted{font-size:13px;color:#b5c7d9}"
    ".note{padding:11px 12px;background:#20354a;border-radius:11px;font-size:13px;color:#c6d9eb}"
    "p{line-height:1.65}a{color:#b2dbff}"
    "</style></head><body><div class='wrap'>"
    "<div class='brand'>ZKTeco / M5StickC Plus · HTTPS SETUP"
    " <span id='batteryMini' style='float:left'>البطارية: —</span></div>"
    "<h1>"+title+"</h1>"+zkNav();
}
inline String zkPageEnd() {
  return "<p class='muted'>نسبة البطارية تقريبية اعتماداً على فولتية AXP192 وليست مقياس سعة دقيقاً.</p>"
    "<script>"
    "async function updateSetupBattery(){"
    "try{const r=await fetch('/api/battery',{cache:'no-store'});"
    "if(!r.ok)return;const b=await r.json();"
    "document.getElementById('batteryMini').textContent=b.valid?"
    "('بطارية ~'+b.percent_estimate+'% · '+Number(b.voltage_v).toFixed(2)"
    "+'V'+(b.usb_power?' · USB':''))
    :'البطارية: قراءة غير متاحة';"
    "}catch(e){}}"
    "updateSetupBattery();setInterval(updateSetupBattery,30000);"
    "</script></div></body></html>";
}
