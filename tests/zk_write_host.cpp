// Host validation for opt-in M5 physical-button command encoder only.
// No network traffic, no real attendance device.
#include "zk_wire.h"
#include <cassert>
#include <cstring>
#include <cstdio>

int main() {
  zkwire::CivilTime date;
  date.year=2026; date.month=10; date.day=29;
  date.hour=8; date.minute=15; date.second=30;
  uint8_t time[4] = {};
  assert(zkwire::encodeTime(date,time));
  zkwire::CivilTime decoded;
  assert(zkwire::decodeTime(time,decoded));
  assert(decoded.year==date.year && decoded.month==date.month);
  assert(decoded.day==date.day && decoded.hour==date.hour);
  assert(decoded.minute==date.minute && decoded.second==date.second);

  uint8_t frame[20] = {};
  assert(zkwire::makeSetTimeFrame(123,1,time,frame));
  assert(zkwire::le16(frame)==zkwire::kMagic1);
  assert(zkwire::le16(frame+2)==zkwire::kMagic2);
  assert(zkwire::le32(frame+4)==12);
  assert(zkwire::le16(frame+8)==202);
  assert(zkwire::le16(frame+12)==123);
  assert(zkwire::le16(frame+14)==2);
  assert(std::memcmp(frame+16,time,4)==0);

  // Independent byte-for-byte fixture generated using fananimi/pyzk:
  // create_header(CMD_SET_TIME=202, <I encoded time>, session=123,
  // reply_id=1). The checksum is intentionally computed BEFORE incrementing
  // reply_id; this is pyzk's actual wire behavior, not a checksum bug.
  const uint8_t reference[20] = {
    0x50,0x50,0x82,0x7d,0x0c,0,0,0,
    0xca,0x00,0xb2,0x6e,0x7b,0x00,0x02,0x00,
    0xa2,0x5c,0x64,0x33
  };
  assert(std::memcmp(frame,reference,sizeof(reference))==0);
  assert(zkwire::checksum(frame+8,2+2+2+2+4)!=zkwire::le16(frame+10));


  zkwire::CivilTime bad=date;
  bad.year=2026;bad.month=2;bad.day=29;
  assert(!zkwire::encodeTime(bad,time));
  zkwire::CivilTime leap=date;
  leap.year=2024;leap.month=2;leap.day=29;
  assert(zkwire::encodeTime(leap,time));
  assert(zkwire::decodeTime(time,decoded)&&decoded.day==29);
  zkwire::CivilTime tomorrow=date;
  tomorrow.day=30;
  assert(zkwire::civilSeconds(tomorrow)-zkwire::civilSeconds(date)==86400);
  std::puts("M4 physical-only frame, encode/decode and Gregorian limit: PASS");
}
