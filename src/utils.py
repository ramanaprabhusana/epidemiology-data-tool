"""
Shared utility functions used across repository, analytics, and pipeline modules.
Centralizes helpers that were previously duplicated in scorecard, reconciliation,
evidence_summary, white_space, and confidence modules.
"""

import re
from typing import Any, Optional

import pandas as pd


def is_stub_value(value: Any) -> bool:
    """True if value indicates no extracted datapoint (e.g. 'See link for...')."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    s = str(value).strip().lower()
    return "see link" in s or s == "" or s == "nan"


def extract_first_numeric(value: Any) -> Optional[float]:
    """
    Extract first plausible numeric from value string.
    Handles "21000", "100,000 (incidence)", "2.5 (rate); 10 (percent)", etc.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s or is_stub_value(value):
        return None
    # Remove parenthetical suffixes like "(incidence)" for parsing
    s_clean = re.sub(r"\s*\([^)]*\)\s*", " ", s)
    # Match numbers: comma-formatted first (e.g. 21,000), then plain integers/decimals
    match = re.search(r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)", s_clean)
    if not match:
        return None
    try:
        num = float(match.group(1).replace(",", ""))
        # Sanity: exclude years, tiny decimals that might be rates
        if 1e-2 <= num <= 1e8 or (0 < num < 1e-2 and "." in match.group(1)):
            return num
        if num >= 1900 and num <= 2050:
            return None  # likely a year
        return num
    except (ValueError, TypeError):
        return None


def tier_rank(tier: Any) -> int:
    """Lower is better: gold=0, silver=1, bronze=2."""
    if tier is None or (isinstance(tier, float) and pd.isna(tier)):
        return 2
    t = str(tier).strip().lower()
    if t == "gold":
        return 0
    if t == "silver":
        return 1
    return 2
