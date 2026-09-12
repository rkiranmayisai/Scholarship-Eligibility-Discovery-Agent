"""
AGENT 1 -- PROFILE ANALYZER AGENT

Responsibility: understand the student. Converts free-text or partial
structured input into a StructuredStudentProfile, and decides -- on its
own -- whether it has enough information to hand off to the Discovery
Agent, or whether it must ask targeted follow-up questions first.

This agent DELEGATES nothing forward if the profile is unusable; it
DECIDES completeness and produces follow-up questions autonomously,
which is what makes it agentic rather than a plain form parser.
"""
from app.models import StudentProfile, ProfileAnalysisResult
from app.tools.profile_extraction_tool import (
    extract_profile_from_text, find_missing_fields, build_follow_up_questions,
)


class ProfileAnalyzerAgent:
    name = "Profile Analyzer Agent"
    icon = "🤖"

    def run(self, raw_text: str | None = None, structured: dict | None = None) -> ProfileAnalysisResult:
        extracted: dict = {}

        if structured:
            extracted.update({k: v for k, v in structured.items() if v not in (None, "")})

        if raw_text:
            from_text = extract_profile_from_text(raw_text)
            # structured input (explicit form fields), if present, takes precedence
            for k, v in from_text.items():
                extracted.setdefault(k, v)

        profile = StudentProfile(**{k: v for k, v in extracted.items() if k in StudentProfile.model_fields})

        missing = find_missing_fields(extracted)
        profile.missing_fields = missing
        follow_ups = build_follow_up_questions(missing)

        # The agent decides for itself: too little info to proceed usefully?
        # We tolerate 1 missing field and still proceed (Discovery/Eligibility
        # agents handle "UNKNOWN" gracefully), but flag 2+ as needing follow-up.
        is_complete_enough = len(missing) <= 1

        return ProfileAnalysisResult(
            profile=profile,
            follow_up_questions=follow_ups,
            is_complete_enough=is_complete_enough,
            raw_input=raw_text,
        )
