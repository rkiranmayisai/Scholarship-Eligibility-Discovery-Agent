"""
TOOL: Scholarship Database Tool
Used by: Scholarship Discovery Agent

Reads the local scholarship knowledge base (acts as the offline
fallback / demo dataset required by the problem statement so the
system works even without live web access to government portals).
"""
import json
import os
from functools import lru_cache

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "scholarships.json")


@lru_cache(maxsize=1)
def load_all_scholarships() -> list:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_scholarship_by_id(scholarship_id: str) -> dict | None:
    for s in load_all_scholarships():
        if s["id"] == scholarship_id:
            return s
    return None


def coarse_filter(profile: dict) -> list:
    """
    Cheap pre-filter used by the Discovery Agent before handing candidates
    to the vector search / RAG tool and the Eligibility Agent. Mirrors how
    a real system would narrow thousands of scholarships down before doing
    expensive semantic retrieval.
    """
    course = (profile.get("course") or "").lower()
    branch = (profile.get("branch") or "").lower()
    state = (profile.get("state") or "").lower()

    candidates = []
    for s in load_all_scholarships():
        course_ok = True
        if s.get("eligible_courses"):
            course_ok = any(
                "any" in ec.lower() or course in ec.lower() or (branch and branch in ec.lower())
                for ec in s["eligible_courses"]
            ) if course or branch else True
        state_ok = True
        if s.get("eligible_states"):
            state_ok = any(
                es.lower() == "all india" or (state and state in es.lower())
                for es in s["eligible_states"]
            ) if state else True
        if course_ok and state_ok:
            candidates.append(s)
    return candidates if candidates else load_all_scholarships()
