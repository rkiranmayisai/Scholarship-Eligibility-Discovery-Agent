"""
TOOL: Scholarship Extraction Tool
Used by: Scholarship Discovery Agent

Given a search-result hit (title/link/snippet) plus the fetched page's
visible text, extracts the structured scholarship schema the Discovery
Agent spec requires -- and, critically, records the EVIDENCE (the
actual sentence a value was read from, plus its source URL) behind every
extracted field. Fields that cannot be found are left as None /
"Not specified" / [] -- never guessed.
"""
import re
import datetime
from app.tools.profile_extraction_tool import (
    INDIAN_STATES, CATEGORY_KEYWORDS, COURSE_KEYWORDS, BRANCH_KEYWORDS, keyword_regex_match,
)

DOCUMENT_KEYWORDS = [
    "Aadhaar", "Income Certificate", "Bonafide Certificate", "Marksheet",
    "Bank Passbook", "Caste Certificate", "Domicile Certificate",
    "Disability Certificate", "College ID", "Admission Letter",
]

CATEGORY_LABELS = {"SC": "SC", "ST": "ST", "OBC": "OBC", "EWS": "EWS",
                    "Minority": "Minority", "BC": "BC", "General": "General"}


def _sentence_containing(text: str, match_span: tuple) -> str:
    """Returns the text window around a regex match, for use as evidence."""
    if not text:
        return ""
    start, end = match_span
    window_start = max(0, start - 120)
    window_end = min(len(text), end + 120)
    snippet = text[window_start:window_end].strip()
    return ("..." if window_start > 0 else "") + snippet + ("..." if window_end < len(text) else "")


def _add_evidence(evidence_list: list, field: str, value, text: str, match, source_url: str):
    evidence_list.append({
        "field": field,
        "value": value,
        "evidence": _sentence_containing(text, match.span()) if match else "Found in search result snippet/title.",
        "source_url": source_url,
    })


