"""
AGENT 4 -- SCHOLARSHIP RANKING AGENT

Responsibility: turn eligibility + profile-fit signals into an
explainable match score and priority ordering.

Score breakdown (0-100) is a weighted blend of:
- eligibility confidence (requirement pass rate)          40%
- retrieval / semantic relevance to profile                15%
- deadline urgency (sooner deadlines score slightly higher) 15%
- scholarship amount (normalized within candidate set)      15%
- direct match bonuses (state/category/course/gender)       15%
"""
import datetime as dt
from app.models import RankedScholarship
from app.tools.deadline_tool import days_remaining, classify_priority


class RankingAgent:
    name = "Ranking Agent"
    icon = "📊"

    def run(self, profile: dict, scholarships: list, eligibility_map: dict) -> list:
        amounts = [s.get("scholarship_amount") or 0 for s in scholarships]
        max_amount = max(amounts) if amounts else 1
        max_amount = max_amount or 1

        ranked_list = []
        for s in scholarships:
            elig = eligibility_map.get(s["id"])
            if elig is None:
                continue

            elig_score = (elig.passed_count / elig.total_count) if elig.total_count else 0.5
            retrieval_score = min(s.get("_retrieval_score", 0.0) * 4, 1.0)  # scale TF-IDF sim into 0-1-ish

            deadline = s.get("application_deadline")
            days_left = None
            deadline_score = 0.5
            if deadline:
                try:
                    days_left = days_remaining(deadline)
                    if days_left < 0:
                        deadline_score = 0.0
                    else:
                        deadline_score = max(0.0, 1 - (days_left / 90))
                except Exception:
                    days_left = None

            amount_score = (s.get("scholarship_amount") or 0) / max_amount

            bonus = 0.0
            if profile.get("state") and s.get("eligible_states") and any(
                es.lower() == profile["state"].lower() for es in s["eligible_states"]
            ):
                bonus += 0.4
            if profile.get("category") and s.get("category_conditions") and any(
                c.lower() == profile["category"].lower() for c in s["category_conditions"]
            ):
                bonus += 0.3
            if profile.get("gender") and s.get("gender_conditions", "any").lower() == profile["gender"].lower():
                bonus += 0.3
            bonus = min(bonus, 1.0)

            breakdown = {
                "eligibility_confidence": round(elig_score * 40, 1),
                "profile_relevance": round(retrieval_score * 15, 1),
                "deadline_urgency": round(deadline_score * 15, 1),
                "scholarship_amount": round(amount_score * 15, 1),
                "direct_match_bonus": round(bonus * 15, 1),
            }
            match_score = round(sum(breakdown.values()), 1)
            match_score = min(match_score, 99.0)  # never claim 100% -- eligibility can always change

            if elig.status == "NOT_ELIGIBLE":
                match_score = round(match_score * 0.35, 1)  # heavily deprioritize ineligible ones

            ranked_list.append(RankedScholarship(
                scholarship_id=s["id"],
                scholarship_name=s["name"],
                provider=s["provider"],
                match_score=match_score,
                eligibility_status=elig.status,
                scholarship_amount=s.get("scholarship_amount"),
                application_deadline=deadline,
                days_remaining=days_left,
                priority=classify_priority(days_left) if days_left is not None else None,
                source_type=s.get("source_type", "DEMO DATA"),
                official_url=s.get("official_url", ""),
                score_breakdown=breakdown,
                verification_status=s.get("verification_status"),
                evidence=s.get("evidence") or [],
                secondary_sources=s.get("secondary_sources") or [],
            ))

        ranked_list.sort(key=lambda r: r.match_score, reverse=True)
        return ranked_list
