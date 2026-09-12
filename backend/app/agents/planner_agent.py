"""
AGENT 7 -- APPLICATION PLANNER AGENT

Responsibility: synthesize everything the other agents produced
(eligibility, ranking, documents, deadlines) into a concrete day-by-day
action plan personalized to the student's situation.
"""
from app.models import PlanTask


class PlannerAgent:
    name = "Planning Agent"
    icon = "🧠"

    def run(self, ranked_scholarships: list, master_checklist: list,
            deadlines: list, document_checklists: list) -> list:
        plan: list[PlanTask] = []
        day = 1

        # Prioritize document acquisition for missing documents first,
        # ordered by which scholarship is most urgent.
        missing_docs_ordered = []
        for chk in document_checklists:
            for item in chk.documents:
                if item.status != "Available" and item.document not in missing_docs_ordered:
                    missing_docs_ordered.append(item.document)

        # Day 1-N: obtain missing documents, 2 per day to keep it realistic
        for i in range(0, len(missing_docs_ordered), 2):
            batch = missing_docs_ordered[i:i + 2]
            plan.append(PlanTask(day=day, tasks=[f"Obtain/prepare: {d}" for d in batch]))
            day += 1

        if not missing_docs_ordered:
            plan.append(PlanTask(day=day, tasks=["Review and organize all existing documents."]))
            day += 1

        # Next: address top eligible scholarships in deadline-priority order
        top_eligible = [r for r in ranked_scholarships if r.eligibility_status == "ELIGIBLE"][:5]
        # sort those by urgency using deadlines list ordering
        urgency_rank = {d.scholarship_id: d.days_remaining for d in deadlines}
        top_eligible.sort(key=lambda r: urgency_rank.get(r.scholarship_id, 9999))

        for r in top_eligible:
            plan.append(PlanTask(day=day, tasks=[f"Complete application for: {r.scholarship_name}"]))
            day += 1
            plan.append(PlanTask(day=day, tasks=[f"Review application details for: {r.scholarship_name} before submission."]))
            day += 1
            plan.append(PlanTask(day=day, tasks=[f"Submit application: {r.scholarship_name} (deadline: {r.application_deadline})."]))
            day += 1

        # Handle almost-eligible: verification tasks
        almost = [r for r in ranked_scholarships if r.eligibility_status == "ALMOST_ELIGIBLE"][:3]
        if almost:
            plan.append(PlanTask(
                day=day,
                tasks=[f"Verify remaining requirement for: {r.scholarship_name}" for r in almost]
            ))
            day += 1

        if not plan:
            plan.append(PlanTask(day=1, tasks=["No immediate actions -- revisit after updating your profile."]))

        return plan
