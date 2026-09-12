"""
TOOL: Deduplication Tool
Used by: Scholarship Discovery Agent

The same scholarship often appears on multiple pages (an aggregator
listing plus the official portal, for instance). Groups records by a
normalized provider+name identity, keeps the single most trustworthy
record as primary, and files the rest as secondary discovery sources
rather than creating duplicate entries.
"""
import re

_TIER_RANK = {"TIER1": 3, "TIER2": 2, "TIER3": 1, "UNKNOWN": 0}
_VERIFICATION_RANK = {"VERIFIED": 3, "NEEDS_VERIFICATION": 2, "EXPIRED": 1, None: 0}


def _normalize(s):
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _identity_key(record):
    provider = record.get("provider") or record.get("source_name") or ""
    name = record.get("scholarship_name") or ""
    return _normalize(provider) + "|" + _normalize(name)


def dedupe_records(records, tiers=None):
    """
    records: list of extracted scholarship dicts (must include
             verification_status by the time this runs).
    tiers: optional {source_url: tier_string} map used to break ties
           between records describing the same scholarship.
    Returns (deduped_records, duplicates_removed_count).
    """
    tiers = tiers or {}
    groups = {}
    for r in records:
        key = _identity_key(r)
        if not key.strip("|"):
            continue  # no usable identity -- caller's data-quality filter should already have rejected this
        groups.setdefault(key, []).append(r)

    deduped = []
    duplicates_removed = 0

    for key, group in groups.items():
        if len(group) == 1:
            deduped.append(group[0])
            continue

        def rank(rec):
            tier = tiers.get(rec.get("source_url"), "UNKNOWN")
            return (_TIER_RANK.get(tier, 0), _VERIFICATION_RANK.get(rec.get("verification_status"), 0))

        group_sorted = sorted(group, key=rank, reverse=True)
        primary = dict(group_sorted[0])
        secondary_sources = []
        for other in group_sorted[1:]:
            if other.get("source_url"):
                secondary_sources.append(other["source_url"])
        primary["secondary_sources"] = list(dict.fromkeys(secondary_sources))
        deduped.append(primary)
        duplicates_removed += len(group) - 1

    return deduped, duplicates_removed
