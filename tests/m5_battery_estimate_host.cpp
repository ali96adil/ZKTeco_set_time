#include "m5_battery_estimate.h"
#include <cassert>
#include <cmath>
#include <cstdio>

int main() {
  using namespace m5battery;
  assert(estimatePercent(0.0f)==-1);
  assert(estimatePercent(2.70f)==-1);
  assert(estimatePercent(4.5f)==-1);
  assert(estimatePercent(NAN)==-1);
  assert(estimatePercent(INFINITY)==-1);
  assert(estimatePercent(3.30f)==0);
  assert(estimatePercent(3.50f)==5);
  assert(estimatePercent(3.70f)==25);
  assert(estimatePercent(3.80f)==55);
  assert(estimatePercent(3.90f)==78);
  assert(estimatePercent(4.00f)==90);
  assert(estimatePercent(4.20f)==100);
  for(int i=330;i<=420;i++){
    const float v=float(i)/100.0f;
    const int pct=estimatePercent(v);
    assert(pct>=0 && pct<=100);
  }
  assert(estimatePercent(3.66f)<estimatePercent(3.76f));
  assert(!hasUsbPower(0.0f));
  assert(!hasUsbPower(4.2f));
  assert(hasUsbPower(5.0f));
  assert(!hasUsbPower(INFINITY));
  std::puts("AXP192_VOLTAGE_BATTERY_ESTIMATE_TEST_OK");
  return 0;
}
