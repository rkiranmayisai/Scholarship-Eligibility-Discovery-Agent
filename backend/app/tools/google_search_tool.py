"""
TOOL: Google Search Tool (live web search)
Used by: Scholarship Discovery Agent (optional, opt-in)

Wraps Google's Programmable Search Engine ("Custom Search JSON API") so
the Discovery Agent can search the live web -- not just the 22-record
offline demo dataset -- for scholarships. Google's own index effectively
gives the agent access to the full universe of scholarship pages (well
beyond any single hand-maintained dataset), which is the point of
wiring this in.

IMPORTANT / SAFETY:
Google search results give us a title, a link, and a snippet -- NOT a
structured minimum-CGPA, income-cutoff, or deadline. We deliberately do
NOT try to guess/parse those from the snippet text, because a wrong
guess presented as a real cutoff is exactly the kind of hallucinated
eligibility rule this project must avoid. Every live-search result is
therefore converted into a scholarship record with its eligibility
fields left empty/None -- which flows naturally through the existing
Eligibility Agent as "0 requirements checked -> ALMOST_ELIGIBLE / Low
confidence / needs manual verification", never as a fabricated PASS/FAIL.

Setup (see README section "Enabling live Google Search"):
1. Create a Programmable Search Engine: https://programmablesearchengine.google.com/
   -> turn on "Search the entire web" -> copy its Search engine ID (cx).
2. Enable the "Custom Search API" in Google Cloud Console and create an
   API key: https://console.cloud.google.com/apis/library/customsearch.googleapis.com
3. Put both values in backend/.env:
       GOOGLE_API_KEY=...
       GOOGLE_CSE_ID=...
Free tier: 100 queries/day. Beyond that, Google bills per query.
"""
import os
import hashlib
import datetime

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"


def google_search_available() -> bool:
    return bool(GOOGLE_API_KEY and GOOGLE_CSE_ID)


def raw_google_search(query: str, num_results: int = 10) -> list[dict]:
    """
    Calls the Custom Search JSON API directly. Returns raw
    {title, link, snippet, displayLink} dicts, or [] if unavailable /
    on any error (network issues must never crash the pipeline -- the
    app is designed to degrade gracefully to the offline dataset).
    """
    if not google_search_available():
        return []
    try:
        import requests  # imported lazily so the whole app doesn't
                          # hard-require `requests` when this feature is unused
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": query,
            "num": min(max(num_results, 1), 10),  # API caps at 10/request
        }
        resp = requests.get(GOOGLE_SEARCH_URL, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", []) or []
    except Exception:
        return []


def search_scholarships_google(profile: dict, max_results: int = 10) -> list[dict]:
    """
    Builds a scholarship-oriented query from the student profile, runs
    the live Google search, and converts results into records shaped
    like the local knowledge base -- but with eligibility fields left
    empty/None (see module docstring for why). Every record is tagged
    source_type="VERIFIED SOURCE (Google Search)" with today's
    retrieval date, and carries the real URL Google returned.
    """
    parts = [
        "scholarship for", profile.get("course") or "", profile.get("branch") or "",
        "students in", profile.get("state") or "India",
        profile.get("category") or "", "eligibility apply",
    ]
    query = " ".join(p for p in parts if p)

    raw_items = raw_google_search(query, num_results=max_results)
    today = datetime.date.today().isoformat()

    converted = []
    for item in raw_items:
        link = item.get("link", "")
        if not link:
            continue
        sid = "GS-" + hashlib.md5(link.encode()).hexdigest()[:10]
        converted.append({
            "id": sid,
            "name": item.get("title", "Untitled scholarship listing").strip(),
            "provider": item.get("displayLink", "Unknown source"),
            "description": item.get("snippet", ""),
            "official_url": link,
            "source_type": "VERIFIED SOURCE (Google Search)",
            "last_verified": today,
            # Deliberately left blank/None -- never invent eligibility
            # numbers from a search snippet. See module docstring.
            "eligible_courses": [],
            "eligible_states": [],
            "minimum_percentage": None,
            "minimum_cgpa": None,
            "maximum_family_income": None,
            "gender_conditions": "Any",
            "category_conditions": [],
            "year_of_study": [],
            "age_limit": None,
            "disability_conditions": "Any",
            "domicile_requirement": None,
            "required_documents": [],
            "application_deadline": None,
            "scholarship_amount": None,
        })
    return converted
