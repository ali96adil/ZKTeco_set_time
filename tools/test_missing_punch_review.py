from datetime import date, datetime
from missing_punch_review import review_previous_four_days

def test_four_days():
    today = date(2026, 11, 6)
    days = [date(2026, 11, x) for x in (2, 3, 4, 5)]
    events = [
        {"employee_id":"24","timestamp":datetime(2026,11,2,8,15),"kind":"in"},
        {"employee_id":"24","timestamp":datetime(2026,11,2,14,46),"kind":"out"},
        {"employee_id":"24","timestamp":datetime(2026,11,3,14,46),"kind":"out"},
        {"employee_id":"24","timestamp":datetime(2026,11,4,8,15),"kind":"in"},
        {"employee_id":"24","timestamp":datetime(2026,11,5,8,15),"kind":"in"},
        {"employee_id":"99","timestamp":datetime(2026,11,5,14,46),"kind":"out"},
    ]
    result = review_previous_four_days("24", events, today=today, complete_days=days[:3], workdays=days)
    assert [r["status"] for r in result] == [
        "COMPLETE", "REVIEW_REQUIRED", "REVIEW_REQUIRED", "UNKNOWN_INCOMPLETE_READ"]
    assert result[1]["missing"] == ["attendance"]
    assert result[2]["missing"] == ["departure"]
    assert result[3]["missing"] == []

if __name__ == "__main__":
    test_four_days()
    print("OK")
