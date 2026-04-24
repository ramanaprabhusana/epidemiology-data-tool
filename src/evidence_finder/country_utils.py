"""
Country alias resolution and PubMed term normalization.

Centralises all country synonym logic so that:
- "US", "USA", "United States", "America" are all treated as equivalent when
  matching source country_filters.
- PubMed searches use the canonical MeSH term (e.g. "United States") rather
  than short codes like "US", which improves recall.
- Users typing any alias (e.g. "nippon", "prc", "oz") get the same coverage
  as typing the canonical name.
"""

from typing import Dict, List, Set

# ---------------------------------------------------------------------------
# Alias groups - each list is a set of synonyms (all lowercase).
# The FIRST entry in each list is the canonical PubMed / MeSH search term.
# EU5 is kept as an alias (not in UI) for backward compatibility with
# any existing evidence tagged "EU5".
# ---------------------------------------------------------------------------
_ALIAS_GROUPS: List[List[str]] = [
    # United States
    [
        "united states", "us", "usa", "u.s.", "u.s.a.",
        "united states of america", "america", "american",
    ],
    # United Kingdom
    [
        "united kingdom", "uk", "gb", "gbr", "great britain",
        "england", "britain", "british", "scotland", "wales", "northern ireland",
    ],
    # Germany
    [
        "germany", "de", "deu", "deutschland", "german", "bundesrepublik",
    ],
    # France
    [
        "france", "fr", "fra", "french", "republique francaise",
        "republique francaise", "french republic",
    ],
    # Canada
    [
        "canada", "ca", "can", "canadian",
    ],
    # Japan
    [
        "japan", "jp", "jpn", "japanese", "nippon", "nihon",
    ],
    # China
    [
        "china", "cn", "chn", "chinese", "prc",
        "people's republic of china", "peoples republic of china",
        "mainland china", "zhongguo",
    ],
    # Italy
    [
        "italy", "it", "ita", "italian", "italia",
    ],
    # Spain
    [
        "spain", "es", "esp", "spanish", "espana", "espana",
    ],
    # Australia
    [
        "australia", "au", "aus", "australian", "oz",
    ],
    # South Korea
    [
        "south korea", "korea", "kr", "kor", "republic of korea", "korean",
    ],
    # India
    [
        "india", "in", "ind", "indian",
    ],
    # Brazil
    [
        "brazil", "br", "bra", "brasil", "brazilian",
    ],
    # Netherlands
    [
        "netherlands", "nl", "nld", "holland", "dutch",
    ],
    # Sweden
    [
        "sweden", "se", "swe", "swedish",
    ],
    # Norway
    [
        "norway", "no", "nor", "norwegian",
    ],
    # Denmark
    [
        "denmark", "dk", "dnk", "danish",
    ],
    # Finland
    [
        "finland", "fi", "fin", "finnish",
    ],
    # Belgium
    [
        "belgium", "be", "bel", "belgian",
    ],
    # Switzerland
    [
        "switzerland", "ch", "che", "swiss",
    ],
    # Austria
    [
        "austria", "at", "aut", "austrian",
    ],
    # Mexico
    [
        "mexico", "mx", "mex", "mexican", "mexico",
    ],
    # Russia
    [
        "russia", "ru", "rus", "russian", "russian federation",
    ],
    # South Africa
    [
        "south africa", "za", "zaf", "south african",
    ],
    # Saudi Arabia
    [
        "saudi arabia", "sa", "sau", "ksa", "saudi",
    ],
    # Turkey
    [
        "turkey", "tr", "tur", "turkish", "turkiye",
    ],
    # Singapore
    [
        "singapore", "sg", "sgp", "singaporean",
    ],
    # Taiwan
    [
        "taiwan", "tw", "twn", "chinese taipei", "republic of china",
    ],
    # Portugal
    [
        "portugal", "pt", "prt", "portuguese",
    ],
    # Poland
    [
        "poland", "pl", "pol", "polish",
    ],
    # Israel
    [
        "israel", "il", "isr", "israeli",
    ],
    # New Zealand
    [
        "new zealand", "nz", "nzl", "new zealander", "aotearoa",
    ],
    # EU / multi-country (eu5 kept as alias for backward compat)
    [
        "eu", "eu5", "europe", "european union", "european",
    ],
]

# Build fast lookup: lowercase alias -> canonical term (first in group)
_ALIAS_TO_CANONICAL: Dict[str, str] = {}
# Build lookup: lowercase alias -> full set of aliases
_ALIAS_TO_SET: Dict[str, Set[str]] = {}

for _group in _ALIAS_GROUPS:
    _canonical = _group[0]
    _group_set = set(_group)
    for _alias in _group:
        _ALIAS_TO_CANONICAL[_alias] = _canonical
        _ALIAS_TO_SET[_alias] = _group_set


def country_aliases(country: str) -> Set[str]:
    """Return all known lowercase aliases for *country* (including itself).

    If the country is not in the alias map, returns a single-element set with
    the normalised (lowercase, stripped) input so the pipeline still works for
    any unlisted country.

    Examples:
        country_aliases("US")      -> {"us","usa","united states","america",...}
        country_aliases("nippon")  -> {"japan","jp","jpn","japanese","nippon","nihon"}
        country_aliases("prc")     -> {"china","cn","chn","chinese","prc",...}
        country_aliases("xyz")     -> {"xyz"}  (unknown - returned as-is)
    """
    c = (country or "").strip().lower()
    return _ALIAS_TO_SET.get(c, {c})


def pubmed_country_term(country: str) -> str:
    """Return the canonical PubMed / MeSH search term for *country*.

    Uses the first (canonical) entry of the matching alias group, which is
    always the full English name matching MeSH vocabulary.

    Examples:
        pubmed_country_term("US")      -> "United States"
        pubmed_country_term("USA")     -> "United States"
        pubmed_country_term("nippon")  -> "Japan"
        pubmed_country_term("prc")     -> "China"
        pubmed_country_term("oz")      -> "Australia"
        pubmed_country_term("uk")      -> "United Kingdom"
        pubmed_country_term("de")      -> "Germany"
        pubmed_country_term("")        -> ""
    """
    c = (country or "").strip().lower()
    if not c:
        return ""
    canonical = _ALIAS_TO_CANONICAL.get(c)
    if canonical:
        # Capitalise first letter of each word to match MeSH style
        return canonical.title()
    # Unknown country - return as-is (original capitalisation preserved)
    return (country or "").strip()
