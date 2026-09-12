"""
AGENT 6 -- DEADLINE & PRIORITY AGENT

Responsibility: analyze scholarship deadlines and classify urgency, and
recommend which application the student should tackle first.
"""
from app.models import DeadlineInfo
from app.tools.deadline_tool import days_remaining, classify_priority


class DeadlineAgent:
    name = "Deadline Agent"
    icon = "⏰"

    def run(self, scholarships: list) -> list:
        results = []
        for s in scholarships:
            deadline = s.get("application_deadline")
            if not deadline:
                continue
            try:
                days = days_remaining(deadline)
            except Exception:
                continue
            if days < 0:
                continue  # expired -- do not recommend
            results.append(DeadlineInfo(
                scholarship_id=s["id"],
                scholarship_name=s["name"],
                deadline=deadline,
                days_remaining=days,
                priority=classify_priority(days),
            ))
        results.sort(key=lambda d: d.days_remaining)
        return results

    def recommend_first(self, deadlines: list) -> str | None:
        if not deadlines:
            return None
        return deadlines[0].scholarship_name
