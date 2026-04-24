"""
Resolve UI indication labels to curated-data slugs and API-friendly search strings.

PubMed uses multiple phrasings (concept expansion) instead of a single literal string.
ClinicalTrials tries several condition strings and keeps the best hit count.
"""

from __future__ import annotations

import re
from typing import List, Optional

from .country_utils import pubmed_country_term, country_aliases


def _lower(s: str) -> str:
    return (s or "").strip().lower()


def _match_normalize(s: str) -> str:
    """
    Lowercase text for substring checks. Maps Unicode dashes to ASCII hyphen so
    labels that use Unicode dash characters still match "non-hodgkin".
    """
    t = _lower(s)
    for ch in ("\u2013", "\u2014", "\u2212"):
        t = t.replace(ch, "-")
    return t


def curated_slug_candidates(indication: str) -> List[str]:
    """
    Ordered slugs to try for config/curated_data/{slug}.yaml (basename without .yaml).
    """
    raw = (indication or "").strip()
    slug = raw.lower().replace(" ", "_").replace("(", "").replace(")", "")
    for ch in ("\u2013", "\u2014", "\u2212"):
        slug = slug.replace(ch, "-")
    out: List[str] = []

    def add(x: str) -> None:
        if x and x not in out:
            out.append(x)

    add(slug)

    sl = _match_normalize(raw)
    compact = re.sub(r"[\s\-]+", "", sl)
    if "cll" in sl or "chronic lymphocytic" in sl:
        add("cll")
    if "hodgkin" in sl and "non" not in sl:
        add("hodgkin")
    is_nhl = (
        "non-hodgkin" in sl
        or "non hodgkin" in sl
        or "nonhodgkin" in compact
        or ("nhl" in sl and "hodgkin" in sl)
        or (re.search(r"\bnhl\b", sl) is not None and "lymphoma" in sl)
        or (re.search(r"\bnhl\b", sl) is not None and "dlbcl" in sl)
        or ("hogdkin" in sl and "non" in sl and "lymphoma" in sl)
        or ("lymphoma" in sl and "dlbcl" in sl and "excl" in sl)
    )
    if is_nhl:
        add("nhl")
    if "gastric" in sl or "(gc)" in sl:
        add("gc")
    if "ovarian" in sl:
        add("ovarian")
    if "prostate" in sl:
        add("prostate")
    if "lung" in sl:
        add("lung_cancer")
    if "breast" in sl:
        add("breast_cancer")

    if "nhl" in out:
        out.remove("nhl")
        out.insert(0, "nhl")

    return out


def trial_search_conditions(display_indication: str) -> List[str]:
    """Short condition strings for ClinicalTrials.gov (tried in order until counts stabilize)."""
    sl = _match_normalize(display_indication)
    compact = re.sub(r"[\s\-]+", "", sl)
    if (
        "non-hodgkin" in sl
        or "non hodgkin" in sl
        or "nonhodgkin" in compact
        or ("nhl" in sl and "non" in sl)
        or (re.search(r"\bnhl\b", sl) is not None and "lymphoma" in sl)
        or (re.search(r"\bnhl\b", sl) is not None and "dlbcl" in sl)
        or ("hogdkin" in sl and "non" in sl and "lymphoma" in sl)
        or ("lymphoma" in sl and "dlbcl" in sl and "excl" in sl)
    ):
        return [
            "Non-Hodgkin lymphoma",
            "Lymphoma, Non-Hodgkin",
            "NHL",
        ]
    if "hodgkin" in sl and "non" not in sl:
        return ["Hodgkin lymphoma", "Hodgkin Lymphoma"]
    if "cll" in sl or "chronic lymphocytic" in sl:
        return ["Chronic lymphocytic leukemia", "CLL", "Chronic Lymphocytic Leukemia"]
    if "gastric" in sl or "(gc)" in sl:
        return ["Gastric cancer", "Stomach cancer"]
    if "ovarian" in sl:
        return ["Ovarian cancer", "Ovarian neoplasms"]
    if "prostate" in sl:
        return ["Prostate cancer", "Prostatic neoplasms"]
    base = re.sub(r"\s*\([^)]*\)\s*", " ", display_indication or "").strip()
    return [base] if base else ["cancer"]


