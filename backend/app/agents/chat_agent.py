"""
AI CHAT ASSISTANT

This is intentionally NOT a standalone chatbot -- it is a thin
natural-language interface layered on top of the same agent outputs
(eligibility_details, ranked_scholarships, document_checklists,
deadlines) already produced by the Orchestrator for this session. This
keeps every chat answer grounded in the same explainable, tool-derived
data the dashboard shows, avoiding hallucinated eligibility claims.

If an LLM is configured, we use it purely to phrase the answer more
naturally, but we always inject the grounded facts into the prompt and
instruct it not to add unsupported claims. Without an LLM, an
intent-matching fallback still answers the same question set.
"""
import re
from datetime import datetime
from app.llm_client import llm_available, call_llm
from app.tools.scholarship_db_tool import load_all_scholarships

# Generic words that appear in many scholarship names and must never be
# used alone to "match" a specific scholarship mentioned in chat.
_GENERIC_NAME_WORDS = {
    "scholarship", "scholarships", "program", "programme", "students",
    "student", "india", "national", "state", "engineering", "education",
    "for", "the", "and", "welfare", "department", "foundation", "award",
    "grant", "fund", "council", "board", "college", "students'",
}

_SCHOLARSHIP_HINTS = (
    "scholarship", "scholarships", "financial aid", "grant", "grants",
    "eligibility", "eligible", "qualify", "qualification", "documents",
    "deadline", "deadlines", "application", "apply", "benefits",
    "compare scholarships", "scholarship amount", "award", "portal",
    "study opportunity", "study opportunities", "educational opportunity",
    "educational opportunities", "academic opportunity", "academic opportunities",
    "student opportunity", "student opportunities", "funding for education"
)


def _distinctive_words(name: str) -> set:
    return {w.lower().strip(",.") for w in name.split() if len(w) > 4} - _GENERIC_NAME_WORDS


def _find_scholarship_by_name_fragment(session_data: dict, text: str):
    text_l = text.lower()
    best, best_score = None, 0
    for r in session_data.get("ranked_scholarships", []):
        name = r.scholarship_name if hasattr(r, "scholarship_name") else r["scholarship_name"]
        if name.lower() in text_l:
            return r
        overlap = sum(1 for w in _distinctive_words(name) if w in text_l)
        if overlap > best_score:
            best, best_score = r, overlap
    return best


def answer_question(session_data: dict, message: str) -> str:
    ranked = session_data.get("ranked_scholarships", [])
    eligibility = session_data.get("eligibility_details", {})
    deadlines = session_data.get("deadlines", [])
    doc_checklists = session_data.get("document_checklists", [])

    msg = message.strip()
    if not msg:
        return "Please ask a question about scholarships or another topic."

    if _is_greeting(msg):
        return "Hello! 👋 Can I help you find a scholarship opportunity?"

    if _is_farewell(msg):
        return "Goodbye! 👋 Best of luck with your scholarship journey. Can I help you with anything else before you go?"

    query_type = _classify_query(msg)

    if query_type == "UNRELATED":
        return _general_query_fallback(msg)

    matches = _search_dashboard_for_scholarships(msg, ranked)
    if matches:
        return _format_dashboard_matches(msg, matches)

    return (
        "I couldn't find a verified matching scholarship in the current Discover Opportunities Dashboard. "
        "You can try another keyword, country, course, degree level, or scholarship category."
    )


def _normalize_text(message: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s]", " ", message.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _is_greeting(message: str) -> bool:
    normalized = _normalize_text(message)
    greetings = {"hi", "hello", "hey", "hii", "hi there", "hello there", "hey there", "hii there"}
    return normalized in greetings


def _is_farewell(message: str) -> bool:
    normalized = _normalize_text(message)
    farewells = {"bye", "goodbye", "see you"}
    return normalized in farewells


def _classify_query(message: str) -> str:
    normalized = _normalize_text(message)

    if not normalized:
        return "UNRELATED"

    scholarship_hits = sum(1 for hint in _SCHOLARSHIP_HINTS if hint in normalized)

    if scholarship_hits:
        return "SCHOLARSHIP_QUERY"

    return "UNRELATED"


def _general_query_fallback(message: str) -> str:
    if not message.strip():
        return "Please ask a question."

    return (
        "I'm designed to help with scholarships and educational opportunities. Please ask me about "
        "scholarship eligibility, documents, deadlines, applications, or study opportunities."
    )


def _search_dashboard_for_scholarships(message: str, ranked) -> list:
    normalized = _normalize_text(message)
    query_terms = [term for term in normalized.split() if term not in {"scholarship", "scholarships", "apply", "find", "show", "me", "for", "the", "a", "an", "i", "want", "to", "in", "of", "and", "or"}]

    all_scholarships = load_all_scholarships()
    if not query_terms:
        return []

    scored = []
    for scholarship in all_scholarships:
        text_blob = " ".join([
            scholarship.get("name", ""),
            scholarship.get("provider", ""),
            scholarship.get("description", ""),
            " ".join(scholarship.get("eligible_courses", []) or []),
            " ".join(scholarship.get("eligible_states", []) or []),
            " ".join(scholarship.get("category_conditions", []) or []),
        ]).lower()

        score = 0
        match_reasons = []

        for term in query_terms:
            if term in text_blob:
                score += 8

        if any(term in scholarship.get("name", "").lower() for term in query_terms):
            score += 25
            match_reasons.append("Exact scholarship name match")

        provider_text = scholarship.get("provider", "").lower()
        if any(term in provider_text for term in query_terms):
            score += 20
            match_reasons.append("Matching provider or organization")

        course_text = " ".join(scholarship.get("eligible_courses", []) or []).lower()
        if any(term in course_text for term in query_terms):
            score += 15
            match_reasons.append("Matching course or field")

        state_text = " ".join(scholarship.get("eligible_states", []) or []).lower()
        if any(term in state_text for term in query_terms):
            score += 12
            match_reasons.append("Matching country or state")

        category_text = " ".join(scholarship.get("category_conditions", []) or []).lower()
        if any(term in category_text for term in query_terms):
            score += 10
            match_reasons.append("Matching category or funding type")

        # Prefer scholarships already surfaced in the current session when available
        if ranked:
            ranked_names = [str(r.scholarship_name if hasattr(r, "scholarship_name") else r["scholarship_name"]).lower() for r in ranked]
            if scholarship.get("name", "").lower() in ranked_names:
                score += 10
                match_reasons.append("Already in your current scholarship results")

        if score > 0:
            scored.append({
                "scholarship": scholarship,
                "score": score,
                "reasons": match_reasons or ["Relevant opportunity found in the dashboard"],
            })

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:5]


