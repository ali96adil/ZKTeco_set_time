"""Offline ONLY candidate ATT_LOG writer protocol study.

No network, no ZKTeco library, no filesystem writes, no physical device commands.
The candidate payload mirrors an unverified third-party CMD_SET_DATA example.
An offline ACK/readback is not evidence of iFace950 firmware support.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime

COMMAND_NAME = "CMD_SET_DATA"
COMMAND_ID = 3001
DEFAULT_USER_ID = "1733"
DEFAULT_TIMESTAMP = "2026-11-09 14:46:00"


def candidate_payload(user_id: str, timestamp: str) -> bytes:
    """Build the third-party candidate for inspection; never transmit it.

    Verify_Type=0 is an arbitrary placeholder. Its meaning on this iFace950
    has NOT been validated. This must never be labelled a fingerprint event.
    """
    if not re.fullmatch(r"[0-9]{1,16}", user_id):
        raise ValueError("User ID must contain 1-16 ASCII digits")
    try:
        parsed = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError("Timestamp must be a real date in YYYY-MM-DD HH:MM:SS") from exc
    if parsed.strftime("%Y-%m-%d %H:%M:%S") != timestamp:
        raise ValueError("Timestamp is not canonical")
    fields = (
        f"TableName=ATT_LOG\r\n"
        f"User_PIN={user_id}\t"
        f"Verify_Type=0\t"
        f"Verify_Time={parsed.strftime('%Y-%m-%dT%H:%M:%S')}\t"
        f"Status=1\tWork_Code_ID=0\x00"
    )
    return fields.encode("ascii")


class OfflineFakeDevice:
    """Memory-only stand-in for THREE hypothetical firmware responses."""

    def __init__(self, behavior: str):
        if behavior not in ("accept_and_store", "reject", "ack_without_storing"):
            raise ValueError("Unknown offline scenario")
        self.behavior = behavior
        self.records = set()

    def submit(self, command: int, payload: bytes) -> bool:
        if command != COMMAND_ID or not payload.startswith(b"TableName=ATT_LOG\r\n"):
            return False
        if self.behavior == "reject":
            return False
        if self.behavior == "accept_and_store":
            self.records.add(payload)
        return True

    def contains(self, payload: bytes) -> bool:
        return payload in self.records


def evaluate_offline(user_id=DEFAULT_USER_ID, timestamp=DEFAULT_TIMESTAMP):
    payload = candidate_payload(user_id, timestamp)
    cases = []
    for behavior in ("accept_and_store", "reject", "ack_without_storing"):
        fake = OfflineFakeDevice(behavior)
        acknowledged = fake.submit(COMMAND_ID, payload)
        readback = fake.contains(payload)
        cases.append({
            "offline_scenario": behavior,
            "simulated_ack": acknowledged,
            "simulated_readback": readback,
            "simulated_verified": acknowledged and readback,
        })
    return {
        "mode": "OFFLINE_SIMULATION_ONLY",
        "target_user_id": user_id,
        "target_timestamp": timestamp,
        "intended_punch": "check_out (hypothesis)",
        "candidate_command": COMMAND_ID,
        "candidate_payload_sha256": hashlib.sha256(payload).hexdigest(),
        "payload_size": len(payload),
        "verification_type": "unvalidated_placeholder_0",
        "cases": cases,
        "network_used": False,
        "device_write_attempted": False,
        "real_device_support_proven": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--timestamp", default=DEFAULT_TIMESTAMP)
    args = parser.parse_args()
    try:
        report = evaluate_offline(args.user_id, args.timestamp)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
