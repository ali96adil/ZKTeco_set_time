# Missing punch review (employee 1723)

Development-only, read-only feature. No changes to the GOLDEN-BASELINE-01 tag.
No firmware integration or device deployment has occurred.

## Scope
- Review the four *completed* calendar days before the scan date.
- Check only explicitly scheduled workdays, not holidays or rest days.
- Attendance: verified `in` punch no later than 08:30.
- Departure: verified `out` punch at or after 14:45.
- Store findings separately from existing clock-time shortcuts.
- Operator may delete one, all, or notes older than seven days. A later verified scan recreates a deleted note if the punch is still missing.
- Never classify missing punches if the device/export read is incomplete.
- A punch-state mapping must be validated for the specific ZKTeco model/export; an event without reliable direction must not be inferred from its timestamp alone.
- Device logs are never modified. No automatic clock-time changes.

## Modules
- `tools/missing_punch_review.py`: four-day classification
- `tools/missing_punch_notes.py`: local note persistence, deletion and rescan
- `tools/zktime_csv_import.py`: strict CSV import with explicit column/state mappings
- `tools/test_missing_punch_review.py` and `tools/test_missing_punch_notes.py`: basic tests

## Remaining integration work
1. Confirm ZKTime CSV headers, timestamp format, and reliable punch-state semantics.
2. Determine scheduled workdays and holidays; configure local timezone.
3. Implement authenticated, read-only source of complete device records or validated CSV import.
4. Add authenticated UI section for review notes and deletion, separated from device-time presets.
5. Run tests, then verify with real data before flashing M5.
6. Keep sensitive attendance records and local notes out of GitHub.

Run local tests from the project root:
```sh
PYTHONPATH=tools python3 tools/test_missing_punch_review.py
PYTHONPATH=tools python3 tools/test_missing_punch_notes.py
```
