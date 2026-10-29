// Offline conformance tests. Never opens a socket or contacts an attendance terminal.
// Reference fixtures from pyzk's __create_header and __encode_time implementations.
#include "zk_wire.h"
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>

static bool frameEquals(const uint8_t* a, const uint8_t* b) {
  return std::memcmp(a,b,16)==0;
}

int main() {
  uint8_t frame[16] = {};
  const uint8_t connectFixture[16] = {
    0x50,0x50,0x82,0x7d,0x08,0,0,0,0xe8,0x03,0x17,0xfc,0,0,0,0
  };
  assert(zkwire::makeReadOnlyFrame(zkwire::kConnect,0,65534,frame));
  assert(frameEquals(frame,connectFixture));

  const uint8_t readFixture[16] = {
    0x50,0x50,0x82,0x7d,0x08,0,0,0,0xc9,0,0xba,0xfe,0x7b,0,0x01,0
  };
  assert(zkwire::makeReadOnlyFrame(zkwire::kGetTime,123,0,frame));
  assert(frameEquals(frame,readFixture));

  const uint8_t exitFixture[16] = {
    0x50,0x50,0x82,0x7d,0x08,0,0,0,0xe9,0x03,0x99,0xfb,0x7b,0,0x02,0
  };
  assert(zkwire::makeReadOnlyFrame(zkwire::kExit,123,1,frame));
  assert(frameEquals(frame,exitFixture));

  // Absolutely no write, delete, supervisor or clock-setting request may be created.
  assert(!zkwire::makeReadOnlyFrame(202,0,0,frame));  // SET_TIME forbidden
  assert(!zkwire::makeReadOnlyFrame(14,0,0,frame));   // CLEAR_DATA forbidden
  assert(!zkwire::makeReadOnlyFrame(15,0,0,frame));   // CLEAR_ATTLOG forbidden
  assert(!zkwire::makeReadOnlyFrame(1003,0,0,frame)); // DISABLEDEVICE forbidden
  assert(!zkwire::makeReadOnlyFrame(20,0,0,frame));   // CLEAR_ADMIN forbidden

  // Correctly bound and validate binary TCP framing.
  const uint8_t goodHeader[8] = {0x50,0x50,0x82,0x7d,0x0c,0,0,0};
  uint32_t length = 0;
  assert(zkwire::getTcpBodyLength(goodHeader,length) && length==12u);
  uint8_t invalidHeader[8];
  std::memcpy(invalidHeader,goodHeader,8);
  invalidHeader[0] = 0;
  assert(!zkwire::getTcpBodyLength(invalidHeader,length));
  std::memcpy(invalidHeader,goodHeader,8);
  zkwire::put32(invalidHeader+4,7);
  assert(!zkwire::getTcpBodyLength(invalidHeader,length));
  zkwire::put32(invalidHeader+4,500000);
  assert(!zkwire::getTcpBodyLength(invalidHeader,length));

  // ZK body with ACK_OK (2000), nonzero session/reply ID, little-endian time.
  const uint8_t goodBody[12] = {
    0xd0,0x07,0,0,0x7b,0,0x02,0,0x70,0x99,0x64,0x33
  };
  zkwire::Reply reply;
  assert(zkwire::parseReplyBody(goodBody,sizeof(goodBody),reply));
  assert(reply.code == 2000 && reply.session == 123 && reply.replyId == 2);
  assert(reply.dataLen==4 && reply.data[0]==0x70);
  assert(!zkwire::parseReplyBody(goodBody,7,reply));
  assert(!zkwire::parseReplyBody(nullptr,12,reply));
  const uint8_t tooLong[zkwire::kMaxBody+1]={};
  assert(!zkwire::parseReplyBody(tooLong,sizeof(tooLong),reply));

  zkwire::CivilTime t;
  // 0x33649970 == 2026-10-29 12:34:56 in ZK time encoding.
  const uint8_t oct29[4] = {0x70,0x99,0x64,0x33};
  assert(zkwire::decodeTime(oct29,t));
  assert(t.year==2026 && t.month==10 && t.day==29);
  assert(t.hour==12 && t.minute==34 && t.second==56);
  const uint8_t leapDay[4] = {0x60,0xbf,0x48,0x2e};
  assert(zkwire::decodeTime(leapDay,t) && t.year==2024 &&
         t.month==2 && t.day==29 && t.hour==11 && t.minute==52);

  // ZK formula can encode non-existent dates; decoder must refuse them.
  const uint32_t feb31 = (26u*12u*31u+1u*31u+30u)*86400u;
  uint8_t invalidDate[4]; zkwire::put32(invalidDate,feb31);
  assert(!zkwire::decodeTime(invalidDate,t));
  const uint8_t hugeDate[4] = {255,255,255,255};
  assert(!zkwire::decodeTime(hugeDate,t));

  std::puts("ZK wire conformance/read-only safety tests: PASS");
  return 0;
}
