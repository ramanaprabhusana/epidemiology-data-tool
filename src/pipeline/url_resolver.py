"""
URL Resolver — maps source citation strings to canonical URLs.
Used to populate source_url when the web scraper doesn't extract one,
especially for CLL template rows that have citation text but no URL.

CLL evidence_data.csv has ~38.5% source_url null rows.
All other indications have >99% coverage.
This module fixes those null rows at pipeline export time.
"""

from __future__ import annotations
import re
from typing import Optional
import pandas as pd

# ── Authoritative source URL map ──────────────────────────────
# Keys are lowercase substrings to match in source_citation
KNOWN_SOURCE_URLS: dict[str, str] = {
    # Gold tier — national cancer registries
    "seer stat fact":      "https://seer.cancer.gov/statfacts/",
    "seer.cancer.gov":     "https://seer.cancer.gov/statfacts/",
    "seer piam":           "https://seer.cancer.gov/piam/",
    "seer":                "https://seer.cancer.gov/",
    "globocan":            "https://gco.iarc.fr/today/",
    "gco.iarc":            "https://gco.iarc.fr/today/",
    "acs cancer facts":    "https://www.cancer.org/research/cancer-facts-statistics/",
    "american cancer society": "https://www.cancer.org/research/cancer-facts-statistics/",
    "cdc wonder":          "https://wonder.cdc.gov/",
    "cdc nchs":            "https://www.cdc.gov/nchs/",
    "nchs":                "https://www.cdc.gov/nchs/",
    "nci":                 "https://www.cancer.gov/",
    "national cancer inst": "https://www.cancer.gov/",
    # Silver tier — clinical guidelines and registries
    "nccn":                "https://www.nccn.org/guidelines/",
    "ash":                 "https://www.hematology.org/education/clinicians/guidelines-and-quality-care/clinical-practice-guidelines",
    "asco":                "https://www.asco.org/practice-policy/guidelines",
    "esmo":                "https://www.esmo.org/guidelines",
    "eha":                 "https://ehaweb.org/education/eha-clinical-practice-guidelines/",
    "fda":                 "https://www.fda.gov/patients/blood-cancers/",
    # InsightACE
    "insightace":          "https://www.insightace.com/",
    "insight ace":         "https://www.insightace.com/",
    # Joinpoint / statistical methods
    "joinpoint":           "https://surveillance.cancer.gov/joinpoint/",
    "aapc":                "https://surveillance.cancer.gov/joinpoint/",
    "annual percent change": "https://surveillance.cancer.gov/joinpoint/",
    # PubMed literature
    "pubmed":              "https://pubmed.ncbi.nlm.nih.gov/",
    "ncbi":                "https://pubmed.ncbi.nlm.nih.gov/",
    "j clin oncol":        "https://ascopubs.org/journal/jco",
    "blood":               "https://ashpublications.org/blood/",
    "lancet":              "https://www.thelancet.com/",
    "nejm":                "https://www.nejm.org/",
    "new england journal": "https://www.nejm.org/",
    "nature":              "https://www.nature.com/",
    "jama":                "https://jamanetwork.com/journals/jama",
    # Biomarker databases
    "tcga":                "https://www.cancer.gov/tcga",
    "cbioportal":          "https://www.cbioportal.org/",
    "cosmic":              "https://cancer.sanger.ac.uk/cosmic",
}

# Pattern to find a URL already embedded in citation text
_URL_PATTERN = re.compile(
    r"https?://[^\s\)\]\"']+",
    re.IGNORECASE,
)

# PubMed ID pattern
_PMID_PATTERN = re.compile(r"(?:PMID|pmid)[:\s]+(\d{6,10})")


def resolve_url(source_citation: str) -> Optional[str]:
    """
    Given a source_citation string, return the best canonical URL.
    Priority:
      1. Extract URL embedded in citation text
      2. Extract PubMed ID and build PubMed URL
      3. Match known source keywords
      4. Return None if no match
    """
    if not source_citation or not isinstance(source_citation, str):
        return None
    s = source_citation.strip()
    if not s:
        return None

    # 1. URL already in citation
    found = _URL_PATTERN.search(s)
    if found:
        return found.group(0).rstrip(".,;)")

    # 2. PubMed ID
    pmid_match = _PMID_PATTERN.search(s)
    if pmid_match:
        return f"https://pubmed.ncbi.nlm.nih.gov/{pmid_match.group(1)}/"

    # 3. Keyword matching (case-insensitive)
    lower = s.lower()
    for key, url in KNOWN_SOURCE_URLS.items():
        if key in lower:
            return url

    return None


def add_resolved_urls(evidence_df: pd.DataFrame) -> pd.DataFrame:
    """
    For rows where source_url is null/empty, attempt to resolve from
    source_citation. Returns DataFrame with source_url filled where possible.
    Only fills; never overwrites existing non-null source_url values.
    """
    if evidence_df.empty:
        return evidence_df

    df = evidence_df.copy()

    if "source_url" not in df.columns:
        df["source_url"] = None

    # Identify rows needing resolution
    needs_url = df["source_url"].isna() | (df["source_url"].astype(str).str.strip() == "")
    needs_url &= df["source_citation"].notna()

    n_before = needs_url.sum()
    if n_before == 0:
        return df

    df.loc[needs_url, "source_url"] = df.loc[needs_url, "source_citation"].apply(resolve_url)

    n_after = (df["source_url"].isna() | (df["source_url"].astype(str).str.strip() == "")).sum()
    resolved = n_before - n_after
    if resolved > 0:
        import logging
        logging.getLogger(__name__).info(
            f"URL resolver: resolved {resolved}/{n_before} null source_url rows"
        )

    return df


def get_url_coverage_report(evidence_df: pd.DataFrame) -> dict:
    """Return null source_url counts per indication for audit."""
    if evidence_df.empty or "source_url" not in evidence_df.columns:
        return {}
    null_mask = evidence_df["source_url"].isna() | (
        evidence_df["source_url"].astype(str).str.strip() == ""
    )
    total = evidence_df.groupby("indication").size()
    nulls = evidence_df[null_mask].groupby("indication").size()
    report = {}
    for ind in total.index:
        n_null = nulls.get(ind, 0)
        n_total = total[ind]
        report[ind] = {
            "total": int(n_total),
            "null_url": int(n_null),
            "coverage_pct": round(100 * (1 - n_null / n_total), 1),
        }
    return report
