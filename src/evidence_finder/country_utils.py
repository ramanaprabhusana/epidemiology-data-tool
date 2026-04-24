"""
Country alias resolution and PubMed term normalization.

Centralises all country synonym logic so that:
- "US", "USA", "United States", "America" are all treated as equivalent when
  matching source country_filters.
- PubMed searches use the canonical MeSH term (e.g. "United States") rather
  than short codes like "US", which improves recall.
"""

from typing import Dict, List, Set

# ---------------------------------------------------------------------------
# Alias groups - each list is a set of synonyms (all lowercase).
# The FIRST entry in each list is the canonical PubMed / MeSH search term.
# ---------------------------------------------------------------------------
_ALIAS_GROUPS: List[List[str]] = [
    # United States
    ["united states", "us", "usa", "u.s.", "u.s.a.", "united states of america", "america"],
    # United Kingdom
    ["united kingdom", "uk", "gb", "gbr", "great britain", "england", "britain"],
    # Germany
    ["germany", "de", "deu", "deutschland"],
    # France
    ["france", "fr", "fra"],
    # Italy
    ["italy", "it", "ita"],
    # Spain
    ["spain", "es", "esp"],
    # Canada
    ["canada", "ca", "can"],
    # Australia
    ["australia", "au", "aus"],
    # Japan
    ["japan", "jp", "jpn"],
    # China
    ["china", "cn", "chn", "people's republic of china"],
    # India
    ["india", "in", "ind"],
    # Brazil
    ["brazil", "br", "bra", "brasil"],
    # Netherlands
    ["netherlands", "nl", "nld", "holland"],
    # Sweden
    ["sweden", "se", "swe"],
    # Norway
    ["norway", "no", "nor"],
    # Denmark
    ["denmark", "dk", "dnk"],
    # Finland
    ["finland", "fi", "fin"],
    # Belgium
    ["belgium", "be", "bel"],
    # Switzerland
    ["switzerland", "ch", "che"],
    # Austria
    ["austria", "at", "aut"],
    # EU / multi-country
    ["eu", "eu5", "europe", "european union"],
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
    the normalised (lowercase, stripped) input.
    """
    c = (country or "").strip().lower()
    return _ALIAS_TO_SET.get(c, {c})


def pubmed_country_term(country: str) -> str:
    """Return the canonical PubMed / MeSH search term for *country*.

    Examples:
        "US"    -> "United States"
        "USA"   -> "United States"
        "uk"    -> "United Kingdom"
        "de"    -> "Germany"
        "Japan" -> "Japan"  (already canonical)
        ""      -> ""
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
