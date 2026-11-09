"""Regression tests for the isolated ATT_LOG command simulation."""
import json
import subprocess
import sys
from pathlib import Path

from attlog_write_dry_run import (
    COMMAND_ID, DEFAULT_TIMESTAMP, DEFAULT_USER_ID,
    candidate_payload, evaluate_offline,
)


def run():
    payload = candidate_payload(DEFAULT_USER_ID, DEFAULT_TIMESTAMP)
    assert payload.startswith(b"TableName=ATT_LOG\r\nUser_PIN=1733\t")
    assert b"Verify_Time=2026-11-09T14:46:00\tStatus=1" in payload
    assert payload.endswith(b"Work_Code_ID=0\x00")
    assert COMMAND_ID == 3001

    report = evaluate_offline()
    assert report["mode"] == "OFFLINE_SIMULATION_ONLY"
    assert report["network_used"] is False
    assert report["device_write_attempted"] is False
    assert report["real_device_support_proven"] is False
    assert [c["simulated_verified"] for c in report["cases"]] == [True, False, False]
    assert [c["simulated_ack"] for c in report["cases"]] == [True, False, True]

    for bad_id in ("", "-1733", "17\t33", "1733\nCMD", "١٧٣٣", "9" * 17):
        try:
            candidate_payload(bad_id, DEFAULT_TIMESTAMP)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Accepted invalid user ID: {bad_id!r}")

    for bad_time in ("2026-02-30 14:46:00", "2026-11-09T14:46:00", "2026-11-09 14:46:00\n"):
        try:
            candidate_payload(DEFAULT_USER_ID, bad_time)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Accepted invalid time: {bad_time!r}")

    script = Path(__file__).with_name("attlog_write_dry_run.py")
    completed = subprocess.run(
        [sys.executable, str(script)], check=True, capture_output=True, text=True,
    )
    assert json.loads(completed.stdout)["real_device_support_proven"] is False
    source = script.read_text(encoding="utf-8")
    assert "from zk import" not in source
    assert "import socket" not in source
    assert "import requests" not in source
    print("PASS: isolated ATT_LOG candidate / 3 fake responses / validation / no device I/O")


if __name__ == "__main__":
    run()
