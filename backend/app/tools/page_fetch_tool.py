"""
TOOL: Page Fetch Tool
Used by: Scholarship Discovery Agent

Fetches a source page's visible text so the extraction tool has real
page content to pull eligibility details and evidence from -- not just
a two-line search snippet. Network failures are always caught and
degrade to "no page text available" rather than crashing the pipeline;
callers must treat that as a reason to lower confidence
(NEEDS_VERIFICATION), never as a reason to fail loudly.

Uses a simple regex-based tag stripper by default so this has no hard
dependency beyond `requests`. If BeautifulSoup is installed, it's used
for cleaner extraction -- see requirements.txt.
"""
import re

_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html_regex(html: str) -> str:
    text = _SCRIPT_STYLE_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def _strip_html_bs4(html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return _WS_RE.sub(" ", soup.get_text(separator=" ")).strip()


def fetch_page_text(url: str, timeout: int = 8, max_chars: int = 20000) -> str | None:
    """
    Returns the page's visible text (truncated to max_chars), or None if
    the page could not be fetched. Never raises.
    """
    if not url:
        return None
    try:
        import requests
        resp = requests.get(
            url, timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (ScholarAI-DiscoveryAgent/1.0)"},
        )
        resp.raise_for_status()
        html = resp.text
        try:
            text = _strip_html_bs4(html)
        except Exception:
            text = _strip_html_regex(html)
        return text[:max_chars]
    except Exception:
        return None
