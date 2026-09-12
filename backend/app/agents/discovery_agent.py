"""
AGENT 2 -- SCHOLARSHIP DISCOVERY AGENT

Responsibility: discover REAL scholarship opportunities, trace every
one back to a source, extract structured eligibility data with
evidence, assign a verification status, deduplicate, and persist the
result -- never fabricating a scholarship or an eligibility number.

Pipeline (mirrors the Discovery Agent spec):
  1. Build a profile-aware + generic multi-query search strategy.
  2. Run each query through the Google Search tool (Tier-aware).
  3. Fetch each unique result's source page (best-effort).
  4. Extract structured fields WITH evidence (scholarship_extraction_tool).
  5. Assign verification_status: VERIFIED / NEEDS_VERIFICATION / EXPIRED.
  6. Reject low-quality records (data_quality_tool).
  7. Deduplicate by provider+name identity (dedup_tool).
  8. Convert to the app's internal schema (schema_converter_tool).
  9. Persist to the scholarships table, tracking newly-added vs updated.
 10. Merge with the local offline dataset (source_type = DEMO DATA,
     never confused with a live discovery result) and hand everything to
     the vector-search (RAG) retrieval step for ranking.

With no GOOGLE_API_KEY/GOOGLE_CSE_ID configured, steps 1-9 are skipped
entirely and the agent runs purely on the offline demo dataset -- this
is what keeps the whole app working with zero API keys.
"""
import datetime as dt

from app.tools.scholarship_db_tool import coarse_filter, load_all_scholarships
from app.tools.vector_search_tool import semantic_search, build_query_from_profile
from app.tools.google_search_tool import google_search_available, raw_google_search
from app.tools.source_tiers import classify_source_tier, get_domain
from app.tools.page_fetch_tool import fetch_page_text
from app.tools.scholarship_extraction_tool import extract_structured_record
from app.tools.data_quality_tool import should_reject
from app.tools.dedup_tool import dedupe_records
from app.tools.schema_converter_tool import to_internal_schema, _normalize_date
from app.database import upsert_live_scholarships, mark_expired_scholarships

GENERIC_QUERIES = [
    "scholarship for B.Tech students India",
    "engineering scholarship India",
    "computer science scholarship India",
    "data science scholarship India",
    "undergraduate scholarship India",
    "merit scholarship engineering students",
    "scholarship Telangana engineering students",
    "scholarship Karnataka engineering students",
    "scholarship Andhra Pradesh engineering students",
    "government scholarship B.Tech India",
    "NSP engineering scholarship",
    "AICTE scholarship engineering",
]


