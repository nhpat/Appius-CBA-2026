"""Tag grant lines with mission themes from config/taxonomy.yaml.

Matching rules (see the header of taxonomy.yaml):
  - Text is lowercased and every run of non-alphanumeric characters becomes one
    space, so "Boys & Girls Club" -> "boys girls club", "SUD/OUD" -> "sud oud".
  - A keyword matches at the START of a word and may run on, so "addict" catches
    "addiction" but "ranch" no longer catches "branch". End a keyword with a space
    (quote it in YAML: "sud ") to require the whole word.
  - A theme's `exclude` phrases are blanked out before its keywords are checked,
    so "children's hospital" doesn't count as "child" for human_services.
"""
from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _norm(s: str | None) -> str:
    return _NON_ALNUM.sub(" ", (s or "").lower())


def _norm_kw(k: str) -> str:
    """Normalize a keyword the same way as text, keeping a trailing space
    (whole-word marker) if the YAML string had one."""
    whole = k.endswith(" ")
    k = _norm(k).strip()
    return k + " " if whole else k


class ThemeTagger:
    def __init__(self, taxonomy: dict):
        self.themes = {}
        for theme, spec in taxonomy["themes"].items():
            self.themes[theme] = {
                "keywords": [" " + _norm_kw(k) for k in spec.get("keywords", [])],
                "exclude": [" " + _norm(x).strip() + " " for x in spec.get("exclude", [])],
                "ntee": [p.upper() for p in spec.get("ntee", [])],
            }
        self.generic = [_norm(g).strip() for g in taxonomy.get("generic_purpose", [])]
        self.generic_exact = {_norm(g).strip() for g in taxonomy.get("generic_exact", [])}

    def tag(self, purpose: str | None, recipient: str | None, ntee: str | None) -> set[str]:
        text = f" {_norm(purpose)} {_norm(recipient)} "
        text = re.sub(" +", " ", text)
        ntee = (ntee or "").upper()
        found = set()
        for theme, spec in self.themes.items():
            t = text
            for x in spec["exclude"]:
                t = t.replace(x, " ")
            if any(k in t for k in spec["keywords"]):
                found.add(theme)
            elif ntee and any(ntee.startswith(p) for p in spec["ntee"]):
                found.add(theme)
        return found

    def is_vague(self, purpose: str | None, recipient: str | None, ntee: str | None) -> bool:
        """True when a line tells us nothing about mission: a generic or blank
        purpose, no theme hit in the recipient name, and no NTEE code."""
        if ntee:
            return False
        if self.tag(None, recipient, None):
            return False
        p = re.sub(" +", " ", _norm(purpose)).strip()
        if not p or p in self.generic_exact:
            return True
        return any(g in p for g in self.generic) and len(p) <= 60

    def value(self, themes: set[str], weights: dict) -> float:
        return max((weights.get(t, 0.0) for t in themes), default=0.0)
