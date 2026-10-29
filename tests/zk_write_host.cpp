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
