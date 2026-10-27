"""Tag grant lines with mission themes from config/taxonomy.yaml."""
from __future__ import annotations


class ThemeTagger:
    def __init__(self, taxonomy: dict):
        self.themes = taxonomy["themes"]
        self.generic = [g.lower() for g in taxonomy.get("generic_purpose", [])]

    def tag(self, purpose: str | None, recipient: str | None, ntee: str | None) -> set[str]:
        text = f" {(purpose or '').lower()} {(recipient or '').lower()} "
        ntee = (ntee or "").upper()
        found = set()
        for theme, spec in self.themes.items():
            if any(k.lower() in text for k in spec.get("keywords", [])):
                found.add(theme)
            elif ntee and any(ntee.startswith(p) for p in spec.get("ntee", [])):
                found.add(theme)
        return found

    def is_vague(self, purpose: str | None, recipient: str | None, ntee: str | None) -> bool:
        """True when a line tells us nothing about mission: a generic or blank
        purpose, no theme hit in the recipient name, and no NTEE code."""
        if ntee:
            return False
        if self.tag(None, recipient, None):
            return False
        p = (purpose or "").lower().strip(" .")
        return not p or any(g in p for g in self.generic) and len(p) <= 60

    def value(self, themes: set[str], weights: dict) -> float:
        return max((weights.get(t, 0.0) for t in themes), default=0.0)
