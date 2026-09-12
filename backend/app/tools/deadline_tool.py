"""
TOOL: Deadline Calculator Tool
Used by: Deadline & Priority Agent
"""
import datetime as dt


def days_remaining(deadline_str: str, today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    deadline = dt.datetime.strptime(deadline_str, "%Y-%m-%d").date()
    return (deadline - today).days


def classify_priority(days: int) -> str:
    if days < 0:
        return "Expired"
    if days <= 10:
        return "Urgent"
    if days <= 25:
        return "Apply Soon"
    return "Later"
