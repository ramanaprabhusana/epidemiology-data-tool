"""
Calculated confidence scoring for epidemiology evidence.
Rule-based score from: source tier, extraction success, completeness (definition, year, geography),
recency, and source URL verification.
Produces 0-100 score and Low/Medium/High label; supports a one-page rubric for methodology doc.

Fix (2026-04-28): Added source_url verification penalty and normalisation of legacy "dummy"
numeric confidence values (e.g. 0.7 floats from old CLL template rows).
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

import pandas as pd


# Tier weight (gold = highest confidence contribution)
TIER_WEIGHTS = {"gold": 35, "silver": 22, "bronze": 15}
# Max points per category (tier 35, extraction 30, completeness 25, recency 10, url 5)
EXTRACTION_EXTRACTED = 30  # value is not "See link"
EXTRACTION_STUB = 0
COMPLETENESS_FACTORS = ["definition", "year_or_range", "geography", "population"]
COMPLETENESS_POINTS_PER_FIELD = 6  # 4 fields * 6 = 24, cap at 25
RECENCY_CURRENT_YEAR_BONUS = 5
RECENCY_WITHIN_5_BONUS = 3
# Source URL: small bonus if URL present (confirms source is reachable)
URL_BONUS = 5
# Known authoritative source names that don't need URL (gold tier sources)
KNOWN_AUTHORITATIVE_SOURCES = {
    "seer", "globocan", "acs", "cdc", "nchs", "nci", "who",
    "nccn", "ash", "asco", "esmo", "eha", "fda", "joinpoint",
}


from ..utils import is_stub_value as _is_stub_value


def _tier_score(source_tier: Any) -> int:
    """Points from source tier (gold/silver/bronze)."""
    if source_tier is None or (isinstance(source_tier, float) and pd.isna(source_tier)):
        return TIER_WEIGHTS.get("bronze", 15)
    t = str(source_tier).strip().lower()
    return TIER_WEIGHTS.get(t, TIER_WEIGHTS.get("bronze", 15))


def _extraction_score(value: Any) -> int:
    """Points from extraction success: extracted value vs stub."""
    return EXTRACTION_EXTRACTED if not _is_stub_value(value) else EXTRACTION_STUB


def _url_score(row: Union[Dict[str, Any], pd.Series]) -> int:
    """
    Small URL verification bonus (0 or 5 points).
    - +5 if source_url is present and non-empty
    - 0 if source_url is null/empty, but no penalty if source is a known authority
    This prevents high-confidence scores for rows that have no verifiable URL
    and are not from a recognised authoritative database.
    """
    source_url = row.get("source_url") if hasattr(row, "get") else getattr(row, "source_url", None)
    has_url = (
        source_url is not None
        and not (isinstance(source_url, float) and pd.isna(source_url))
        and str(source_url).strip() not in ("", "nan")
    )
    if has_url:
        return URL_BONUS
    # No URL: check if the source citation contains a known authoritative name
    citation = row.get("source_citation") if hasattr(row, "get") else getattr(row, "source_citation", None)
    if citation:
        lower = str(citation).lower()
        if any(auth in lower for auth in KNOWN_AUTHORITATIVE_SOURCES):
            return 0  # no bonus, but no penalty (known source)
    return 0  # no URL, unknown source: no bonus (they already lost extraction points if stub)


def _completeness_score(row: Union[Dict[str, Any], pd.Series]) -> int:
    """Points from presence of definition, year_or_range, geography, population."""
    total = 0
    for field in COMPLETENESS_FACTORS:
        val = row.get(field) if hasattr(row, "get") else getattr(row, field, None)
        if val is not None and not (isinstance(val, float) and pd.isna(val)):
            s = str(val).strip()
            if s and s.lower() not in ("nan", ""):
                total += COMPLETENESS_POINTS_PER_FIELD
    return min(total, 25)


def _recency_score(row: Union[Dict[str, Any], pd.Series], current_year: int = None) -> int:
    """Points from year_or_range being recent (e.g. within 5 years)."""
    if current_year is None:
        current_year = datetime.now().year
    yr = row.get("year_or_range") if hasattr(row, "get") else getattr(row, "year_or_range", None)
    if yr is None or (isinstance(yr, float) and pd.isna(yr)):
        return 0
    s = str(yr).strip()
    if not s:
        return 0
    # Extract first 4-digit year
    match = re.search(r"20\d{2}|19\d{2}", s)
    if not match:
        return 0
    y = int(match.group(0))
    if y >= current_year - 1:
        return RECENCY_CURRENT_YEAR_BONUS
    if y >= current_year - 5:
        return RECENCY_WITHIN_5_BONUS
    return 0


def compute_confidence_score(row: Union[Dict[str, Any], pd.Series]) -> int:
    """
    Compute 0-100 confidence score for one evidence row.
    Factors:
      - Source tier (up to 35): gold=35, silver=22, bronze=15
      - Extraction success (0 or 30): 30 if numeric value extracted; 0 if stub
      - Completeness (up to 25): definition, year, geography, population
      - Recency (up to 10): current/recent year bonus
      - URL verification (0 or 5): bonus if source_url present

    Also normalises legacy "dummy" confidence values: if the existing
    'confidence' column contains a float like 0.7, 0.8 etc. (legacy scale)
    the computed score overrides it.
    """
    tier_pts = _tier_score(row.get("source_tier") if hasattr(row, "get") else getattr(row, "source_tier", None))
    value = row.get("value") if hasattr(row, "get") else getattr(row, "value", None)
    ext_pts = _extraction_score(value)
    comp_pts = _completeness_score(row)
    rec_pts = _recency_score(row)
    url_pts = _url_score(row)
    total = tier_pts + ext_pts + comp_pts + rec_pts + url_pts
    return min(100, max(0, total))


def normalise_legacy_confidence(evidence_df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect and fix 'dummy' confidence values in the existing 'confidence' column.

    Legacy format: float values 0.0-1.0 (e.g. 0.7) from old CLL templates.
    Current format: 'low' / 'medium' / 'high' label strings.

    Converts floats to labels: ≥0.7 → 'high', ≥0.4 → 'medium', else → 'low'.
    Also flags rows where confidence was a dummy numeric value.
    """
    if "confidence" not in evidence_df.columns:
        return evidence_df
    df = evidence_df.copy()

    def _fix_conf(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        s = str(val).strip().lower()
        # Already correct label
        if s in ("high", "medium", "low"):
            return s
        # Legacy float (e.g. "0.7" or 0.7)
        try:
            fval = float(s)
            if 0.0 <= fval <= 1.0:
                if fval >= 0.7:
                    return "high"
                elif fval >= 0.4:
                    return "medium"
                else:
                    return "low"
        except (ValueError, TypeError):
            pass
        return s  # leave unknown formats as-is

    df["confidence"] = df["confidence"].apply(_fix_conf)
    return df


def get_confidence_label(score: int) -> str:
    """Map numeric score to Low / Medium / High."""
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def add_computed_confidence(evidence_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add columns computed_confidence_score and computed_confidence to evidence_df.
    Does not overwrite existing confidence if present; adds computed as separate columns for transparency.
    """
    if evidence_df.empty:
        evidence_df["computed_confidence_score"] = []
        evidence_df["computed_confidence"] = []
        return evidence_df
    scores = evidence_df.apply(compute_confidence_score, axis=1)
    evidence_df = evidence_df.copy()
    evidence_df["computed_confidence_score"] = scores
    evidence_df["computed_confidence"] = scores.apply(get_confidence_label)
    return evidence_df


def get_rubric_markdown() -> str:
    """Return full confidence scoring rubric as markdown for methodology doc or export."""
    return """# Confidence Scoring Rubric

## Purpose
Each evidence row receives a **confidence score (0–100)** and a **label (Low / Medium / High)** so that downstream users and the KPI scorecard can distinguish high-confidence, source-backed values from weak or stub-only evidence.

## Factors and Weights

| Factor | Max points | Description |
|--------|------------|-------------|
| **Source tier** | 35 | Gold = 35, Silver = 22, Bronze = 15. Authoritative sources (e.g. SEER, CDC) contribute most. |
| **Extraction success** | 30 | 30 if the value is an extracted number or range; 0 if the value is "See link for..." (no datapoint extracted). |
| **Completeness** | 25 | Up to 6 points each for having definition, year_or_range, geography, population (max 25). |
| **Recency** | 10 | Bonus if year is within 1 year of current (5 pts) or within 5 years (3 pts). |

**Total:** 0–100. Rounded to integer; capped at 100.

## Label Interpretation

| Score range | Label | Interpretation |
|-------------|--------|-----------------|
| 70–100 | **High** | Strong source (gold/silver), value extracted, good context (year, geography). Safe to use for validation. |
| 40–69 | **Medium** | Reasonable source or partial context; or silver/bronze with extraction. Use with awareness of source. |
| 0–39 | **Low** | Stub-only (no extraction), or weak completeness/recency. Prefer other sources or manual check. |

## How to Use
- In the evidence table, use **computed_confidence** (or **confidence** if overwritten) to filter or sort.
- In the KPI scorecard, "validation readiness" can use these labels (e.g. require at least one High for "Ready").
- Do not treat Low as invalid-it may still be the only available link; treat it as "needs review."
"""


def export_rubric(path: Path) -> None:
    """Write the confidence rubric to a markdown file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(get_rubric_markdown(), encoding="utf-8")
