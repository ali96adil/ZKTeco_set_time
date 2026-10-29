#pragma once
// Switch ONLY the LCD backlight off after a user-configured idle interval.
// ESP32 keeps handling WLAN/HTTP and RTC. Never deep-sleep network transport.
#include <Arduino.h>
#include <Preferences.h>
#include <M5StickCPlus.h>

class ScreenIdle {
  uint32_t lastUseMs = 0;
  bool dark = false;
  uint16_t timeoutSecs = 30;

 public:
  void begin() {
    Preferences p;
    p.begin("zk-display", true);
    uint16_t loaded = p.getUShort("timeout", 30);
    p.end();
    timeoutSecs = valid(loaded) ? loaded : 30;
    lastUseMs = millis();
  }
  static bool valid(uint16_t secs) {
    return secs == 0 || secs == 15 || secs == 30 ||
           secs == 60 || secs == 120;
  }
  uint16_t timeout() const { return timeoutSecs; }
  bool sleeping() const { return dark; }

  bool save(uint16_t secs) {
    if (!valid(secs)) return false;
    Preferences p;
    if (!p.begin("zk-display", false)) return false;
    size_t written = p.putUShort("timeout", secs);
    p.end();
    if (written != sizeof(uint16_t)) return false;
    timeoutSecs = secs;
    touch();
    return true;
  }

  void touch() {
    lastUseMs = millis();
    if (dark) {
      M5.Axp.ScreenSwitch(true);
      dark = false;
    }
  }

  void update() {
    if (!dark && timeoutSecs && !((millis() - lastUseMs) < (uint32_t)timeoutSecs*1000UL)) {
      M5.Axp.ScreenSwitch(false); // backlight only, no Wi-Fi disconnect
      dark = true;
    }
  }
};
