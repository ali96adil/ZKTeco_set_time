// M5 safe default: read-only firmware. Time-write laboratory path requires explicit build flag.
// Target board: M5StickC Plus (original) + ESP32 Arduino.
// No users, attendance records, biometric data or admin credentials accessed.
#include <Arduino.h>
#include <cstring>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <M5StickCPlus.h>
#include <qrcode.h>
#include "config.h"
#include "zk_wire.h"
#include "network_setup.h"
#include "m5_presets.h"
#include "m5_rtc.h"
#ifndef ZK_ENABLE_M5_TIME_WRITE
#define ZK_ENABLE_M5_TIME_WRITE 0
#endif

namespace {
constexpr uint16_t CMD_CONNECT = zkwire::kConnect;
constexpr uint16_t CMD_GET_TIME = zkwire::kGetTime;
constexpr uint16_t CMD_EXIT = zkwire::kExit;
constexpr uint16_t CMD_ACK_OK = zkwire::kAckOk;
constexpr uint16_t CMD_ACK_UNAUTH = zkwire::kAckUnauth;
constexpr size_t MAX_PACKET_BODY = zkwire::kMaxBody;
constexpr uint32_t TIMEOUT_MS = 5000;
WebServer server(80);
NetworkSetup net;
M5Presets stored;
M5Clock rtcClock;
enum class ScreenMode { BOOT, SETUP, CONNECT };
ScreenMode screenMode = ScreenMode::BOOT;
uint8_t selectedPreset = 0;
bool buttonBLatched = false;
bool longShiftHold = false;
bool buttonALatched = false;
bool commandBusy = false;
bool mdnsRunning = false;
bool showSetupQr = true;
uint32_t lastWifiAttempt = 0;
uint32_t lastHttpRead = 0;
String statusLine = "BOOT";
String lastClock = "--:--:--";
bool serverStarted = false;

bool readExact(WiFiClient &client, uint8_t *out, size_t count) {
  const uint32_t start = millis();
  size_t done = 0;
  while (done < count && (millis() - start) < TIMEOUT_MS) {
    int available = client.available();
    if (available > 0) {
      int n = client.read(out + done, min(static_cast<size_t>(available), count - done));
      if (n > 0) done += static_cast<size_t>(n);
    } else if (!client.connected()) {
      return false;
    } else {
      delay(2);
    }
  }
  return done == count;
}

using Reply = zkwire::Reply;

bool sendCommand(WiFiClient &client, uint16_t command, uint16_t session,
                 uint16_t previousReplyId) {
  uint8_t frame[16] = {};
  if (!zkwire::makeReadOnlyFrame(command, session, previousReplyId, frame))
    return false;
  return client.write(frame, sizeof(frame)) == sizeof(frame);
}

bool receiveReply(WiFiClient &client, Reply &reply, String &error) {
  uint8_t tcpHeader[8] = {};
  if (!readExact(client, tcpHeader, sizeof(tcpHeader))) {
    error = "TCP header timeout";
    return false;
  }
  uint32_t length = 0;
  if (!zkwire::getTcpBodyLength(tcpHeader, length)) {
    error = "Invalid TCP frame";
    return false;
  }
  uint8_t payload[MAX_PACKET_BODY] = {};
  if (!readExact(client, payload, length)) {
    error = "Incomplete ZK reply";
    return false;
  }
  if (!zkwire::parseReplyBody(payload, length, reply)) {
    error = "Malformed ZK reply";
    return false;
  }
  return true;
}

bool decodeZkTime(const uint8_t data[4], String &clock) {
  zkwire::CivilTime time;
  if (!zkwire::decodeTime(data, time)) return false;
  char buf[24] = {};
  snprintf(buf, sizeof(buf), "%04u-%02u-%02uT%02u:%02u:%02u",
           unsigned(time.year), unsigned(time.month), unsigned(time.day),
           unsigned(time.hour), unsigned(time.minute), unsigned(time.second));
  clock = buf;
  return true;
}

bool readDeviceClock(String &clock, String &error, uint32_t &durationMs) {
  const uint32_t started = millis();
  if (WiFi.status() != WL_CONNECTED) {
    error = "M5 is not connected to Wi-Fi";
    return false;
  }
  IPAddress ip;
  if (!ip.fromString(net.zkIp)) {
    error = "Invalid target IP in config.h";
    return false;
  }
  WiFiClient client;
  client.setTimeout(TIMEOUT_MS);
  if (!client.connect(ip, ZK_DEVICE_PORT, TIMEOUT_MS)) {
    error = "Cannot reach target TCP port";
    return false;
  }
  // Always close the socket. Never disable the attendance terminal.
  bool success = false;
  do {
    Reply r;
    if (!sendCommand(client, CMD_CONNECT, 0, 65534)) {
      error = "Failed to send CONNECT"; break;
    }
    if (!receiveReply(client, r, error)) break;
    if (r.code == CMD_ACK_UNAUTH) {
      error = "SDK communication key required"; break;
    }
    if (r.code != CMD_ACK_OK) {
      error = "ZK CONNECT rejected code " + String(r.code); break;
    }
    const uint16_t session = r.session;
    const uint16_t replyId = r.replyId;

    if (!sendCommand(client, CMD_GET_TIME, session, replyId)) {
      error = "Failed to send GET_TIME"; break;
    }
    if (!receiveReply(client, r, error)) break;
    if (r.code != CMD_ACK_OK || r.session != session || r.dataLen < 4) {
      error = "Unexpected GET_TIME reply"; break;
    }
    if (!decodeZkTime(r.data, clock)) {
      error = "Invalid terminal clock payload"; break;
    }
    // Best-effort clean SDK session close; never send DISABLEDEVICE.
    sendCommand(client, CMD_EXIT, session, r.replyId);
    success = true;
  } while (false);
  client.stop();
  durationMs = millis() - started;
  return success;
}


bool parseCivil(const String& str, zkwire::CivilTime& t) {
  if (!M5Presets::validDateTime(str)) return false;
  t.year = str.substring(0,4).toInt();
  t.month = str.substring(5,7).toInt();
  t.day = str.substring(8,10).toInt();
  t.hour = str.substring(11,13).toInt();
  t.minute = str.substring(14,16).toInt();
  t.second = str.substring(17,19).toInt();
  return true;
}

enum class RunResult { COMPLETED, NEED_LONG_HOLD, FAILED };

RunResult executeSelected(bool allowLargeShift) {
  if (screenMode != ScreenMode::CONNECT || commandBusy) return RunResult::FAILED;
  if (WiFi.status() != WL_CONNECTED) {
    statusLine = "NO WIFI / ZK UNREACHABLE";
    return RunResult::FAILED;
  }
  stored.load();
  if (selectedPreset > stored.count) return RunResult::FAILED;
  zkwire::CivilTime target;
  if (selectedPreset == stored.count) {
    if (!rtcClock.trustworthy(target)) {
      statusLine = "RTC NOT CALIBRATED: SETUP";
      return RunResult::FAILED;
    }
  } else if (!parseCivil(stored.items[selectedPreset].datetime, target)) {
    statusLine = "INVALID PRESET";
    return RunResult::FAILED;
  }
  String current, error;
  uint32_t readingMs = 0;
  if (!readDeviceClock(current, error, readingMs)) {
    statusLine = "READ ERROR: " + error;
    return RunResult::FAILED;
  }
  zkwire::CivilTime before;
  if (!parseCivil(current, before)) {
    statusLine = "BAD DEVICE TIME";
    return RunResult::FAILED;
  }
  int64_t delta = zkwire::civilSeconds(target) - zkwire::civilSeconds(before);
  if ((delta > 86400LL || delta < -86400LL) && !allowLargeShift) {
    statusLine = "LARGE SHIFT: HOLD B 4s";
    return RunResult::NEED_LONG_HOLD;
  }
#if ZK_ENABLE_M5_TIME_WRITE
  // ONLY the physical B-button path can reach this function. There is no
  // HTTP write API. One send, fresh independent SDK read to verify, no retries.
  commandBusy = true;
  uint8_t encoded[4];
  if (!zkwire::encodeTime(target, encoded)) {
    statusLine = "CLOCK ENCODE FAILED";
    commandBusy = false;
    return RunResult::FAILED;
  }
  IPAddress ip;
  if (!ip.fromString(net.zkIp)) {
    statusLine = "TARGET IP INVALID";
    commandBusy = false;
    return RunResult::FAILED;
  }
  WiFiClient client;
  client.setTimeout(TIMEOUT_MS);
  bool acknowledged = false;
  uint32_t sentAt = 0;
  do {
    if (!client.connect(ip, ZK_DEVICE_PORT, TIMEOUT_MS)) break;
    Reply reply;
    String receiveError;
    if (!sendCommand(client, CMD_CONNECT, 0, 65534) ||
        !receiveReply(client, reply, receiveError) || reply.code != CMD_ACK_OK)
      break;
    const uint16_t session = reply.session;
    uint8_t frame[20] = {};
    if (!zkwire::makeSetTimeFrame(session, reply.replyId, encoded, frame))
      break;
    sentAt = millis();
    if (client.write(frame, sizeof(frame)) != sizeof(frame) ||
        !receiveReply(client, reply, receiveError) ||
        reply.code != CMD_ACK_OK || reply.session != session) break;
    acknowledged = true;
    sendCommand(client, CMD_EXIT, session, reply.replyId);
  } while (false);
  client.stop();

  delay(800);
  String confirmed, verifyError;
  uint32_t verifyMs = 0;
  const bool readOk = readDeviceClock(confirmed, verifyError, verifyMs);
  zkwire::CivilTime observed;
  bool valid = readOk && parseCivil(confirmed, observed);
  int64_t expectedSeconds = zkwire::civilSeconds(target) +
                             ((millis() - sentAt) / 1000);
  bool verified = acknowledged && valid &&
    llabs(zkwire::civilSeconds(observed) - expectedSeconds) <= 2;
  statusLine = verified ? "CLOCK VERIFIED" : "UNVERIFIED: CHECK ZKTeco";
  Serial.println(statusLine);
  commandBusy = false;
  return verified ? RunResult::COMPLETED : RunResult::FAILED;
#else
  statusLine = "WRITE LAB DISABLED";
  Serial.println("M5 write disabled for physical qualification build");
  return RunResult::FAILED;
#endif
}

const char PAGE[] PROGMEM = R"HTML(
<!doctype html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="ZK Clock">
<meta name="theme-color" content="#0c1725">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" type="image/svg+xml" href="/icon.svg">
<title>ZKTeco Clock — M2 Preview</title>
<style>
:root{color-scheme:dark;font-family:system-ui,Tahoma,Arial,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:#0c1725;color:#edf5ff}
main{max-width:540px;margin:18px auto;padding:16px}
h1{font-size:23px;margin:6px 0}
header p{margin:7px 0 16px;color:#b6c8dc;line-height:1.6}
.card{background:#17283c;border:1px solid #294158;border-radius:15px;padding:17px;margin:13px 0}
.eyebrow{font-size:12px;color:#aac3dc}
.time{font-size:28px;direction:ltr;text-align:right;font-variant-numeric:tabular-nums;font-weight:750;line-height:1.6}
.small{font-size:13px;color:#adc3d8;line-height:1.65}
strong{font-size:18px}button,input{font:inherit}
button{border:0;border-radius:11px;padding:13px 15px;background:#2876cf;color:white;font-weight:700;cursor:pointer}
button:disabled{opacity:.5;cursor:default}
.primary{width:100%;font-size:17px}
.mode{display:flex;gap:8px;margin-bottom:12px}
.mode button{flex:1;background:#30465c}
.mode button.selected{background:#2876cf}
input{display:block;width:100%;padding:13px;border:1px solid #51708c;border-radius:9px;background:#0e1c2c;color:#fff;direction:ltr}
label{display:block;font-size:13px;margin:12px 0 6px}
.ok{color:#89efbd}.warn{color:#ffce82}.muted{color:#b6c8dc}
hr{border:0;border-top:1px solid #324860;margin:16px 0}
.note{background:#302b22;border-right:3px solid #ebb85e;padding:12px;line-height:1.7;border-radius:5px}
</style></head><body><main>
<header><div class="eyebrow">ZKTeco iFace 950 • M5StickC Plus</div>
<h1>التحكم بساعة البصمة</h1>
<p>نسخة M2 تجريبية: قراءة حقيقية ومعاينة التصحيح فقط. <b>لا تحتوي أي أمر لتغيير الساعة.</b></p>
</header>
<div class="card">
<div class="eyebrow">ساعة جهاز البصمة • بغداد</div><div class="time" id="device">—</div>
<div class="eyebrow">ساعة الموبايل • بغداد</div><div class="time" id="phone">—</div>
<hr><div class="eyebrow">فرق الجهاز عن الهاتف (تقريبي)</div>
<div class="time" id="delta">—</div><p class="small" id="status">اضغط «قراءة» أولاً.</p>
<button class="primary" id="read" type="button">قراءة ساعة الجهاز</button>
</div>
<div class="card">
<h2 style="font-size:18px">معاينة تغيير الوقت</h2>
<div class="mode">
<button type="button" id="phoneMode" class="selected">مزامنة الهاتف</button>
<button type="button" id="manualMode">إدخال يدوي</button>
</div>
<div id="manualBox" hidden>
<label for="manual">التاريخ والوقت المطلوبان (توقيت بغداد)</label>
<input id="manual" type="datetime-local" step="1" min="2000-01-01T00:00:00" max="2099-12-31T23:59:59">
</div>
<p class="small" id="sourceHint">نستخدم ساعة الهاتف لحظة الضغط على المعاينة، وليس وقت فتح الصفحة.</p>
<button id="preview" class="primary" type="button">معاينة التصحيح</button>
<div id="previewResult" hidden>
<hr>
<div class="eyebrow">التوقيت المقترح</div><div class="time" id="proposed">—</div>
<div class="eyebrow">فرق التصحيح المطلوب</div>
<strong id="shift">—</strong>
<p class="note" id="warning"></p>
</div>
</div>
<p class="small">⚠️ هذه نسخة DRY RUN: لا يوجد زر تطبيق، ولا API لضبط الساعة. تصحيح الوقت للخلف والأمام سيكون متاحاً بعد اختبار الجهاز وحماية عملية التنفيذ. تحقق من ساعة الهاتف؛ قد تكون خاطئة.</p>
</main><script>
'use strict';
const $=id=>document.getElementById(id);
let mode='phone', measuredOffsetMs=null, measuredAtMs=0;
const formatter=new Intl.DateTimeFormat('en-GB',{
  timeZone:'Asia/Baghdad',year:'numeric',month:'2-digit',day:'2-digit',
  hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'
});
function baghdadParts(epoch){
  const parts=formatter.formatToParts(new Date(epoch));
  const v={}; for(const p of parts)if(p.type!=='literal')v[p.type]=p.value;
  return v.year+'-'+v.month+'-'+v.day+' '+v.hour+':'+v.minute+':'+v.second;
}
function formatCivil(epoch){
  // ZKTeco stores wall-clock fields (no timezone). Keep the displayed civil
  // date stable even for dates when Baghdad historically observed DST.
  return new Date(epoch+3*3600*1000).toISOString().slice(0,19).replace('T',' ');
}
function formatDiff(ms){
  const sign=ms<0?'−':'+';
  let s=Math.round(Math.abs(ms)/1000);
  const d=Math.floor(s/86400);s%=86400;
  const h=Math.floor(s/3600);s%=3600;
  const m=Math.floor(s/60);s%=60;
  return sign+(d?d+' يوم ':'')+(h?h+' ساعة ':'')+(m?m+' دقيقة ':'')+s+' ثانية';
}
function parseBaghdadManual(value){
  const m=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(value);
  if(!m)throw Error('أدخل التاريخ والساعة بشكل صحيح');
  const y=+m[1],month=+m[2],d=+m[3],h=+m[4],min=+m[5],s=+(m[6]||'0');
  if(y<2000||y>2099||month<1||month>12||d<1||d>31||h>23||min>59||s>59)
    throw Error('التاريخ خارج النطاق المسموح');
  // Synthetic fixed +03:00 is used only to compare ZKTeco wall-clock fields.
  // It is NOT a historical Baghdad UTC conversion before 2008.
  const utc=Date.UTC(y,month-1,d,h-3,min,s);
  const verify=new Date(utc+3*3600*1000);
  if(verify.getUTCFullYear()!==y||verify.getUTCMonth()+1!==month||
     verify.getUTCDate()!==d||verify.getUTCHours()!==h||
     verify.getUTCMinutes()!==min||verify.getUTCSeconds()!==s)
    throw Error('هذا التاريخ غير موجود');
  return utc;
}
function fresh(){return measuredOffsetMs!==null && (Date.now()-measuredAtMs)<60000;}
function render(){
  const now=Date.now();
  $('phone').textContent=baghdadParts(now);
  if(measuredOffsetMs!==null){
    $('device').textContent=formatCivil(now+measuredOffsetMs);
    $('delta').textContent=formatDiff(measuredOffsetMs);
    if(!fresh())$('status').textContent='القراءة قديمة؛ أعد القراءة قبل المعاينة.';
  }
}
function setMode(next){
  mode=next;
  $('phoneMode').classList.toggle('selected',mode==='phone');
  $('manualMode').classList.toggle('selected',mode==='manual');
  $('manualBox').hidden=mode!=='manual';
  $('sourceHint').textContent=mode==='phone'
    ? 'نستخدم ساعة الهاتف لحظة الضغط على المعاينة، بتوقيت بغداد.'
    : 'أدخل التاريخ والوقت المحليين لبغداد، بالثواني إن رغبت.';
  $('previewResult').hidden=true;
}
$('phoneMode').onclick=()=>setMode('phone');
$('manualMode').onclick=()=>setMode('manual');
$('read').onclick=async()=>{
  const button=$('read'),status=$('status');
  button.disabled=true;status.textContent='جاري الاتصال...';
  const start=Date.now();
  try{
    const response=await fetch('/api/read',{cache:'no-store'});
    const end=Date.now();
    const value=await response.json();
    if(!response.ok||!value.ok)throw Error(value.error||'تعذر الاتصال');
    const civil=value.device_time.replace('T','');
    const epoch=parseBaghdadManual(civil.slice(0,10)+'T'+civil.slice(10));
    measuredAtMs=Math.round((start+end)/2);
    measuredOffsetMs=epoch-measuredAtMs;
    status.className='small ok';
    status.textContent='قراءة ناجحة، زمن الاستجابة '+(end-start)+' مللي ثانية. الفرق تقريبي.';
    $('previewResult').hidden=true;
    render();
  }catch(e){
    measuredOffsetMs=null;measuredAtMs=0;
    $('device').textContent='—';$('delta').textContent='—';
    status.className='small warn';status.textContent='فشل القراءة: '+e.message;
  }finally{button.disabled=false;}
};
$('preview').onclick=()=>{
  const out=$('previewResult'),warning=$('warning');
  out.hidden=false;
  try{
    if(!fresh())throw Error('اقرأ ساعة البصمة من جديد قبل المعاينة');
    const now=Date.now();
    const proposed=mode==='phone'?now:parseBaghdadManual($('manual').value);
    const shift=proposed-(now+measuredOffsetMs);
    $('proposed').textContent=mode==='manual'?formatCivil(proposed):baghdadParts(proposed);
    $('shift').textContent=formatDiff(shift);
    warning.className='note';
    warning.textContent=shift<0
     ? 'تنبيه: هذا التصحيح يرجع ساعة البصمة للخلف، وقد تتداخل أوقات الحضور الجديدة مع القديمة. مسموح في النسخة النهائية بعد التأكيد.'
     : 'هذا التصحيح يقدّم الساعة للأمام أو يبقيها قريبة من وقتها الحالي. المراجعة فقط، لا تغيير فعلي.';
    if(Math.abs(shift)>24*3600*1000)
      warning.textContent+=' انتبه: الفرق يتجاوز يوماً كاملاً، راجع التاريخ والمصدر.';
  }catch(e){
    $('proposed').textContent='—';$('shift').textContent='—';
    warning.textContent=e.message;
  }
};
setInterval(render,1000);
render();
</script></body></html>
)HTML";

// M5StickC Plus: 240 x 135 px landscape. Default font size 1 was
// unreadably small. Keep a high contrast two-page physical setup UI.
// QR is Wi-Fi credentials only, never ZKTeco control or attendance data.
void drawSetupQr() {
  M5.Lcd.fillScreen(BLACK);
  String payload = "WIFI:T:WPA;S:" + net.apSsid +
                   ";P:" + net.apPassword + ";;";
  QRCode qr;
  uint8_t data[qrcode_getBufferSize(4)] = {};
  // Version 4, medium correction: 33x33 modules. With 4-module white
  // quiet-zone around it, 41*3=123 px fits the 135px screen.
  qrcode_initText(&qr, data, 4, ECC_MEDIUM, payload.c_str());
  const int unit = 3;
  const int left = 4;
  const int top = 6;
  const int quiet = 4;
  const int side = (qr.size + quiet * 2) * unit;
  M5.Lcd.fillRect(left, top, side, side, WHITE);
  for (int y=0; y<qr.size; ++y) {
    for (int x=0; x<qr.size; ++x) {
      if (qrcode_getModule(&qr,x,y)) {
        M5.Lcd.fillRect(left + (quiet+x)*unit,
                        top + (quiet+y)*unit,unit,unit,BLACK);
      }
    }
  }
  M5.Lcd.setTextColor(WHITE,BLACK);
  M5.Lcd.setTextSize(1);
  M5.Lcd.drawString("JOIN WIFI",133,9,2);
  M5.Lcd.drawString("SCAN QR",133,32,2);
  M5.Lcd.drawString("iPhone",133,58,2);
  M5.Lcd.drawString("Camera",133,76,1);
  M5.Lcd.drawString("A: PASS",133,101,2);
  M5.Lcd.drawString("B hold: exit",133,121,1);
}

void drawSetupPassword() {
  M5.Lcd.fillScreen(BLACK);
  M5.Lcd.setTextColor(WHITE,BLACK);
  M5.Lcd.setTextSize(1);
  M5.Lcd.drawString("SETUP WIFI",8,3,2);
  M5.Lcd.drawFastHLine(8,26,224,0x34BF);
  M5.Lcd.setTextColor(0x9D9F,BLACK);
  M5.Lcd.drawString("NETWORK NAME",8,31,1);
  M5.Lcd.setTextColor(WHITE,BLACK);
  M5.Lcd.drawString(net.apSsid,8,42,2);
  M5.Lcd.setTextColor(0x9D9F,BLACK);
  M5.Lcd.drawString("PASSWORD - FIRST / LAST",8,64,1);
  M5.Lcd.setTextColor(WHITE,BLACK);
  const int mid = net.apPassword.length()/2;
  // Fixed-width and scaled: seven characters fit reliably in each half.
  M5.Lcd.setTextSize(2);
  M5.Lcd.drawString(net.apPassword.substring(0,mid),8,79,2);
  M5.Lcd.drawString(net.apPassword.substring(mid),126,79,2);
  M5.Lcd.setTextSize(1);
  M5.Lcd.setTextColor(0xBDF7,BLACK);
  M5.Lcd.drawString("type both parts without space",8,109,1);
  M5.Lcd.drawString("A: QR    192.168.4.1",8,123,1);
}

void drawScreen() {
  M5.Lcd.fillScreen(BLACK);
  M5.Lcd.setTextColor(WHITE,BLACK);
  M5.Lcd.setTextSize(1);
  if (screenMode == ScreenMode::BOOT) {
    M5.Lcd.drawString("ZKTeco CLOCK",10,6,2);
    M5.Lcd.drawFastHLine(10,30,220,0x34BF);
    M5.Lcd.fillRoundRect(8,38,224,39,6,0x13A5);
    M5.Lcd.drawString("A",17,49,4);
    M5.Lcd.drawString("SETUP WIFI",61,50,2);
    M5.Lcd.fillRoundRect(8,84,224,39,6,0x13A5);
    M5.Lcd.drawString("B",17,94,4);
    M5.Lcd.drawString("CONNECT WIFI",61,96,2);
    return;
  }
  if (screenMode == ScreenMode::SETUP) {
    if (showSetupQr) drawSetupQr();
    else drawSetupPassword();
    return;
  }
  M5.Lcd.drawString("ZKTeco CLOCK",7,3,2);
  M5.Lcd.drawString(WiFi.status()==WL_CONNECTED ? "WIFI CONNECTED" : "CONNECTING...",7,23,2);
  if (WiFi.status()==WL_CONNECTED)
    M5.Lcd.drawString("zkclock.local",7,43,2);
  stored.load();
  if (selectedPreset > stored.count) selectedPreset = 0;
  M5.Lcd.drawString(String(selectedPreset + 1) + "/" + String(stored.count+1),7,63,2);
  if (selectedPreset == stored.count) {
    zkwire::CivilTime currentRtc;
    const bool good = rtcClock.trustworthy(currentRtc);
    M5.Lcd.drawString("SYNC FROM M5 RTC",48,63,2);
    M5.Lcd.drawString(good ? M5Clock::asString(currentRtc) : "RTC NOT SET",7,82,2);
  } else {
    M5.Lcd.drawString(stored.items[selectedPreset].name,48,63,2);
    M5.Lcd.drawString(stored.items[selectedPreset].datetime,7,82,2);
  }
  M5.Lcd.drawString("A: NEXT     HOLD B: RUN",7,105,1);
  M5.Lcd.drawString(statusLine,7,120,1);
}

void startHttpOnce() {
  if (serverStarted) return;
  net.attachRoutes(server);
  stored.routes(server, net);
  rtcClock.routes(server, net);
  server.on("/manifest.webmanifest", HTTP_GET, []() {
    server.sendHeader("Cache-Control", "no-store");
    server.send(200,"application/manifest+json",
      "{\"name\":\"ZKTeco M5 Clock\",\"short_name\":\"ZK M5\","
      "\"start_url\":\"/\",\"display\":\"standalone\","
      "\"theme_color\":\"#0c1725\",\"background_color\":\"#0c1725\","
      "\"icons\":[{\"src\":\"/icon.svg\",\"sizes\":\"any\","
      "\"type\":\"image/svg+xml\"}]}");
  });
  server.on("/icon.svg", HTTP_GET, []() {
    server.send(200,"image/svg+xml",
      "<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'"
      " viewBox='0 0 180 180'><rect width='180' height='180' rx='32'"
      " fill='#0c1725'/><circle cx='90' cy='90' r='62' fill='#2376cf'/>"
      "<path d='M90 48v43h33' stroke='white' stroke-width='11'"
      " stroke-linecap='round' fill='none'/></svg>");
  });
  server.on("/", HTTP_GET, []() {
    server.sendHeader("Cache-Control", "no-store");
    server.send_P(200, "text/html; charset=utf-8", PAGE);
  });
  server.on("/api/read", HTTP_GET, []() {
    // An open campus WLAN is not trusted. Bound the rate of device reads
    // so repeated unauthenticated HTTP requests cannot continuously occupy it.
    if (lastHttpRead && millis() - lastHttpRead < 8000) {
      server.sendHeader("Cache-Control", "no-store");
      server.send(429, "application/json", "{\"ok\":false,\"error\":\"Read rate limited (8 seconds)\"}");
      return;
    }
    lastHttpRead = millis();
    String clock, error;
    uint32_t ms = 0;
    const bool ok = readDeviceClock(clock, error, ms);
    server.sendHeader("Cache-Control", "no-store");
    if (ok) {
      lastClock = clock;
      statusLine = "READ OK";
      server.send(200, "application/json",
                  "{\"ok\":true,\"device_time\":\"" + clock +
                  "\",\"duration_ms\":" + String(ms) + "}");
    } else {
      statusLine = "READ FAILED";
      // Fixed internal error classes only; no credentials in responses.
      error.replace("\"", "'");
      server.send(503, "application/json",
                  "{\"ok\":false,\"error\":\"" + error + "\"}");
    }
    drawScreen();
  });
  server.onNotFound([]() {
    server.send(404, "text/plain", "Not found. Read-only endpoints only.");
  });
  server.begin();
  serverStarted = true;
}

void connectWifiIfNeeded() {
  static bool reported = false;
  if (screenMode == ScreenMode::CONNECT) net.tick();
  const bool connected = WiFi.status() == WL_CONNECTED;
  if (connected && !reported) {
    if (!mdnsRunning && MDNS.begin("zkclock")) {
      MDNS.addService("http", "tcp", 80);
      mdnsRunning = true;
      Serial.println("Bonjour local address: http://zkclock.local/");
    }
    reported = true;
    statusLine = "WIFI CONNECTED";
    Serial.println("M5 IP: " + WiFi.localIP().toString());
    Serial.println("Gateway: " + WiFi.gatewayIP().toString());
    Serial.println("STA MAC: " + WiFi.macAddress());
    drawScreen();
  } else if (!connected && reported) {
    if (mdnsRunning) { MDNS.end(); mdnsRunning = false; }
    reported = false;
    statusLine = "WIFI DISCONNECTED";
    drawScreen();
  }
  if ((connected || net.apOn) && !serverStarted) startHttpOnce();
}

} // namespace

void setup() {
  M5.begin();
  Serial.begin(115200);
  M5.Lcd.setRotation(1);
  net.begin(ZK_WIFI_SSID, ZK_WIFI_PASSWORD, ZK_DEVICE_IP);
  stored.load();
  rtcClock.begin();
  // No network write to attendance device on startup.
  connectWifiIfNeeded();
  drawScreen();
}

void loop() {
  M5.update();
  if (screenMode == ScreenMode::BOOT) {
    if (M5.BtnA.wasPressed()) {
      screenMode = ScreenMode::SETUP;
      showSetupQr = true;
      net.startAP();
      if (net.apOn) {
        // Advertise the same friendly address in setup mode when phone/mDNS
        // supports it. The documented 192.168.4.1 fallback always remains.
        if (!mdnsRunning && MDNS.begin("zkclock")) {
          MDNS.addService("http","tcp",80);
          mdnsRunning = true;
        }
        startHttpOnce();
      }
      drawScreen();
    } else if (M5.BtnB.wasPressed()) {
      screenMode = ScreenMode::CONNECT;
      net.lastAttempt = millis() - 15000;
      drawScreen();
    }
    delay(18);
    return;
  }

  connectWifiIfNeeded();
  if (screenMode == ScreenMode::SETUP) {
    if (M5.BtnA.wasPressed()) {
      showSetupQr = !showSetupQr;
      drawScreen();
    }
    if (M5.BtnB.pressedFor(2000) && !buttonBLatched) {
      buttonBLatched = true;
      if (mdnsRunning) { MDNS.end(); mdnsRunning = false; }
      net.stopAP();
      screenMode = ScreenMode::BOOT;
      drawScreen();
    }
    if (!M5.BtnB.isPressed()) buttonBLatched = false;
  } else {
    if (M5.BtnA.wasPressed()) {
      selectedPreset = (selectedPreset + 1) % (stored.count + 1);
      drawScreen();
    }
    if (M5.BtnA.pressedFor(3000) && !buttonALatched) {
      buttonALatched = true;
      WiFi.disconnect(false, false);
      screenMode = ScreenMode::BOOT;
      drawScreen();
    }
    if (!M5.BtnA.isPressed()) buttonALatched = false;

    if (!buttonBLatched) {
      if (!longShiftHold && M5.BtnB.pressedFor(2200)) {
        RunResult result = executeSelected(false);
        if (result == RunResult::NEED_LONG_HOLD)
          longShiftHold = true;
        else
          buttonBLatched = true;
        drawScreen();
      }
      if (longShiftHold && M5.BtnB.pressedFor(4200)) {
        executeSelected(true);
        buttonBLatched = true;
        longShiftHold = false;
        drawScreen();
      }
    }
    if (!M5.BtnB.isPressed()) {
      buttonBLatched = false;
      longShiftHold = false;
    }
  }
  if ((WiFi.status() == WL_CONNECTED || net.apOn) && serverStarted)
    server.handleClient();
  delay(15);
}
