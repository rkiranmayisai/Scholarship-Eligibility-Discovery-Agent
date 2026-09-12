import uuid
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from app.database import init_db, SessionLocal, StudentRecord, AgentLogRecord
from app.agents.orchestrator import Orchestrator
from app.agents.chat_agent import answer_question
from app.tools.scholarship_db_tool import load_all_scholarships, get_scholarship_by_id
from app.models import OrchestrationResult

app = FastAPI(title="ScholarAI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = Orchestrator()

# In-memory session store (keyed by session_id) holding the last
# orchestration result so the chat assistant + document tracker can
# stay grounded in it without re-running the whole pipeline every message.
SESSIONS: dict = {}


@app.on_event("startup")
def on_startup():
    init_db()


class DiscoverRequest(BaseModel):
    session_id: Optional[str] = None
    raw_text: Optional[str] = None
    structured: Optional[dict] = None
    documents_available: Optional[List[str]] = None


class DocumentUpdateRequest(BaseModel):
    session_id: str
    scholarship_id: str
    document: str
    status: str  # Available / Missing / Need to Obtain


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ScholarAI"}


@app.get("/api/scholarships")
def list_scholarships():
    return load_all_scholarships()


@app.get("/api/scholarships/{scholarship_id}")
def get_scholarship(scholarship_id: str):
    s = get_scholarship_by_id(scholarship_id)
    if not s:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    return s


@app.post("/api/discovery/refresh")
def discovery_refresh():
    """
    Manually triggers a full-catalog discovery run (generic queries, not
    tied to any one student) and re-checks stored live scholarships for
    expiry. Intended to be called periodically (e.g. a nightly cron job
    or scheduled task hitting this endpoint) -- see README "Continuous
    update" section.
    """
    report = orchestrator.discovery_agent.run_full_refresh()
    return report


@app.get("/api/discovery/report")
def discovery_last_report():
    """Returns the discovery report from the most recent /api/discover call."""
    report = orchestrator.discovery_agent.last_discovery_report
    if report is None:
        return {"message": "No live discovery has run yet in this process (either no /api/discover call has been made, or GOOGLE_API_KEY/GOOGLE_CSE_ID are not configured)."}
    return report


@app.post("/api/discover")
def discover(req: DiscoverRequest):
    """
    Runs the full multi-agent pipeline:
    Profile Analyzer -> Discovery -> Eligibility -> Ranking -> Document ->
    Deadline -> Planner, orchestrated end to end.
    """
    session_id = req.session_id or str(uuid.uuid4())

    result: OrchestrationResult = orchestrator.run(
        raw_text=req.raw_text,
        structured=req.structured,
        documents_available=req.documents_available,
    )

    SESSIONS[session_id] = result.model_dump()

    # persist student + agent logs
    db = SessionLocal()
    try:
        db.merge(StudentRecord(id=session_id, profile_json=json.dumps(result.profile.model_dump())))
        for entry in result.agent_activity:
            db.add(AgentLogRecord(
                session_id=session_id, agent=entry.agent, message=entry.message, status=entry.status
            ))
        db.commit()
    finally:
        db.close()

    response = result.model_dump()
    response["session_id"] = session_id
    return response


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found. Run /api/discover first.")
    return SESSIONS[session_id]


@app.post("/api/documents/update")
def update_document(req: DocumentUpdateRequest):
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    for checklist in session["document_checklists"]:
        if checklist["scholarship_id"] == req.scholarship_id:
            for doc in checklist["documents"]:
                if doc["document"] == req.document:
                    doc["status"] = req.status
    return {"ok": True}


@app.post("/api/chat")
def chat(req: ChatRequest):
    from app.agents.chat_agent import _classify_query, _general_query_fallback, _is_greeting, _is_farewell

    msg = req.message.strip()

    if _is_greeting(msg):
        return {"reply": "Hello! 👋 Can I help you find a scholarship opportunity?"}

    if _is_farewell(msg):
        return {"reply": "Goodbye! 👋 Best of luck with your scholarship journey. Can I help you with anything else before you go?"}

    if _classify_query(msg) == "UNRELATED":
        return {"reply": _general_query_fallback(msg)}

    session = SESSIONS.get(req.session_id)
    if not session:
        session = {
            "ranked_scholarships": [],
            "eligibility_details": {},
            "deadlines": [],
            "document_checklists": [],
        }

    # reconstruct light objects the chat agent expects (attribute access)
    from types import SimpleNamespace

    def to_ns(d):
        return SimpleNamespace(**d) if isinstance(d, dict) else d

    ranked = [to_ns(r) for r in session.get("ranked_scholarships", [])]
    eligibility = {k: to_ns(v) for k, v in session.get("eligibility_details", {}).items()}
    deadlines = [to_ns(d) for d in session.get("deadlines", [])]
    doc_checklists = []
    for c in session.get("document_checklists", []):
        docs = [to_ns(d) for d in c["documents"]]
        c2 = dict(c)
        c2["documents"] = docs
        doc_checklists.append(to_ns(c2))

    reply = answer_question({
        "ranked_scholarships": ranked,
        "eligibility_details": eligibility,
        "deadlines": deadlines,
        "document_checklists": doc_checklists,
    }, req.message)

    return {"reply": reply}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
