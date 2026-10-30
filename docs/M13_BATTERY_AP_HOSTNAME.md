# ZK Clock M13: battery estimate and reliable SETUP access

## Hardware and accuracy

Original M5StickC Plus contains AXP192 power management. Its GetBatVoltage() reports measured cell voltage in volts, and GetVBusVoltage() reports USB 5V input. The stock M5StickCPlus library does **not** expose an authoritative calibrated battery state-of-charge percentage. This release estimates charge from a rough single-cell LiPo voltage curve.

- A `~` before the displayed percentage means **approximate**. This indicator can change substantially while charging, under load, at different temperatures or on aged cells.
- `USB` means external power detected, not necessarily active charging. It is not a charging-current or battery-full claim.
- Bad/out-of-range voltage returns `—` rather than an invented percentage.
- Sensor readings are cached for 10 seconds. Both Safari UIs refresh the battery indicator every 30 seconds; the M5 LCD shows a sampled value whenever the screen redraws.

## Network access by mode

- **A — SETUP**: Join the M5 WPA2 Wi-Fi and open **https://192.168.4.1/**. This IP and trusted HTTPS certificate were confirmed to work on an iPhone. `https://zkclock.local` might fail in SoftAP because iOS Bonjour/multicast DNS is not guaranteed; the firmware also starts an AP-only regular DNS responder and tries reducing Wi-Fi power save to improve reception. Do not use plain HTTP and do not bypass certificate warnings.
- **B — CONNECT**: Open **https://zkclock.local/** on the connected LAN, as physically confirmed by the operator. Authenticated operators can see battery status alongside the other device fields.

## Security and functionality

`GET /api/battery` returns voltage, estimated %, and USB state. Accessible on the physically selected M5 WPA2 setup AP, and only to an authenticated browser in CONNECT. It never exposes network passwords, stored credentials or employee records.

**Unchanged:** single-tap phone execution, 700 ms deliberate M5 B hold, 2 second post-write cooldown, independent ZKTeco readback, local NVS configuration and the original trusted M5 TLS key.

## Qualification

The code was compiled in GitHub CI for the production firmware and tested with an offline host estimator test. It must still be tested on the owner's original M5StickC Plus for sensible voltage/% and display layout. SETUP `zkclock.local` availability must not be claimed until confirmed on that exact iPhone/AP pair.
