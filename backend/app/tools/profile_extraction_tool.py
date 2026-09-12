"""
TOOL: Profile Extraction Tool
Used by: Profile Analyzer Agent

Extracts structured fields out of a free-text student description.
Tries an LLM first (if configured); otherwise falls back to a robust
regex/keyword extractor so the tool always returns a usable result.
"""
import re
import json
from app.llm_client import llm_available, call_llm

INDIAN_STATES = [
    "Telangana", "Andhra Pradesh", "Karnataka", "Tamil Nadu", "Kerala",
    "Maharashtra", "Gujarat", "Rajasthan", "Uttar Pradesh", "Bihar",
    "West Bengal", "Odisha", "Punjab", "Haryana", "Madhya Pradesh",
    "Assam", "Meghalaya", "Manipur", "Mizoram", "Nagaland", "Tripura",
    "Arunachal Pradesh", "Sikkim", "Delhi", "Chhattisgarh", "Jharkhand",
    "Uttarakhand", "Himachal Pradesh", "Goa", "Jammu and Kashmir",
]

CATEGORY_KEYWORDS = ["General", "OBC", "SC", "ST", "EWS", "Minority", "BC"]

COURSE_KEYWORDS = [
    "B.Tech", "BTech", "B.E", "BE", "B.Sc", "BSc", "B.Com", "BCom",
    "B.A", "BA", "MBBS", "MBA", "Diploma", "M.Tech", "MTech", "M.Sc", "MSc",
]

# Short 2-letter abbreviations collide with ordinary English words
# ("be", "ba") when matched case-insensitively -- e.g. "income should be
# below X" must NOT be read as a "BE" (Bachelor of Engineering) mention.
# These are matched case-sensitively instead; everything else stays
# case-insensitive since longer keywords carry enough distinctiveness.
_CASE_SENSITIVE_KEYWORDS = {"BE", "BA", "IT", "AI"}


def keyword_regex_match(keyword: str, text: str):
    """Shared helper: case-sensitive for ambiguous short keywords (BE/BA),
    case-insensitive otherwise. Used for course/branch keyword matching
    across both the student-profile parser and the live-discovery
    extraction tool, so both apply the same false-positive guard."""
    flags = 0 if keyword in _CASE_SENSITIVE_KEYWORDS else re.I
    return re.search(r"\b" + re.escape(keyword) + r"\b", text, flags)

BRANCH_KEYWORDS = [
    "CSE", "Computer Science", "IT", "Information Technology", "ECE",
    "Electronics", "Mechanical", "Civil", "EEE", "Electrical", "AIML",
    "Data Science", "AI", "Chemical", "Biotechnology",
]

YEAR_PATTERNS = {
    "first": "1", "1st": "1", "second": "2", "2nd": "2",
    "third": "3", "3rd": "3", "fourth": "4", "4th": "4", "final": "4",
}


