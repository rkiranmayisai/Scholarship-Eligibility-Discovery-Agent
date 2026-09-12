"""
Pydantic models shared across the agent pipeline.
Keeping these centralized lets every agent speak the same structured
"language" as data is passed through the Orchestrator.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class StudentProfile(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    state: Optional[str] = None
    domicile: Optional[str] = None
    gender: Optional[str] = None
    category: Optional[str] = None
    disability_status: Optional[str] = None
    course: Optional[str] = None
    branch: Optional[str] = None
    current_year: Optional[str] = None
    cgpa: Optional[float] = None
    percentage_10: Optional[float] = None
    percentage_12: Optional[float] = None
    family_income: Optional[float] = None
    college_type: Optional[str] = None
    college_location: Optional[str] = None
    special_circumstances: Optional[str] = None

    # bookkeeping used by the Profile Agent
    missing_fields: List[str] = Field(default_factory=list)
    confidence: Dict[str, float] = Field(default_factory=dict)


class ProfileAnalysisResult(BaseModel):
    profile: StudentProfile
    follow_up_questions: List[str] = Field(default_factory=list)
    is_complete_enough: bool = True
    raw_input: Optional[str] = None


class RequirementCheck(BaseModel):
    requirement: str
    required_value: str
    student_value: str
    result: str  # PASS / FAIL / UNKNOWN
    explanation: str


class EligibilityResult(BaseModel):
    scholarship_id: str
    scholarship_name: str
    status: str  # ELIGIBLE / ALMOST_ELIGIBLE / NOT_ELIGIBLE
    checks: List[RequirementCheck]
    passed_count: int
    total_count: int
    confidence: str  # High / Medium / Low
    missing_requirement_summary: Optional[str] = None


class RankedScholarship(BaseModel):
    scholarship_id: str
    scholarship_name: str
    provider: str
    match_score: float
    eligibility_status: str
    scholarship_amount: Optional[float]
    application_deadline: Optional[str]
    days_remaining: Optional[int]
    priority: Optional[str] = None
    source_type: str
    official_url: str
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    verification_status: Optional[str] = None
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    secondary_sources: List[str] = Field(default_factory=list)


class DocumentChecklistItem(BaseModel):
    document: str
    status: str = "Missing"  # Available / Missing / Need to Obtain


class ScholarshipDocumentChecklist(BaseModel):
    scholarship_id: str
    scholarship_name: str
    documents: List[DocumentChecklistItem]


class DeadlineInfo(BaseModel):
    scholarship_id: str
    scholarship_name: str
    deadline: str
    days_remaining: int
    priority: str  # Urgent / Apply Soon / Later


class PlanTask(BaseModel):
    day: int
    tasks: List[str]


class AgentLogEntry(BaseModel):
    agent: str
    icon: str
    message: str
    status: str = "done"  # running / done / error


class OrchestrationResult(BaseModel):
    profile: StudentProfile
    follow_up_questions: List[str]
    summary: Dict[str, int]
    ranked_scholarships: List[RankedScholarship]
    eligibility_details: Dict[str, EligibilityResult]
    document_checklists: List[ScholarshipDocumentChecklist]
    master_checklist: List[str]
    deadlines: List[DeadlineInfo]
    action_plan: List[PlanTask]
    agent_activity: List[AgentLogEntry]
    discovery_report: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
