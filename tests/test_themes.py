"""Matching rules for ThemeTagger, plus regressions found on real grant text
(analysis/taxonomy_eval/)."""
from prospector.config import load_taxonomy
from prospector.themes import ThemeTagger

TOY = {
    "generic_purpose": ["general support"],
    "generic_exact": ["general"],
    "themes": {
        "substance_use": {"keywords": ["addict", "sud "]},
        "agriculture": {"keywords": ["farm "], "exclude": ["farm animal"]},
        "human_services": {"keywords": ["boys and girls club", "child"],
                           "exclude": ["children's hospital"], "ntee": ["P"]},
    },
}


def test_keyword_matches_at_word_start_only():
    t = ThemeTagger({"themes": {"ag": {"keywords": ["ranch"]}}})
    assert t.tag("Ranch hands", None, None) == {"ag"}
    assert t.tag("Long Branch recreation", None, None) == set()


def test_stem_and_whole_word_keywords():
    t = ThemeTagger(TOY)
    assert "substance_use" in t.tag("Addiction recovery", None, None)
    assert "substance_use" in t.tag("SUD/OUD treatment", None, None)
    assert "substance_use" not in t.tag(None, "Sudbury Valley Trustees", None)
    assert "substance_use" not in t.tag("Schools in South Sudan", None, None)


def test_punctuation_is_ignored():
    # "&" becomes a space, not "and", so taxonomy.yaml lists both spellings.
    t = ThemeTagger({"themes": {"hs": {"keywords": ["boys girls club"]}}})
    assert t.tag(None, "Boys & Girls Club of Boston", None) == {"hs"}
    assert t.tag(None, "BOYS/GIRLS-CLUB", None) == {"hs"}


def test_exclude_blanks_phrase_but_not_ntee():
    t = ThemeTagger(TOY)
    assert t.tag("General", "Boston Children's Hospital", None) == set()
    assert t.tag("General", "Boston Children's Hospital", "P30") == {"human_services"}
    assert t.tag(None, "Winslow Farm Animal Sanctuary", None) == set()
    assert t.tag(None, "Wright-Locke Farm", None) == {"agriculture"}


def test_generic_exact_only_when_whole_purpose():
    t = ThemeTagger(TOY)
    assert t.is_vague("GENERAL", "Some Org", None)
    assert t.is_vague("For general support.", "Some Org", None)
    assert not t.is_vague("General education", "Some Org", None)
    assert not t.is_vague("General", "Some Org", "A51")      # NTEE known -> not vague


def test_real_taxonomy_regressions():
    t = ThemeTagger(load_taxonomy())
    assert t.tag("SCHOLARSHIP", "Skidmore College", "B42") == set()
    assert t.tag("General operating", "Beth Israel Deaconess Medical Center", "E22") == set()
    assert t.tag(None, "Lowell Day Nursery Association", None) == set()
    assert t.tag("General", "Sudbury Valley Trustees", None) == set()
    assert t.tag("GRANTS", "American Red Cross & its Chapters and Branches", None) == set()
    assert t.tag("Charitable purpose", "Montville Twp Drug Awareness Council", None) == {"substance_use"}
    assert t.tag("Unrestricted", "National Alliance on Mental Illness", None) == {"behavioral_health"}
    assert t.is_vague("TO AID THE DONEE IN ITS EXEMPT FUNCTIONS", "Some Org", None)
