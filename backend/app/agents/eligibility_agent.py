"""
AGENT 3 -- ELIGIBILITY ANALYZER AGENT

Responsibility: compare the student's profile against every candidate
scholarship's requirements and produce an explainable decision:
ELIGIBLE / ALMOST_ELIGIBLE / NOT_ELIGIBLE -- never a bare yes/no.
"""
from app.models import EligibilityResult
from app.tools.eligibility_rule_tool import evaluate_requirements


class EligibilityAgent:
    name = "Eligibility Agent"
    icon = "⚖️"

    def evaluate(self, profile: dict, scholarship: dict) -> EligibilityResult:
        if scholarship.get("verification_status") == "EXPIRED":
            return EligibilityResult(
                scholarship_id=scholarship["id"],
                scholarship_name=scholarship["name"],
                status="NOT_ELIGIBLE",
                checks=[],
                passed_count=0,
                total_count=0,
                confidence="High",
                missing_requirement_summary=(
                    "This scholarship's application deadline has already passed "
                    f"({scholarship.get('application_deadline', 'date unknown')}). "
                    "It is a genuine scholarship, not a demo record, but is no longer accepting applications."
                ),
            )

        checks = evaluate_requirements(profile, scholarship)

        total = len(checks)
        passed = sum(1 for c in checks if c.result == "PASS")
        failed = sum(1 for c in checks if c.result == "FAIL")
        unknown = sum(1 for c in checks if c.result == "UNKNOWN")

        if total == 0:
            status, confidence = "ALMOST_ELIGIBLE", "Low"
            return EligibilityResult(
                scholarship_id=scholarship["id"],
                scholarship_name=scholarship["name"],
                status=status,
                checks=checks,
                passed_count=passed,
                total_count=total,
                confidence=confidence,
                missing_requirement_summary=(
                    "No structured eligibility rules were available for this listing "
                    "(likely a live search result) -- open the official link and verify "
                    "requirements manually before applying."
                ),
            )
        elif failed == 0 and unknown == 0:
            status, confidence = "ELIGIBLE", "High"
        elif failed == 0 and unknown > 0:
            status, confidence = "ALMOST_ELIGIBLE", "Medium"
        elif failed == 1 and passed >= total - 1:
            status, confidence = "ALMOST_ELIGIBLE", "Medium"
        else:
            status, confidence = "NOT_ELIGIBLE", "High" if unknown == 0 else "Medium"

        missing_summary = None
        if status == "ALMOST_ELIGIBLE":
            failing = [c for c in checks if c.result == "FAIL"]
            unk = [c for c in checks if c.result == "UNKNOWN"]
            if failing:
                c = failing[0]
                missing_summary = f"{c.requirement}: required {c.required_value}, you have {c.student_value}."
            elif unk:
                c = unk[0]
                missing_summary = f"{c.requirement} needs verification (value not provided: {c.required_value} required)."

        return EligibilityResult(
            scholarship_id=scholarship["id"],
            scholarship_name=scholarship["name"],
            status=status,
            checks=checks,
            passed_count=passed,
            total_count=total,
            confidence=confidence,
            missing_requirement_summary=missing_summary,
        )

    def run(self, profile: dict, scholarships: list) -> dict:
        return {s["id"]: self.evaluate(profile, s) for s in scholarships}
