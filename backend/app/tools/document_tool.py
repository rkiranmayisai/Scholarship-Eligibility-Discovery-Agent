"""
TOOL: Document Requirement Tool
Used by: Document Checklist Agent
"""


def get_required_documents(scholarship: dict) -> list:
    return list(scholarship.get("required_documents") or [])


def build_master_checklist(scholarships: list) -> list:
    seen = []
    for s in scholarships:
        for doc in s.get("required_documents", []):
            if doc not in seen:
                seen.append(doc)
    return seen