def _deadline_status(application_deadline: str | None) -> str:
    if not application_deadline:
        return "Deadline Not Available"
    try:
        deadline = datetime.strptime(application_deadline, "%Y-%m-%d")
    except Exception:
        return "Deadline Not Available"
    today = datetime.today()
    delta_days = (deadline - today).days
    if delta_days < 0:
        return "Closed"
    if delta_days <= 14:
        return "Closing Soon"
    return "Open"


def _format_dashboard_matches(message: str, matches: list) -> str:
    query = message.strip()
    parts = []

    if matches:
        exact_match = any(item["score"] >= 25 for item in matches)
        if exact_match:
            parts.append("I found the following opportunities related to your request:")
        else:
            parts.append("I couldn't find a verified exact match in the current Discover Opportunities Dashboard. However, I found these similar opportunities you may be interested in:")

        for item in matches:
            scholarship = item["scholarship"]
            status = _deadline_status(scholarship.get("application_deadline"))
            parts.append("")
            parts.append(f"🎓 Scholarship Name: {scholarship.get('name', 'Not available')}")
            parts.append(f"Provider: {scholarship.get('provider', 'Not available')}")
            parts.append(f"Why it matches: {', '.join(item['reasons'])}")
            parts.append(f"Eligibility: {scholarship.get('category_conditions', ['Not available']) or ['Not available']}")
            parts.append(f"Funding: {scholarship.get('scholarship_amount', 'Not available')}")
            parts.append(f"Deadline: {scholarship.get('application_deadline', 'Not available')}")
            parts.append(f"Status: {status}")
            parts.append(f"Official Portal: {scholarship.get('official_url') or 'An official application portal link is currently not available or could not be verified.'}")
    else:
        parts.append("I couldn't find a verified matching scholarship in the current Discover Opportunities Dashboard.")
        parts.append("You can try another keyword, country, course, degree level, or scholarship category.")

    return "\n".join(parts)


def _build_grounded_context(ranked, eligibility, deadlines, doc_checklists, message) -> str:
    lines = []
    for r in ranked[:10]:
        lines.append(f"- {r.scholarship_name}: {r.eligibility_status}, match {r.match_score}%, "
                      f"deadline {r.application_deadline}")
    return "\n".join(lines)


def _rule_based_answer(msg: str, ranked, eligibility, deadlines, doc_checklists) -> str:
    # "which one should I apply for first"
    if re.search(r"first|priority|urgent|start with", msg):
        if deadlines:
            top = deadlines[0]
            return (f"{top.scholarship_name} should be your first priority -- "
                    f"it has {top.days_remaining} day(s) left and is marked {top.priority}.")
        return "I don't have any active deadlines to prioritize yet -- run a scholarship search first."

    # "what documents do I need"
    if re.search(r"document|paperwork|certificate", msg):
        if doc_checklists:
            all_docs = sorted(set(d.document for c in doc_checklists for d in c.documents))
            return "Across your actionable scholarships, you'll need: " + ", ".join(all_docs) + "."
        return "I don't have a document checklist yet -- run a scholarship search first."

    # "can I apply for X" / "am I eligible for X"
    if re.search(r"eligib|qualify|can i apply", msg):
        target = _find_scholarship_by_name_fragment(
            {"ranked_scholarships": ranked}, msg
        )
        if target:
            elig = eligibility.get(target.scholarship_id)
            if elig:
                if elig.status == "ELIGIBLE":
                    return f"Yes -- you meet all {elig.total_count} checked requirements for {target.scholarship_name}."
                if elig.status == "ALMOST_ELIGIBLE":
                    return (f"You meet {elig.passed_count} of {elig.total_count} requirements for "
                            f"{target.scholarship_name}. {elig.missing_requirement_summary or ''}")
                return f"Based on your profile, you don't currently meet the requirements for {target.scholarship_name}."
        if ranked:
            best = ranked[0]
            return (f"I don't have that exact scholarship in view -- but your best current match is "
                    f"{best.scholarship_name} ({best.eligibility_status}, {best.match_score}% match).")
        return "Run a scholarship search first so I have your matches to check against."

    # default
    if ranked:
        best = ranked[0]
        return (f"Your top match right now is {best.scholarship_name} with a {best.match_score}% match "
                f"({best.eligibility_status}). Ask me about eligibility, documents, or deadlines for specifics.")
    return "Tell me about yourself (course, state, CGPA, family income) and I'll find scholarships you're eligible for."
