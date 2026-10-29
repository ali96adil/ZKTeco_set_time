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
<title>ZKTeco Clock — Read Only</title>
<style>
body{margin:0;background:#101c2a;color:#eff6ff;font:16px system-ui,Tahoma,Arial}
main{max-width:440px;margin:36px auto;padding:18px}
section{background:#1b2b3d;border-radius:16px;padding:20px;margin:14px 0}
h1{font-size:22px} .time{font-size:29px;font-variant-numeric:tabular-nums;font-weight:700}
small{color:#aebfce} button{width:100%;padding:16px;background:#3977dc;color:white;
border:0;border-radius:12px;font-size:17px;font-weight:700}
.warn{color:#ffd288} .ok{color:#a4e5be}
</style></head><body><main>
<h1>ساعة البصمة — فحص فقط</h1>
<p>هذه النسخة تقرأ الوقت ولا تحتوي أمر تعديل أو مزامنة.</p>
<section><small>ساعة ZKTeco</small><div class="time" id="device">—</div></section>
<section><small>ساعة الموبايل (بغداد)</small><div class="time" id="phone">—</div>
<small>الموبايل هو مصدر العرض فقط؛ تأكد أن ساعته مضبوطة.</small></section>
<section><small>فرق التوقيت التقريبي</small><div class="time" id="delta">—</div>
<p id="message"></p></section>
<button id="read">قراءة ساعة الجهاز</button>
<p><small>الاتصال محلي — لا بيانات موظفين، لا رفع سحابي، لا تعديل للسجلات.</small></p>
</main><script>
let lastDeviceTime = null;
function refreshPhone(){
 const now = new Date();
 document.getElementById('phone').textContent = new Intl.DateTimeFormat('en-GB',{
   timeZone:'Asia/Baghdad',hour:'2-digit',minute:'2-digit',second:'2-digit',
   hour12:false}).format(now);
 if(lastDeviceTime){
   const offset = (lastDeviceTime.getTime()-now.getTime())/1000;
   document.getElementById('delta').textContent =
       (offset >= 0 ? '+' : '') + offset.toFixed(1) + ' ثانية';
 }
}
setInterval(refreshPhone,1000);refreshPhone();
document.getElementById('read').addEventListener('click',async()=>{
 const button=document.getElementById('read');
 const message=document.getElementById('message');
 button.disabled=true;message.textContent='جاري القراءة...';
 try{
  const response=await fetch('/api/read',{cache:'no-store'});
  const result=await response.json();
  if(!response.ok||!result.ok) throw new Error(result.error||'Connection failed');
  document.getElementById('device').textContent=result.device_time.replace('T',' ');
  lastDeviceTime=new Date(result.device_time+'+03:00');
  message.className='ok';
  message.textContent='قراءة ناجحة. زمن الاتصال: '+result.duration_ms+' مللي ثانية. الفرق تقريبي.';
  refreshPhone();
 }catch(e){ message.className='warn';message.textContent='فشل الاتصال: '+e.message; }
 finally{button.disabled=false;}
});
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
