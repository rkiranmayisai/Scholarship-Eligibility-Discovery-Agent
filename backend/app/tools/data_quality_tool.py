"""
TOOL: Data Quality Tool
Used by: Scholarship Discovery Agent

Applies the rejection rules the Discovery Agent spec requires, before a
record is ever allowed into the knowledge base. Rejecting bad records
here is what keeps a flood of ad pages / broken listings out of a
student's results.
"""

MIN_USEFUL_TEXT_LEN = 40  # a real scholarship description is longer than this


def should_reject(record: dict, page_text) -> tuple:
    """
    Returns (reject: bool, reason: str | None).
    """
    if not record.get("scholarship_name"):
        return True, "Missing scholarship name"

    if not record.get("source_url"):
        return True, "Missing source URL"

    if not (record.get("provider") or record.get("source_name")):
        return True, "Could not identify any provider or source"

    # Reject if the page reads like a bare advertisement / listing with
    # nothing extractable at all -- no eligibility signal, no benefit,
    # no documents, and only a very short description.
    has_any_eligibility_signal = any([
        record.get("degree"), record.get("branches"), record.get("state"),
        record.get("minimum_cgpa") is not None, record.get("maximum_income") is not None,
        record.get("category_requirement"), record.get("required_documents"),
        record.get("amount") is not None,
    ])
    description_len = len(record.get("description") or "")
    page_len = len(page_text or "")

    if not has_any_eligibility_signal and description_len < MIN_USEFUL_TEXT_LEN and page_len < MIN_USEFUL_TEXT_LEN:
        return True, "No eligibility information or substantive content could be found (likely an advertisement or broken listing)"

    return False, None
