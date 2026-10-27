"""Organization name cleanup and fuzzy comparison.

Uses rapidfuzz when installed (fast). Falls back to Python's difflib so the
code still runs without it; results are similar but slower.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

try:
    from rapidfuzz import fuzz as _rf
except ImportError:  # pragma: no cover - fallback path
    _rf = None

_STOP = {"inc", "incorporated", "corp", "corporation", "co", "llc", "ltd", "the", "of", "and",
         "for", "a", "an", "trust", "fund"}
_REPLACE = [(r"&", " and "), (r"\bst\b", "saint"), (r"\bctr\b", "center"), (r"\bassn\b", "association"),
            (r"\bassoc\b", "association"), (r"\bfdn\b", "foundation"), (r"\bfndn\b", "foundation"),
            (r"\bhlth\b", "health"), (r"\bsvcs\b", "services"), (r"\bsvc\b", "service"),
            (r"\bcnty\b", "county"), (r"\bcty\b", "county"), (r"\bny\b", "new york"),
            (r"\bnys\b", "new york state"), (r"\bmt\b", "mount"), (r"\buniv\b", "university")]


def normalize(name: str | None) -> str:
    """'The Lakeview Health Fdn., Inc.' -> 'lakeview health foundation'"""
    if not name:
        return ""
    n = name.lower()
    n = re.sub(r"\bc/o\b.*$", "", n)          # drop "c/o John Smith"
    for pat, rep in _REPLACE:
        n = re.sub(pat, rep, n)
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    words = [w for w in n.split() if w not in _STOP]
    return " ".join(words)


def similarity(a: str, b: str) -> float:
    """0 to 100, order-insensitive. Inputs should already be normalized."""
    if not a or not b:
        return 0.0
    if _rf is not None:
        return float(_rf.token_sort_ratio(a, b))
    sa, sb = " ".join(sorted(a.split())), " ".join(sorted(b.split()))
    return 100.0 * SequenceMatcher(None, sa, sb).ratio()


def best_match(name: str, candidates: list[str], threshold: float) -> tuple[int, float] | None:
    """Index and score of the best candidate at or above threshold."""
    target = normalize(name)
    best = None
    for i, c in enumerate(candidates):
        s = similarity(target, normalize(c))
        if s >= threshold and (best is None or s > best[1]):
            best = (i, s)
    return best