def pubmed_expanded_queries(display_indication: str, country: Optional[str]) -> List[str]:
    """
    Multiple PubMed query strings (concept expansion, not strict lexical AND on one long UI label).

    Uses the canonical PubMed/MeSH country term (e.g. "United States" instead of "US")
    so that results are not missed due to abbreviation mismatches. All country aliases
    are preserved as additional query variants to maximise recall.
    """
    sl = _match_normalize(display_indication)
    compact = re.sub(r"[\s\-]+", "", sl)

    # Primary geo term - use canonical MeSH form for best PubMed recall
    geo_primary = pubmed_country_term(country or "")
    geo = f" {geo_primary}" if geo_primary else ""

    # Build extra geo variants from all aliases (e.g. add "US" and "USA" queries too)
    extra_geo_variants: List[str] = []
    if country:
        aliases = country_aliases(country)
        canonical_lower = geo_primary.lower()
        for alias in sorted(aliases):
            if alias != canonical_lower and len(alias) <= 30:
                extra_geo_variants.append(alias.upper() if len(alias) <= 3 else alias.title())

    queries: List[str] = []

    def q(s: str) -> None:
        if s.strip() and s not in queries:
            queries.append(s.strip())

    if (
        "non-hodgkin" in sl
        or "non hodgkin" in sl
        or "nonhodgkin" in compact
        or ("nhl" in sl and "non" in sl)
        or (re.search(r"\bnhl\b", sl) is not None and "lymphoma" in sl)
        or (re.search(r"\bnhl\b", sl) is not None and "dlbcl" in sl)
        or ("hogdkin" in sl and "non" in sl and "lymphoma" in sl)
        or ("lymphoma" in sl and "dlbcl" in sl and "excl" in sl)
    ):
        q(f"non-Hodgkin lymphoma epidemiology incidence prevalence{geo}")
        q(f"NHL lymphoma population-based cohort{geo}")
        q(f"B-cell lymphoma epidemiology SEER{geo}")
        q(f"T-cell lymphoma epidemiology{geo}")
        q(f"diffuse large B-cell lymphoma incidence prevalence{geo}")
        q(f"follicular lymphoma epidemiology{geo}")
    elif "hodgkin" in sl and "non" not in sl:
        q(f"Hodgkin lymphoma epidemiology incidence survival{geo}")
        q(f"classical Hodgkin lymphoma population cohort{geo}")
    elif "cll" in sl or "chronic lymphocytic" in sl:
        q(f"chronic lymphocytic leukemia epidemiology incidence prevalence{geo}")
        q(f"CLL population-based study{geo}")
    elif "gastric" in sl or "(gc)" in sl:
        q(f"gastric cancer epidemiology incidence mortality{geo}")
        q(f"stomach neoplasm SEER{geo}")
    elif "ovarian" in sl:
        q(f"ovarian cancer epidemiology incidence prevalence{geo}")
    elif "prostate" in sl:
        q(f"prostate cancer epidemiology incidence mortality{geo}")
    else:
        q(f"{display_indication} cancer epidemiology{geo}")

    # Add alias-variant queries for extra coverage (e.g. same query with "US" or "USA")
    base_queries = list(queries)
    for variant in extra_geo_variants:
        for bq in base_queries:
            if geo_primary and geo_primary in bq:
                alias_q = bq.replace(geo_primary, variant)
                q(alias_q)

    return queries[:12]


def semantic_abstract_score(abstract: str, reference_blob: str) -> float:
    """
    Lightweight relevance: token overlap between abstract and a reference string,
    boosted for epidemiology terms (no external ML models).
    """
    def tok(s: str) -> set:
        return set(re.findall(r"[a-zA-Z]{3,}", (s or "").lower()))

    a = tok(abstract)
    r = tok(reference_blob)
    if not a or not r:
        return 0.0
    inter = len(a & r)
    union = len(a | r) or 1
    jacc = inter / union
    epi = sum(1 for w in ("incidence", "prevalence", "cohort", "population", "epidemiol", "mortality", "survival") if w in abstract.lower())
    return jacc + 0.07 * min(epi, 6)
