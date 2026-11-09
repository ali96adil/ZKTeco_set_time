# ATT_LOG CMD_SET_DATA research — OFFLINE ONLY

## Device under study
- ZKTeco iFace950, ZMM220_TFT, firmware Ver 6.60 May 14 2018.
- Physical device `10.1.65.2:4370` was previously read over pyzk TCP, with 37,812 log entries.
- Operator's proposed trial is user 1733 / 2026-11-09 14:46:00, intended as check-out.
- Prior user existence and absence of exact timestamp were read without writing.
- A private JSON snapshot was saved under `local/device_backups/` (gitignored). JSON is **not** proven to be restorable to device firmware.

## Evidence and limits
- The third-party `taha-rafi/php-zkteco` code claims `CMD_SET_DATA=3001` with a `TableName=ATT_LOG` payload. Its own live test is not evidence it has been tested against this precise device/firmware.
- ZKTeco standalone SDK manuals document writing selected PULL protocol tables, subject to firmware support. They do **not** establish ATT_LOG record insertion support on iFace950 Ver 6.60.
- `get_compat_old_firmware=1`, `get_extend_fmt=1`, `get_user_extend_fmt=1`, `get_fp_version=10` are capabilities/settings, not evidence that `CMD_SET_DATA` may write attendance.
- The device currently reports status=15 and punch=1 for raw punches that ZKTime interprets based on schedule; do not mislabel manual insertions as biometric verification.
- **No confirmed direct physical write or edit of an attendance event.**

## Test (safe: no device/network access)
```sh
cd "$HOME/zkteco-m5-lab/ZKTeco_set_time"
git pull --ff-only
PYTHONPATH=tools python3 tools/test_attlog_write_dry_run.py
PYTHONPATH=tools python3 tools/attlog_write_dry_run.py --user-id 1733 --timestamp "2026-11-09 14:46:00"
```

This runs three **fake-device** scenarios: accepted+stored, rejected, and acknowledged-but-not-stored. The final scenario demonstrates why an ACK alone cannot prove a record was saved. The output is `OFFLINE_SIMULATION_ONLY` and always declares `device_write_attempted=false`.

The script does not import pyzk/sockets, connect to any device, issue an SDK command, or save any attendance record. `Verify_Type=0` is only a placeholder in the candidate payload: it has **not** been validated on this firmware.

## Next validation gate
Before any live write on a separate test terminal, verify the exact protocol table/fields for the firmware from authoritative sources, obtain a restorable full device backup, use an explicitly marked non-biometric test record, and verify persistence by disconnecting/reconnecting and reading directly from the test device. Do not run speculative writes against the current unit. Do not change the existing `GOLDEN-BASELINE-01` reference, flash M5, or store attendance records in Git.