class DiscoveryAgent:
    name = "Discovery Agent"
    icon = "🔎"

    def __init__(self):
        self.last_discovery_report = None
        self.last_live_search_count = 0

    # ------------------------------------------------------------------
    # Public entry point used by the Orchestrator
    # ------------------------------------------------------------------
    def run(self, profile: dict, top_k: int = 20, include_live_search: bool = True) -> list:
        candidates = coarse_filter(profile)
        if not candidates:
            candidates = load_all_scholarships()

        live_internal_records = []
        if include_live_search and google_search_available():
            live_internal_records, report = self.discover_live(profile)
            self.last_discovery_report = report
            self.last_live_search_count = len(live_internal_records)
            candidates = candidates + live_internal_records
        else:
            self.last_discovery_report = None
            self.last_live_search_count = 0

        query = build_query_from_profile(profile)
        ranked = semantic_search(query, candidates, top_k=top_k)
        return ranked

    # ------------------------------------------------------------------
    # Full live discovery pipeline (profile-aware)
    # ------------------------------------------------------------------
    def discover_live(self, profile: dict, max_queries: int = 6, max_urls: int = 12):
        queries = self._build_query_list(profile, max_queries)
        raw_items_by_url = self._run_queries(queries, per_query_results=5)

        unique_urls = list(raw_items_by_url.keys())[:max_urls]
        tiers = {url: classify_source_tier(url) for url in unique_urls}

        extracted, rejected_count = [], 0
        for url in unique_urls:
            item = raw_items_by_url[url]
            tier = tiers[url]
            page_text = fetch_page_text(url)
            record = extract_structured_record(item, page_text, tier)
            record["verification_status"] = self._assign_verification_status(record, tier)

            reject, _reason = should_reject(record, page_text)
            if reject:
                rejected_count += 1
                continue
            extracted.append(record)

        deduped, duplicates_removed = dedupe_records(extracted, tiers=tiers)
        internal_records = [to_internal_schema(r) for r in deduped]

        persistence = upsert_live_scholarships(internal_records)

        report = {
            "scholarships_discovered": len(unique_urls),
            "successfully_extracted": len(extracted),
            "rejected_low_quality": rejected_count,
            "verified": sum(1 for r in internal_records if r["verification_status"] == "VERIFIED"),
            "needs_verification": sum(1 for r in internal_records if r["verification_status"] == "NEEDS_VERIFICATION"),
            "expired": sum(1 for r in internal_records if r["verification_status"] == "EXPIRED"),
            "duplicates_removed": duplicates_removed,
            "sources_used": sorted({get_domain(u) for u in unique_urls if get_domain(u)}),
            "queries_used": queries,
            "newly_added": persistence["newly_added"],
            "updated": persistence["updated"],
        }
        return internal_records, report

    # ------------------------------------------------------------------
    # Full-catalog refresh (no student profile) -- for periodic/manual runs
    # ------------------------------------------------------------------
    def run_full_refresh(self, max_queries: int = 8, max_urls: int = 20) -> dict:
        if not google_search_available():
            return {"error": "Live search not configured (GOOGLE_API_KEY / GOOGLE_CSE_ID missing).",
                    "expired_marked": mark_expired_scholarships()}

        queries = GENERIC_QUERIES[:max_queries]
        raw_items_by_url = self._run_queries(queries, per_query_results=6)
        unique_urls = list(raw_items_by_url.keys())[:max_urls]
        tiers = {url: classify_source_tier(url) for url in unique_urls}

        extracted, rejected_count = [], 0
        for url in unique_urls:
            item = raw_items_by_url[url]
            tier = tiers[url]
            page_text = fetch_page_text(url)
            record = extract_structured_record(item, page_text, tier)
            record["verification_status"] = self._assign_verification_status(record, tier)
            reject, _ = should_reject(record, page_text)
            if reject:
                rejected_count += 1
                continue
            extracted.append(record)

        deduped, duplicates_removed = dedupe_records(extracted, tiers=tiers)
        internal_records = [to_internal_schema(r) for r in deduped]
        persistence = upsert_live_scholarships(internal_records)
        expired_marked = mark_expired_scholarships()

        return {
            "scholarships_discovered": len(unique_urls),
            "successfully_extracted": len(extracted),
            "rejected_low_quality": rejected_count,
            "verified": sum(1 for r in internal_records if r["verification_status"] == "VERIFIED"),
            "needs_verification": sum(1 for r in internal_records if r["verification_status"] == "NEEDS_VERIFICATION"),
            "expired": sum(1 for r in internal_records if r["verification_status"] == "EXPIRED"),
            "duplicates_removed": duplicates_removed,
            "sources_used": sorted({get_domain(u) for u in unique_urls if get_domain(u)}),
            "queries_used": queries,
            "newly_added": persistence["newly_added"],
            "updated": persistence["updated"],
            "expired_marked_this_run": expired_marked,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _build_query_list(self, profile: dict, max_queries: int) -> list:
        """Profile-aware queries first (spec section 'STUDENT-PROFILE-AWARE
        DISCOVERY'), padded out with generic queries up to the budget."""
        course = profile.get("course") or ""
        branch = profile.get("branch") or ""
        year = profile.get("current_year") or ""
        state = profile.get("state") or ""
        category = profile.get("category") or ""

        profile_queries = []
        if course:
            profile_queries.append("{} scholarship India".format(course))
        if branch:
            profile_queries.append("{} scholarship for engineering students India".format(branch))
        if year:
            profile_queries.append("year {} engineering scholarship India".format(year))
        if state:
            profile_queries.append("scholarship {} engineering students".format(state))
        if category:
            profile_queries.append("{} category scholarship engineering India".format(category))

        combined = profile_queries + [q for q in GENERIC_QUERIES if q not in profile_queries]
        return combined[:max_queries]

    def _run_queries(self, queries: list, per_query_results: int = 5) -> dict:
        """Runs each query, returns a dict of {url: raw_search_item} deduped across queries."""
        seen = {}
        for q in queries:
            items = raw_google_search(q, num_results=per_query_results)
            for item in items:
                link = item.get("link")
                if link and link not in seen:
                    seen[link] = item
        return seen

    def _assign_verification_status(self, record: dict, tier: str) -> str:
        deadline_norm = _normalize_date(record.get("application_deadline"))
        if deadline_norm:
            try:
                deadline_date = dt.datetime.strptime(deadline_norm, "%Y-%m-%d").date()
                if deadline_date < dt.date.today():
                    return "EXPIRED"
            except Exception:
                pass

        signal_fields = [
            record.get("minimum_cgpa"), record.get("maximum_income"),
            record.get("degree"), record.get("state"),
            record.get("category_requirement"), record.get("required_documents"),
        ]
        signal_count = sum(1 for f in signal_fields if f)

        if tier == "TIER1" and signal_count >= 2:
            return "VERIFIED"
        return "NEEDS_VERIFICATION"