def _regex_extract(text: str) -> dict:
    result = {}
    t = text

    # Age
    m = re.search(r"(\d{2})\s*[- ]?\s*year[s]?[- ]?old", t, re.I)
    if not m:
        m = re.search(r"\bage[d]?\s*:?\s*(\d{2})\b", t, re.I)
    if m:
        result["age"] = int(m.group(1))

    # State / domicile
    for state in INDIAN_STATES:
        if state.lower() in t.lower():
            result["state"] = state
            result["domicile"] = state
            break

    # Gender
    if re.search(r"\b(female|girl|woman)\b", t, re.I):
        result["gender"] = "Female"
    elif re.search(r"\b(male|boy|man)\b", t, re.I):
        result["gender"] = "Male"

    # Category
    for cat in CATEGORY_KEYWORDS:
        if re.search(rf"\b{re.escape(cat)}\b", t, re.I):
            result["category"] = cat.upper() if cat.upper() in ["SC", "ST", "OBC", "BC", "EWS"] else cat
            break

    # Disability
    if re.search(r"disab|pwd|specially[- ]abled|divyang", t, re.I):
        result["disability_status"] = "Yes"

    # Course
    for course in COURSE_KEYWORDS:
        if keyword_regex_match(course, t):
            result["course"] = course.replace("BTech", "B.Tech").replace("BE", "B.E") \
                .replace("BSc", "B.Sc").replace("BCom", "B.Com").replace("BA", "B.A") \
                .replace("MTech", "M.Tech").replace("MSc", "M.Sc")
            break

    # Branch
    for branch in BRANCH_KEYWORDS:
        if keyword_regex_match(branch, t):
            result["branch"] = branch
            break

    # Year of study
    m = re.search(r"\b(1st|2nd|3rd|4th|first|second|third|fourth|final)\s*[- ]?\s*year\b", t, re.I)
    if m:
        result["current_year"] = YEAR_PATTERNS.get(m.group(1).lower(), None)

    # CGPA
    m = re.search(r"cgpa\D{0,5}(\d{1,2}(?:\.\d{1,2})?)", t, re.I)
    if m:
        result["cgpa"] = float(m.group(1))

    # 10th / 12th percentage
    m = re.search(r"10th\D{0,10}?(\d{2,3}(?:\.\d{1,2})?)\s*%?", t, re.I)
    if m:
        result["percentage_10"] = float(m.group(1))
    m = re.search(r"12th\D{0,10}?(\d{2,3}(?:\.\d{1,2})?)\s*%?", t, re.I)
    if m:
        result["percentage_12"] = float(m.group(1))

    # Family income -- handle lakh / thousand / plain rupee figures
    m = re.search(r"(?:income|earn)[^\d₹]{0,15}(?:₹|rs\.?|inr)?\s*([\d,.]+)\s*(lakh|lac|l\b|thousand|k\b)?", t, re.I)
    if m:
        num = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        if unit in ("lakh", "lac", "l"):
            num *= 100000
        elif unit in ("thousand", "k"):
            num *= 1000
        result["family_income"] = num

    # Name (very light heuristic: "I am <Name>," patterns are unreliable in this domain -- skip unless explicit)
    m = re.search(r"my name is ([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)", t)
    if m:
        result["name"] = m.group(1)

    # College type
    if re.search(r"government college|govt\.?\s*college", t, re.I):
        result["college_type"] = "Government"
    elif re.search(r"private college", t, re.I):
        result["college_type"] = "Private"

    return result


def extract_profile_from_text(text: str) -> dict:
    """
    Returns a dict of extracted fields. Uses LLM extraction if available
    for higher recall on free-form phrasing, else deterministic regex.
    """
    if llm_available():
        system_prompt = (
            "You are a precise information extraction engine for a scholarship "
            "eligibility system. Extract ONLY fields explicitly present or clearly "
            "inferable from the student's text. Return strict JSON with keys: "
            "name, age, state, domicile, gender, category, disability_status, course, "
            "branch, current_year, cgpa, percentage_10, percentage_12, family_income, "
            "college_type, college_location, special_circumstances. "
            "Omit keys you cannot determine -- do not guess or invent values."
        )
        try:
            raw = call_llm(system_prompt, text, json_mode=True)
            data = json.loads(raw)
            return {k: v for k, v in data.items() if v not in (None, "", "unknown")}
        except Exception:
            pass  # fall through to regex fallback

    return _regex_extract(text)


REQUIRED_FIELDS_FOR_DISCOVERY = [
    "state", "course", "current_year", "cgpa", "family_income", "category",
]


def find_missing_fields(profile: dict) -> list:
    return [f for f in REQUIRED_FIELDS_FOR_DISCOVERY if not profile.get(f)]


FOLLOW_UP_QUESTION_TEMPLATES = {
    "state": "Which state are you domiciled in?",
    "course": "What course are you currently pursuing (e.g. B.Tech, B.Sc)?",
    "current_year": "Which year of study are you in?",
    "cgpa": "What is your current CGPA (or overall percentage)?",
    "family_income": "What is your approximate annual family income?",
    "category": "What category do you belong to (General / OBC / SC / ST / EWS)?",
}


def build_follow_up_questions(missing_fields: list) -> list:
    return [FOLLOW_UP_QUESTION_TEMPLATES[f] for f in missing_fields if f in FOLLOW_UP_QUESTION_TEMPLATES]
