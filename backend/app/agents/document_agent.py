"""
AGENT 5 -- DOCUMENT CHECKLIST AGENT

Responsibility: identify required documents per scholarship and produce
a combined master checklist across all eligible / almost-eligible
scholarships, so the student prepares once instead of per-application.
"""
from app.models import ScholarshipDocumentChecklist, DocumentChecklistItem
from app.tools.document_tool import get_required_documents, build_master_checklist


class DocumentAgent:
    name = "Document Agent"
    icon = "📄"

    def run(self, scholarships: list, already_have: list[str] | None = None) -> tuple[list, list]:
        already_have = set(d.lower() for d in (already_have or []))

        per_scholarship = []
        for s in scholarships:
            docs = get_required_documents(s)
            items = [
                DocumentChecklistItem(
                    document=d,
                    status="Available" if d.lower() in already_have else "Missing",
                )
                for d in docs
            ]
            per_scholarship.append(ScholarshipDocumentChecklist(
                scholarship_id=s["id"], scholarship_name=s["name"], documents=items,
            ))

        master = build_master_checklist(scholarships)
        return per_scholarship, master
