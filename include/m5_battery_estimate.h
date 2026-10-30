#pragma once
// Original M5StickC Plus / AXP192 has voltage ADC, NOT a calibrated SoC
// fuel gauge. This is only an approximate LiPo voltage-derived indicator.
// In particular readings under USB charge or heavy Wi-Fi/TLS load vary.
// No power management register writes are performed.
#include <cmath>
#include <cstdint>

namespace m5battery {
struct Point { float volts; uint8_t percent; };

inline int estimatePercent(float v) {
  if (!std::isfinite(v) || v < 2.8f || v > 4.35f) return -1;
  // Rough resting single-cell LiPo voltage/charge guide; NOT exact remaining
  // capacity. Use battery voltage as the authoritative displayed measurement.
  static const Point curve[] = {
    {3.30f,0}, {3.50f,5}, {3.60f,12}, {3.70f,25},
    {3.75f,40}, {3.80f,55}, {3.85f,68},
    {3.90f,78}, {4.00f,90}, {4.10f,96}, {4.20f,100}
  };
  if (v<=curve[0].volts) return 0;
  const unsigned n=sizeof(curve)/sizeof(curve[0]);
  if(v>=curve[n-1].volts) return 100;
  for(unsigned i=1;i<n;++i){
    if(v<curve[i].volts){
      const float t=(v-curve[i-1].volts)/
                    (curve[i].volts-curve[i-1].volts);
      return int(curve[i-1].percent+
         t*float(curve[i].percent-curve[i-1].percent)+0.5f);
    }
  }
  return 100;
}
inline bool hasUsbPower(float busVoltage) {
  return std::isfinite(busVoltage) && busVoltage>4.4f && busVoltage<5.8f;
}
}
