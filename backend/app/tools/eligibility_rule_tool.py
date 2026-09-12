"""
TOOL: Eligibility Rule Tool
Used by: Eligibility Analyzer Agent

Pure, deterministic rule evaluation -- given a student profile and a
scholarship record, evaluates every individual eligibility requirement
and returns an explainable pass/fail/unknown breakdown. Kept separate
from the agent so it is independently testable and auditable (no LLM
"vibes"-based eligibility decisions).
"""
from app.models import RequirementCheck


def _fmt_money(v):
    if v is None:
        return "Not specified"
    return f"₹{int(v):,}"


def evaluate_requirements(profile: dict, scholarship: dict) -> list[RequirementCheck]:
    checks: list[RequirementCheck] = []

    # --- Course requirement ---
    eligible_courses = scholarship.get("eligible_courses") or []
    student_course = (profile.get("course") or "").strip()
    student_branch = (profile.get("branch") or "").strip()
    if eligible_courses:
        combined = f"{student_course} {student_branch}".lower()
        matched = any(
            "any" in ec.lower() or ec.lower() in combined or combined.strip() and combined.split()[0] in ec.lower()
            for ec in eligible_courses
        ) if combined.strip() else False
        if not student_course:
            checks.append(RequirementCheck(
                requirement="Course",
                required_value=", ".join(eligible_courses),
                student_value="Not provided",
                result="UNKNOWN",
                explanation="Student course not specified -- cannot confirm course eligibility."
            ))
        else:
            checks.append(RequirementCheck(
                requirement="Course",
                required_value=", ".join(eligible_courses),
                student_value=f"{student_course} {student_branch}".strip(),
                result="PASS" if matched else "FAIL",
                explanation=("Student's course matches an eligible course category." if matched
                             else "Student's course/branch is not listed among eligible courses.")
            ))

    # --- Academic requirement: CGPA ---
    min_cgpa = scholarship.get("minimum_cgpa")
    if min_cgpa is not None:
        student_cgpa = profile.get("cgpa")
        if student_cgpa is None:
            checks.append(RequirementCheck(
                requirement="Minimum CGPA", required_value=str(min_cgpa),
                student_value="Not provided", result="UNKNOWN",
                explanation="Student CGPA not provided -- cannot verify academic requirement."
            ))
        else:
            passed = student_cgpa >= min_cgpa
            checks.append(RequirementCheck(
                requirement="Minimum CGPA", required_value=str(min_cgpa),
                student_value=str(student_cgpa),
                result="PASS" if passed else "FAIL",
                explanation=(f"Student CGPA {student_cgpa} meets minimum required {min_cgpa}." if passed
                             else f"Student CGPA {student_cgpa} is below the minimum required {min_cgpa}.")
            ))

    # --- Academic requirement: percentage (12th, used as general academic percentage) ---
    min_pct = scholarship.get("minimum_percentage")
    if min_pct is not None:
        student_pct = profile.get("percentage_12") or profile.get("percentage_10")
        if student_pct is None:
            checks.append(RequirementCheck(
                requirement="Minimum Percentage", required_value=f"{min_pct}%",
                student_value="Not provided", result="UNKNOWN",
                explanation="Student academic percentage not provided -- cannot verify."
            ))
        else:
            passed = student_pct >= min_pct
            checks.append(RequirementCheck(
                requirement="Minimum Percentage", required_value=f"{min_pct}%",
                student_value=f"{student_pct}%",
                result="PASS" if passed else "FAIL",
                explanation=(f"Student's {student_pct}% meets the minimum required {min_pct}%." if passed
                             else f"Student's {student_pct}% is below the minimum required {min_pct}%.")
            ))

    # --- Income requirement ---
    max_income = scholarship.get("maximum_family_income")
    if max_income is not None:
        student_income = profile.get("family_income")
        if student_income is None:
            checks.append(RequirementCheck(
                requirement="Maximum Family Income", required_value=_fmt_money(max_income),
                student_value="Not provided", result="UNKNOWN",
                explanation="Student family income not provided -- cannot verify income eligibility."
            ))
        else:
            passed = student_income <= max_income
            checks.append(RequirementCheck(
                requirement="Maximum Family Income", required_value=_fmt_money(max_income),
                student_value=_fmt_money(student_income),
                result="PASS" if passed else "FAIL",
                explanation=(f"Family income {_fmt_money(student_income)} is within the limit of {_fmt_money(max_income)}."
                             if passed else
                             f"Family income {_fmt_money(student_income)} exceeds the limit of {_fmt_money(max_income)}.")
            ))

    # --- State / domicile requirement ---
    eligible_states = scholarship.get("eligible_states") or []
    if eligible_states and not any(es.lower() == "all india" for es in eligible_states):
        student_state = (profile.get("state") or profile.get("domicile") or "").strip()
        if not student_state:
            checks.append(RequirementCheck(
                requirement="State / Domicile", required_value=", ".join(eligible_states),
                student_value="Not provided", result="UNKNOWN",
                explanation="Student's state/domicile not provided."
            ))
        else:
            passed = any(es.lower() == student_state.lower() for es in eligible_states)
            checks.append(RequirementCheck(
                requirement="State / Domicile", required_value=", ".join(eligible_states),
                student_value=student_state,
                result="PASS" if passed else "FAIL",
                explanation=(f"Student's domicile ({student_state}) matches the required state." if passed
                             else f"Student's domicile ({student_state}) does not match required state(s): {', '.join(eligible_states)}.")
            ))

    # --- Category requirement ---
    eligible_categories = scholarship.get("category_conditions") or []
    if eligible_categories and set(c.lower() for c in eligible_categories) != {"any"}:
        student_category = (profile.get("category") or "").strip()
        if not student_category:
            checks.append(RequirementCheck(
                requirement="Category", required_value=", ".join(eligible_categories),
                student_value="Not provided", result="UNKNOWN",
                explanation="Student category not provided."
            ))
        else:
            passed = any(c.lower() == student_category.lower() for c in eligible_categories)
            checks.append(RequirementCheck(
                requirement="Category", required_value=", ".join(eligible_categories),
                student_value=student_category,
                result="PASS" if passed else "FAIL",
                explanation=(f"Student category '{student_category}' is covered by this scholarship." if passed
                             else f"Student category '{student_category}' is not among eligible categories: {', '.join(eligible_categories)}.")
            ))

    # --- Gender requirement ---
    gender_req = scholarship.get("gender_conditions")
    if gender_req and gender_req.lower() != "any":
        student_gender = (profile.get("gender") or "").strip()
        if not student_gender:
            checks.append(RequirementCheck(
                requirement="Gender", required_value=gender_req,
                student_value="Not provided", result="UNKNOWN",
                explanation="Student gender not provided."
            ))
        else:
            passed = student_gender.lower() == gender_req.lower()
            checks.append(RequirementCheck(
                requirement="Gender", required_value=gender_req, student_value=student_gender,
                result="PASS" if passed else "FAIL",
                explanation=(f"Gender requirement ({gender_req}) satisfied." if passed
                             else f"This scholarship is restricted to {gender_req} students.")
            ))

    # --- Year of study requirement ---
    eligible_years = scholarship.get("year_of_study") or []
    if eligible_years:
        student_year = str(profile.get("current_year") or "").strip()
        if not student_year:
            checks.append(RequirementCheck(
                requirement="Year of Study", required_value=", ".join(eligible_years),
                student_value="Not provided", result="UNKNOWN",
                explanation="Student's current year of study not provided."
            ))
        else:
            passed = student_year in eligible_years
            checks.append(RequirementCheck(
                requirement="Year of Study", required_value=", ".join(eligible_years),
                student_value=student_year,
                result="PASS" if passed else "FAIL",
                explanation=(f"Year {student_year} is an eligible year for this scholarship." if passed
                             else f"Year {student_year} is not among eligible years: {', '.join(eligible_years)}.")
            ))

    # --- Age limit ---
    age_limit = scholarship.get("age_limit")
    if age_limit is not None:
        student_age = profile.get("age")
        if student_age is None:
            checks.append(RequirementCheck(
                requirement="Age Limit", required_value=f"≤ {age_limit} years",
                student_value="Not provided", result="UNKNOWN",
                explanation="Student age not provided."
            ))
        else:
            passed = student_age <= age_limit
            checks.append(RequirementCheck(
                requirement="Age Limit", required_value=f"≤ {age_limit} years",
                student_value=f"{student_age} years",
                result="PASS" if passed else "FAIL",
                explanation=(f"Student age {student_age} is within the limit of {age_limit}." if passed
                             else f"Student age {student_age} exceeds the limit of {age_limit}.")
            ))

    # --- Disability requirement ---
    disability_req = scholarship.get("disability_conditions")
    if disability_req and "any" not in disability_req.lower():
        student_disability = (profile.get("disability_status") or "No").strip()
        passed = student_disability.lower() in ("yes", "true")
        checks.append(RequirementCheck(
            requirement="Disability Status", required_value=disability_req,
            student_value=student_disability,
            result="PASS" if passed else ("UNKNOWN" if student_disability.lower() not in ("no",) else "FAIL"),
            explanation=(f"Meets disability requirement: {disability_req}." if passed
                         else f"This scholarship requires: {disability_req}.")
        ))

    return checks
