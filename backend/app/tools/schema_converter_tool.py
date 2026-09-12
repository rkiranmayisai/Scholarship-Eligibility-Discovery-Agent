"""
TOOL: Schema Converter
Used by: Scholarship Discovery Agent

The rest of ScholarAI (Eligibility, Ranking, Document, Deadline agents)
was built around one internal scholarship schema (see
scholarship_db_tool.py / data/scholarships.json). Rather than rewrite
every downstream agent to understand two schemas, this converts a
freshly-discovered rich record (matching the Discovery Agent spec) into
that internal shape -- while keeping every rich field (evidence,
verification_status, secondary_sources, provider_type, category,
benefit, duration) attached as pass-through extras so the UI can still
show them.
"""
import hashlib


def to_internal_schema(record: dict) -> dict:
    source_url = record.get("source_url") or record.get("application_url") or ""
    scholarship_id = "LIVE-" + hashlib.md5(source_url.encode()).hexdigest()[:10] if source_url \
        else "LIVE-" + hashlib.md5((record.get("scholarship_name") or "unknown").encode()).hexdigest()[:10]

    verification_status = record.get("verification_status") or "NEEDS_VERIFICATION"
    display_source_type = verification_status.replace("_", " ")  # e.g. "NEEDS VERIFICATION"

    eligible_courses = list(record.get("degree") or [])
    eligible_states = [record["state"]] if record.get("state") else []
    category_conditions = [record["category_requirement"]] if record.get("category_requirement") else []
    year_of_study = list(record.get("academic_year") or [])

    return {
        "id": scholarship_id,
        "name": record.get("scholarship_name") or "Untitled scholarship listing",
        "provider": record.get("provider") or record.get("source_name") or "Unknown provider",
        "description": record.get("description") or "",
        "official_url": record.get("application_url") or source_url,
        "source_type": display_source_type,
        "last_verified": record.get("last_checked"),

        "eligible_courses": eligible_courses,
        "eligible_states": eligible_states,
        "minimum_percentage": None,  # spec's schema doesn't distinguish % from CGPA; we only extract CGPA live
        "minimum_cgpa": record.get("minimum_cgpa"),
        "maximum_family_income": record.get("maximum_income"),
        "gender_conditions": record.get("gender_requirement") or "Any",
        "category_conditions": category_conditions,
        "year_of_study": year_of_study,
        "age_limit": _parse_age_limit(record.get("age_requirement")),
        "disability_conditions": "Any",
        "domicile_requirement": record.get("domicile_requirement"),
        "required_documents": list(record.get("required_documents") or []),
        "application_deadline": _normalize_date(record.get("application_deadline")),
        "scholarship_amount": record.get("amount"),

        # Pass-through rich fields for the UI / evidence panel
        "verification_status": verification_status,
        "evidence": record.get("evidence") or [],
        "secondary_sources": record.get("secondary_sources") or [],
        "provider_type": record.get("provider_type"),
        "scholarship_category": record.get("scholarship_category"),
        "benefit": record.get("benefit"),
        "duration": record.get("duration"),
        "application_start_date": record.get("application_start_date"),
    }


def _parse_age_limit(age_requirement) -> int | None:
    if not age_requirement or "not specified" in str(age_requirement).lower():
        return None
    import re
    m = re.search(r"(\d{2})", str(age_requirement))
    return int(m.group(1)) if m else None


def _normalize_date(date_str):
    """
    Best-effort normalization of freely-formatted extracted dates into
    YYYY-MM-DD so the existing deadline_tool (which expects that format)
    keeps working. Returns None if the date can't be confidently parsed
    -- an unparsed deadline is dropped rather than guessed.
    """
    if not date_str:
        return None
    from datetime import datetime
    formats = ["%d %B %Y", "%d %b %Y", "%B %d, %Y", "%B %d %Y", "%d/%m/%Y", "%d-%m-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date().isoformat()
        except Exception:
            continue
    return None