def extract_structured_record(search_item: dict, page_text, source_tier: str) -> dict:
    """
    search_item: {"name"/"title", "provider"/"displayLink", "description"/"snippet", "official_url"/"link"}
    page_text: fetched visible page text, or None if fetch failed/unavailable
    source_tier: "TIER1" / "TIER2" / "TIER3" / "UNKNOWN" (from source_tiers.py)
    """
    title = (search_item.get("name") or search_item.get("title") or "").strip()
    snippet = (search_item.get("description") or search_item.get("snippet") or "").strip()
    url = search_item.get("official_url") or search_item.get("link") or ""
    display_source = search_item.get("provider") or search_item.get("displayLink") or url

    combined_text = "{}. {}. {}".format(title, snippet, page_text or "")
    evidence = []

    record = {
        "scholarship_name": title or None,
        "provider": None,
        "provider_type": None,
        "description": snippet or None,
        "scholarship_category": None,
        "country": "India",
        "state": None,
        "degree": [],
        "branches": [],
        "academic_year": [],
        "minimum_cgpa": None,
        "maximum_income": None,
        "domicile_requirement": None,
        "institution_type": [],
        "gender_requirement": "Any",
        "category_requirement": None,
        "age_requirement": "Not specified",
        "benefit": None,
        "amount": None,
        "duration": None,
        "required_documents": [],
        "application_start_date": None,
        "application_deadline": None,
        "application_url": url or None,
        "source_url": url or None,
        "source_name": display_source or None,
        "verification_status": None,
        "last_checked": datetime.date.today().isoformat(),
        "evidence": evidence,
    }

    if source_tier == "TIER1":
        record["provider"] = display_source
        record["provider_type"] = "Government"
    elif source_tier == "TIER2":
        record["provider"] = display_source
        record["provider_type"] = "Private / Corporate / NGO"
    else:
        record["provider"] = None
        record["provider_type"] = "Unknown (discovered via aggregator/listing site)"

    for state in INDIAN_STATES:
        m = re.search(r"\b" + re.escape(state) + r"\b", combined_text, re.I)
        if m:
            record["state"] = state
            record["domicile_requirement"] = state
            _add_evidence(evidence, "state", state, combined_text, m, url)
            break

    for course in COURSE_KEYWORDS:
        m = keyword_regex_match(course, combined_text)
        if m and course not in record["degree"]:
            record["degree"].append(course)
            _add_evidence(evidence, "degree", course, combined_text, m, url)

    for branch in BRANCH_KEYWORDS:
        m = keyword_regex_match(branch, combined_text)
        if m and branch not in record["branches"]:
            record["branches"].append(branch)
            _add_evidence(evidence, "branches", branch, combined_text, m, url)

    m = re.search(r"\b(1st|2nd|3rd|4th|first|second|third|fourth|final)\s*[- ]?\s*year\b", combined_text, re.I)
    if m:
        record["academic_year"] = [m.group(1)]
        _add_evidence(evidence, "academic_year", m.group(1), combined_text, m, url)

    m = re.search(r"(?:minimum\s+)?cgpa[^\d]{0,15}(\d(?:\.\d{1,2})?)", combined_text, re.I)
    if m:
        record["minimum_cgpa"] = float(m.group(1))
        _add_evidence(evidence, "minimum_cgpa", record["minimum_cgpa"], combined_text, m, url)

    m = re.search(
        r"(?:income|family income)[^\d\u20b9]{0,20}(?:below|up\s*to|not\s*exceed(?:ing)?|maximum\s*of)?\s*"
        r"(?:\u20b9|rs\.?|inr)?\s*([\d,.]+)\s*(lakh|lac|l\b|thousand|k\b)?",
        combined_text, re.I,
    )
    if m:
        num = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        if unit in ("lakh", "lac", "l"):
            num *= 100000
        elif unit in ("thousand", "k"):
            num *= 1000
        record["maximum_income"] = num
        _add_evidence(evidence, "maximum_income", num, combined_text, m, url)

    m = re.search(r"\b(girls?|women|female)\b", combined_text, re.I)
    if m:
        record["gender_requirement"] = "Female"
        _add_evidence(evidence, "gender_requirement", "Female", combined_text, m, url)

    for cat in CATEGORY_KEYWORDS:
        m = re.search(r"\b" + re.escape(cat) + r"\b", combined_text, re.I)
        if m:
            record["category_requirement"] = CATEGORY_LABELS.get(cat, cat)
            _add_evidence(evidence, "category_requirement", record["category_requirement"], combined_text, m, url)
            break

    m = re.search(r"age[^\d]{0,15}(?:below|up\s*to|not\s*exceed(?:ing)?|maximum\s*of)?\s*(\d{2})\s*years?", combined_text, re.I)
    if m:
        record["age_requirement"] = "Up to {} years".format(m.group(1))
        _add_evidence(evidence, "age_requirement", record["age_requirement"], combined_text, m, url)

    m = re.search(r"government\s+college|govt\.?\s*college", combined_text, re.I)
    if m:
        record["institution_type"].append("Government")
        _add_evidence(evidence, "institution_type", "Government", combined_text, m, url)
    m = re.search(r"private\s+college", combined_text, re.I)
    if m:
        record["institution_type"].append("Private")
        _add_evidence(evidence, "institution_type", "Private", combined_text, m, url)

    m = re.search(
        r"(?:scholarship\s+(?:of|worth|amount)|award\s+of|stipend\s+of)[^\d\u20b9]{0,10}"
        r"(?:\u20b9|rs\.?|inr)?\s*([\d,.]+)\s*(lakh|lac|l\b|thousand|k\b)?",
        combined_text, re.I,
    )
    if m:
        num = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        if unit in ("lakh", "lac", "l"):
            num *= 100000
        elif unit in ("thousand", "k"):
            num *= 1000
        record["amount"] = num
        record["benefit"] = "Financial award (\u20b9{:,})".format(int(num))
        _add_evidence(evidence, "amount", num, combined_text, m, url)

    m = re.search(r"\b(per\s+year|per\s+annum|annual(?:ly)?|one[- ]time|per\s+month|monthly)\b", combined_text, re.I)
    if m:
        record["duration"] = m.group(1)
        _add_evidence(evidence, "duration", m.group(1), combined_text, m, url)

    for doc in DOCUMENT_KEYWORDS:
        m = re.search(r"\b" + re.escape(doc) + r"\b", combined_text, re.I)
        if m:
            record["required_documents"].append(doc)
            _add_evidence(evidence, "required_documents", doc, combined_text, m, url)

    date_pattern = r"(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{4})"
    m = re.search(r"(?:last\s+date|deadline|apply\s+by|closes?\s+on)[^\d]{0,20}" + date_pattern, combined_text, re.I)
    if m:
        record["application_deadline"] = m.group(1)
        _add_evidence(evidence, "application_deadline", m.group(1), combined_text, m, url)
    m2 = re.search(r"(?:applications?\s+open|starts?\s+on|from)[^\d]{0,20}" + date_pattern, combined_text, re.I)
    if m2:
        record["application_start_date"] = m2.group(1)
        _add_evidence(evidence, "application_start_date", m2.group(1), combined_text, m2, url)

    if re.search(r"\bmerit\b", combined_text, re.I):
        record["scholarship_category"] = "Merit-based"
    elif re.search(r"\bneed[- ]based\b|financial(?:ly)?\s+(?:need|hardship)", combined_text, re.I):
        record["scholarship_category"] = "Need-based"
    elif record["category_requirement"]:
        record["scholarship_category"] = "{} category-based".format(record["category_requirement"])
    elif record["gender_requirement"] == "Female":
        record["scholarship_category"] = "Women in STEM / Gender-focused"

    return record
