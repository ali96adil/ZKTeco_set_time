// M1 READ-ONLY firmware. Intentionally DOES NOT IMPLEMENT CMD_SET_TIME (202).
// Target board: M5StickC Plus (original) + ESP32 Arduino.
// No users, attendance records, biometric data or admin credentials accessed.
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <M5StickCPlus.h>
#include "config.h"

namespace {
constexpr uint16_t CMD_CONNECT = 1000;
constexpr uint16_t CMD_GET_TIME = 201;
constexpr uint16_t CMD_EXIT = 1001;
constexpr uint16_t CMD_ACK_OK = 2000;
constexpr uint16_t CMD_ACK_UNAUTH = 2005;
constexpr uint16_t ZK_TCP_MAGIC1 = 20560;
constexpr uint16_t ZK_TCP_MAGIC2 = 32130;
constexpr size_t MAX_PACKET_BODY = 64;
constexpr uint32_t TIMEOUT_MS = 5000;
WebServer server(80);
uint32_t lastWifiAttempt = 0;
String statusLine = "BOOT";
String lastClock = "--:--:--";
bool serverStarted = false;

uint16_t le16(const uint8_t *p) {
  return static_cast<uint16_t>(p[0]) |
         (static_cast<uint16_t>(p[1]) << 8);
}
uint32_t le32(const uint8_t *p) {
  return static_cast<uint32_t>(p[0]) |
         (static_cast<uint32_t>(p[1]) << 8) |
         (static_cast<uint32_t>(p[2]) << 16) |
         (static_cast<uint32_t>(p[3]) << 24);
}
void put16(uint8_t *p, uint16_t v) {
  p[0] = static_cast<uint8_t>(v & 255);
  p[1] = static_cast<uint8_t>((v >> 8) & 255);
}
void put32(uint8_t *p, uint32_t v) {
  for (int i = 0; i < 4; ++i) p[i] = (v >> (8 * i)) & 255;
}

// Mirrors pyzk checksum algorithm (not the standard TCP checksum).
uint16_t zkChecksum(const uint8_t *p, size_t len) {
  uint32_t sum = 0;
  size_t i = 0;
  while (i + 1 < len) {
    sum += le16(p + i);
    if (sum > 65535) sum -= 65535;
    i += 2;
  }
  if (i < len) sum += p[i];
  while (sum > 65535) sum -= 65535;
  int32_t result = ~static_cast<int32_t>(sum);
  while (result < 0) result += 65535;
  return static_cast<uint16_t>(result);
}

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

struct Reply {
  uint16_t code = 0;
  uint16_t session = 0;
  uint16_t replyId = 0;
  uint8_t data[MAX_PACKET_BODY - 8] = {};
  size_t dataLen = 0;
};

bool sendCommand(WiFiClient &client, uint16_t command, uint16_t session,
                 uint16_t previousReplyId) {
  // M1 hard allowlist: no writes or administrative commands.
  if (command != CMD_CONNECT && command != CMD_GET_TIME && command != CMD_EXIT) return false;
  uint8_t zk[8] = {};
  put16(zk, command);
  put16(zk + 4, session);
  put16(zk + 6, previousReplyId);
  const uint16_t checksum = zkChecksum(zk, sizeof(zk));
  put16(zk + 2, checksum);
  uint32_t nextId = static_cast<uint32_t>(previousReplyId) + 1;
  if (nextId >= 65535) nextId -= 65535;
  put16(zk + 6, static_cast<uint16_t>(nextId));

  uint8_t frame[16] = {};
  put16(frame, ZK_TCP_MAGIC1);
  put16(frame + 2, ZK_TCP_MAGIC2);
  put32(frame + 4, sizeof(zk));
  memcpy(frame + 8, zk, sizeof(zk));
  return client.write(frame, sizeof(frame)) == sizeof(frame);
}

bool receiveReply(WiFiClient &client, Reply &reply, String &error) {
  uint8_t tcpHeader[8] = {};
  if (!readExact(client, tcpHeader, sizeof(tcpHeader))) {
    error = "TCP header timeout";
    return false;
  }
  if (le16(tcpHeader) != ZK_TCP_MAGIC1 || le16(tcpHeader + 2) != ZK_TCP_MAGIC2) {
    error = "Unexpected TCP framing";
    return false;
  }
  const uint32_t length = le32(tcpHeader + 4);
  if (length < 8 || length > MAX_PACKET_BODY) {
    error = "Invalid TCP payload length";
    return false;
  }

  uint8_t payload[MAX_PACKET_BODY] = {};
  if (!readExact(client, payload, length)) {
    error = "Incomplete ZK reply";
    return false;
  }
  reply.code = le16(payload);
  reply.session = le16(payload + 4);
  reply.replyId = le16(payload + 6);
  reply.dataLen = length - 8;
  if (reply.dataLen) memcpy(reply.data, payload + 8, reply.dataLen);
  return true;
}

bool decodeZkTime(const uint8_t data[4], String &clock) {
  uint32_t encoded = le32(data);
  const int sec = encoded % 60; encoded /= 60;
  const int minute = encoded % 60; encoded /= 60;
  const int hour = encoded % 24; encoded /= 24;
  const int day = encoded % 31 + 1; encoded /= 31;
  const int month = encoded % 12 + 1; encoded /= 12;
  const int year = static_cast<int>(encoded) + 2000;

  if (year < 2000 || year > 2099 || month < 1 || month > 12 ||
      hour > 23 || minute > 59 || sec > 59) return false;
  const int mdays[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  const bool leap = (year % 4 == 0 && (year % 100 != 0 || year % 400 == 0));
  const int maxDay = (month == 2 && leap) ? 29 : mdays[month - 1];
  if (day < 1 || day > maxDay) return false;

  char buf[24] = {};
  snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02d",
           year, month, day, hour, minute, sec);
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
  if (!ip.fromString(ZK_DEVICE_IP)) {
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

const char PAGE[] PROGMEM = R"HTML(
<!doctype html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
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

void drawScreen() {
  M5.Lcd.fillScreen(BLACK);
  M5.Lcd.setCursor(5, 5);
  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(WHITE);
  M5.Lcd.println("ZKTeco clock");
  M5.Lcd.setTextSize(1);
  M5.Lcd.println("M1 - READ ONLY");
  M5.Lcd.println(statusLine);
  if (WiFi.status() == WL_CONNECTED) {
    M5.Lcd.print("URL: http://");
    M5.Lcd.println(WiFi.localIP().toString());
  }
  M5.Lcd.println(lastClock);
  M5.Lcd.println("A: Read  B: no-op");
}

void startHttpOnce() {
  if (serverStarted) return;
  server.on("/", HTTP_GET, []() {
    server.sendHeader("Cache-Control", "no-store");
    server.send_P(200, "text/html; charset=utf-8", PAGE);
  });
  server.on("/api/read", HTTP_GET, []() {
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
  if (WiFi.status() == WL_CONNECTED) {
    statusLine = "WIFI CONNECTED";
    startHttpOnce();
    return;
  }
  if (millis() - lastWifiAttempt < 15000) return;
  lastWifiAttempt = millis();
  statusLine = "CONNECTING WIFI";
  WiFi.mode(WIFI_STA);
  WiFi.begin(ZK_WIFI_SSID, ZK_WIFI_PASSWORD);
  drawScreen();
}
} // namespace

void setup() {
  M5.begin();
  Serial.begin(115200);
  M5.Lcd.setRotation(1);
  WiFi.setAutoReconnect(true);
  // No network write to attendance device on startup.
  lastWifiAttempt = millis() - 15000;
  connectWifiIfNeeded();
  drawScreen();
}

void loop() {
  M5.update();
  connectWifiIfNeeded();
  if (WiFi.status() == WL_CONNECTED && serverStarted) server.handleClient();
  if (M5.BtnA.wasPressed()) {
    String clock, error;
    uint32_t ms = 0;
    if (readDeviceClock(clock, error, ms)) {
      lastClock = clock;
      statusLine = "READ OK";
    } else {
      statusLine = "READ FAILED";
      Serial.println(error);
    }
    drawScreen();
  }
  delay(15);
}
