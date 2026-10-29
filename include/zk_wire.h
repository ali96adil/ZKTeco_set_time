#pragma once
// Pure, host-testable ZKTeco TCP wire helpers.
// Exactly three read-only commands are allowed; no clock-setting opcode exists here.
// Reference: fananimi/pyzk zk/base.py / zk/const.py (ZK terminal protocol).
#include <stdint.h>
#include <stddef.h>
#include <string.h>

namespace zkwire {

static const uint16_t kConnect = 1000;
static const uint16_t kGetTime = 201;
static const uint16_t kExit = 1001;
static const uint16_t kAckOk = 2000;
static const uint16_t kAckUnauth = 2005;
static const uint16_t kMagic1 = 20560;
static const uint16_t kMagic2 = 32130;
static const size_t kMaxBody = 64;
static const size_t kReplyDataCapacity = kMaxBody - 8;

inline uint16_t le16(const uint8_t* data) {
  return uint16_t(data[0]) | (uint16_t(data[1]) << 8);
}
inline uint32_t le32(const uint8_t* data) {
  return uint32_t(data[0]) | (uint32_t(data[1]) << 8) |
         (uint32_t(data[2]) << 16) | (uint32_t(data[3]) << 24);
}
inline void put16(uint8_t* data, uint16_t v) {
  data[0] = uint8_t(v & 255u);
  data[1] = uint8_t(v >> 8);
}
inline void put32(uint8_t* data, uint32_t v) {
  for (int i = 0; i < 4; ++i) data[i] = uint8_t(v >> (8 * i));
}

// Matches pyzk's 16-bit little-endian one's complement checksum.
inline uint16_t checksum(const uint8_t* bytes, size_t count) {
  uint32_t sum = 0;
  size_t i = 0;
  while (i + 1 < count) {
    sum += le16(bytes + i);
    if (sum > 65535u) sum -= 65535u;
    i += 2;
  }
  if (i < count) sum += bytes[i];
  while (sum > 65535u) sum -= 65535u;
  int32_t result = ~static_cast<int32_t>(sum);
  while (result < 0) result += 65535;
  return static_cast<uint16_t>(result);
}

// The request payload has no body; the 8-byte ZK header follows the 8-byte TCP header.
inline bool makeReadOnlyFrame(uint16_t command, uint16_t session,
                              uint16_t priorReplyId, uint8_t out[16]) {
  if (!out || (command != kConnect && command != kGetTime && command != kExit)) return false;
  uint8_t zk[8] = {};
  put16(zk, command);
  put16(zk + 4, session);
  put16(zk + 6, priorReplyId);
  put16(zk + 2, checksum(zk, sizeof(zk)));
  uint32_t nextId = uint32_t(priorReplyId) + 1u;
  if (nextId >= 65535u) nextId -= 65535u;
  put16(zk + 6, uint16_t(nextId));
  memset(out, 0, 16);
  put16(out, kMagic1);
  put16(out + 2, kMagic2);
  put32(out + 4, sizeof(zk));
  memcpy(out + 8, zk, sizeof(zk));
  return true;
}


// Separate, explicitly named SET_TIME encoder for physically authorized
// M5 Button B actions only. This is NEVER routed through HTTP.
// The firmware build flag defaults to disabling real M5 time writes.
inline bool makeSetTimeFrame(uint16_t session, uint16_t priorReplyId,
                             const uint8_t clock[4], uint8_t out[20]) {
  if (!clock || !out) return false;
  uint8_t zk[12] = {};
  put16(zk, 202); // CMD_SET_TIME
  put16(zk + 4, session);
  put16(zk + 6, priorReplyId);
  memcpy(zk + 8, clock, 4);
  put16(zk + 2, checksum(zk, sizeof(zk)));
  uint32_t nextId = uint32_t(priorReplyId) + 1u;
  if (nextId >= 65535u) nextId -= 65535u;
  put16(zk + 6, uint16_t(nextId));
  memset(out, 0, 20);
  put16(out, kMagic1);
  put16(out + 2, kMagic2);
  put32(out + 4, sizeof(zk));
  memcpy(out + 8, zk, sizeof(zk));
  return true;
}

inline bool getTcpBodyLength(const uint8_t header[8], uint32_t& length) {
  if (!header || le16(header) != kMagic1 || le16(header + 2) != kMagic2) return false;
  length = le32(header + 4);
  return length >= 8u && length <= kMaxBody;
}

struct Reply {
  uint16_t code = 0;
  uint16_t session = 0;
  uint16_t replyId = 0;
  uint8_t data[kReplyDataCapacity] = {};
  size_t dataLen = 0;
};
inline bool parseReplyBody(const uint8_t* bytes, size_t length, Reply& reply) {
  if (!bytes || length < 8 || length > kMaxBody) return false;
  Reply parsed;
  parsed.code = le16(bytes);
  parsed.session = le16(bytes + 4);
  parsed.replyId = le16(bytes + 6);
  parsed.dataLen = length - 8;
  if (parsed.dataLen) memcpy(parsed.data, bytes + 8, parsed.dataLen);
  reply = parsed;
  return true;
}

struct CivilTime {
  uint16_t year = 0;
  uint8_t month = 0;
  uint8_t day = 0;
  uint8_t hour = 0;
  uint8_t minute = 0;
  uint8_t second = 0;
};

// ZKTeco time is a local wall-clock date, NOT Unix time / UTC.
inline bool decodeTime(const uint8_t bytes[4], CivilTime& out) {
  if (!bytes) return false;
  uint32_t value = le32(bytes);
  CivilTime t;
  t.second = uint8_t(value % 60); value /= 60;
  t.minute = uint8_t(value % 60); value /= 60;
  t.hour = uint8_t(value % 24); value /= 24;
  t.day = uint8_t(value % 31 + 1); value /= 31;
  t.month = uint8_t(value % 12 + 1); value /= 12;
  const uint32_t year = value + 2000;
  if (year < 2000 || year > 2099) return false;
  t.year = uint16_t(year);
  static const uint8_t monthDays[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
  bool leap = (year % 4 == 0 && (year % 100 != 0 || year % 400 == 0));
  uint8_t maxDay = t.month == 2 && leap ? 29 : monthDays[t.month - 1];
  if (t.day > maxDay) return false;
  out = t;
  return true;
}

inline bool encodeTime(const CivilTime& t, uint8_t output[4]) {
  if (!output || t.year < 2000 || t.year > 2099 ||
      t.month < 1 || t.month > 12 || t.day < 1 || t.day > 31 ||
      t.hour > 23 || t.minute > 59 || t.second > 59) return false;
  static const uint8_t days[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
  bool leap = t.year % 4 == 0 && (t.year % 100 != 0 || t.year % 400 == 0);
  const uint8_t maxD = t.month == 2 && leap ? 29 : days[t.month - 1];
  if (t.day > maxD) return false;
  uint32_t v = (((uint32_t(t.year - 2000) * 12 + (t.month - 1)) * 31 +
                (t.day - 1)) * 86400)
                + (uint32_t(t.hour)*3600) + (t.minute*60) + t.second;
  put32(output, v);
  return true;
}

// Proleptic Gregorian seconds, for difference/confirmation (not ZK encoding).
inline int64_t civilSeconds(const CivilTime& t) {
  static const uint8_t days[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
  int64_t total = 0;
  for (uint16_t y=2000; y<t.year; ++y)
    total += ((y%4==0 && (y%100!=0 || y%400==0)) ? 366 : 365) * 86400LL;
  for (uint8_t m=1; m<t.month; ++m) {
    total += days[m-1]*86400LL;
    if (m == 2 && t.year%4==0 && (t.year%100!=0 || t.year%400==0))
      total += 86400LL;
  }
  total += (t.day-1)*86400LL + t.hour*3600LL + t.minute*60LL + t.second;
  return total;
}

} // namespace zkwire
