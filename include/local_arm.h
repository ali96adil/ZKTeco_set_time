#pragma once
// Local physical authorization for on-device *non-secret* editing only.
// Not a substitute for TLS on the open campus Wi-Fi.
#include <Arduino.h>
class LocalArm {
  uint32_t armedAt = 0;
  bool enabled = false;
public:
  static constexpr uint32_t kWindowMs = 90000;
  void grant() { armedAt = millis(); enabled = true; }
  void revoke() { enabled = false; }
  bool allowed() const { return enabled && (millis()-armedAt)<kWindowMs; }
  unsigned seconds() const {
    return allowed() ? (kWindowMs-(millis()-armedAt)+999)/1000 : 0;
  }
};
