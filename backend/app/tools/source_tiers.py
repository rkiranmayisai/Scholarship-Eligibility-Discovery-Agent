"""
TOOL: Source Tier Classifier
Used by: Scholarship Discovery Agent

Classifies a URL's domain into the tier system the Discovery Agent spec
requires. Tier drives how much a record can be trusted before it's
allowed to be marked VERIFIED (see scholarship_extraction_tool.py and
discovery_agent.py for how tier feeds into verification_status).
"""
from urllib.parse import urlparse

TIER1_DOMAIN_FRAGMENTS = [
    "scholarships.gov.in", "aicte-india.org", "aicte-pragati-saksham-gov.in",
    "ugc.gov.in", "ugc.ac.in", "education.gov.in", "nic.in",
    ".gov.in", "cgg.gov.in",  # covers most state portals (telangana, etc.)
    "tsche.telangana.gov.in", "online-dst.gov.in",
]

TIER2_DOMAIN_FRAGMENTS = [
    "tatatrusts.org", "jntataendowment.org", "reliancefoundation.org",
    "hdfcbank.com", "ongcindia.com", "wiprocares.com", "larsentoubro.com",
    "sitaramjindalfoundation.org", "colgatepalmolive.com",
    "google.com", "microsoft.com", "buildyourfuture.withgoogle.com",
    ".edu", ".ac.in",  # university sites
]

TIER3_DOMAIN_FRAGMENTS = [
    "buddy4study.com", "scholarships.com", "unigo.com", "collegedunia.com",
    "vidyasaarathi.co.in", "shiksha.com", "getmyuni.com", "careers360.com",
]


def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def classify_source_tier(url: str) -> str:
    """Returns 'TIER1', 'TIER2', 'TIER3', or 'UNKNOWN'."""
    domain = get_domain(url)
    if not domain:
        return "UNKNOWN"
    if any(frag in domain for frag in TIER1_DOMAIN_FRAGMENTS):
        return "TIER1"
    if any(frag in domain for frag in TIER2_DOMAIN_FRAGMENTS):
        return "TIER2"
    if any(frag in domain for frag in TIER3_DOMAIN_FRAGMENTS):
        return "TIER3"
    return "UNKNOWN"
