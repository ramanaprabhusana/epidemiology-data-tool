"""
Insights generation: summary stats, gap/conflict flags, and narrative-style summaries
for dashboards and reports.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def build_insights_summary(
    evidence_df: pd.DataFrame,
    kpi_df: Optional[pd.DataFrame] = None,
    indication: str = "",
) -> pd.DataFrame:
    """
    Build a structured insights summary table for dashboards:
    - Metric-level: evidence count, tier mix, year range, gap flag.
    - Optional: one-row summary (indication, total_evidence, gaps_count, coverage_pct).
    Returns a DataFrame suitable for Tableau/Power BI (one row per metric or one summary row).
    """
    if evidence_df.empty:
        return pd.DataFrame(columns=["indication", "metric", "evidence_count", "tiers", "year_min", "year_max", "has_gap", "insight_text"])

    evidence_df = evidence_df.copy()
    evidence_df["year_parsed"] = evidence_df.get("year_or_range", "").apply(_parse_year_for_insight)

    by_metric = evidence_df.groupby("metric").agg(
        evidence_count=("value", "count"),
        source_tiers=("source_tier", lambda s: ", ".join(sorted(s.dropna().unique().astype(str)))),
        year_min=("year_parsed", "min"),
        year_max=("year_parsed", "max"),
    ).reset_index()

    gaps = set()
    if kpi_df is not None and not kpi_df.empty and "gap" in kpi_df.columns and "metric_id" in kpi_df.columns:
        gap_mask = (kpi_df["gap"] == True) | (kpi_df["gap"].astype(str).str.lower() == "true")  # noqa: E712
        gaps = set(kpi_df.loc[gap_mask, "metric_id"].dropna().astype(str))

    by_metric["has_gap"] = by_metric["metric"].isin(gaps)
    by_metric["indication"] = indication
    by_metric["insight_text"] = by_metric.apply(
        lambda r: _one_line_insight(r["metric"], r["evidence_count"], r["source_tiers"], r["year_min"], r["year_max"], r["has_gap"]),
        axis=1,
    )
    by_metric = by_metric.rename(columns={"source_tiers": "tiers"})
    cols = ["indication", "metric", "evidence_count", "tiers", "year_min", "year_max", "has_gap", "insight_text"]
    return by_metric[[c for c in cols if c in by_metric.columns]]


def _parse_year_for_insight(val: Any) -> Optional[int]:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        s = str(val).strip()
        if "-" in s:
            s = s.split("-")[0]
        return int(s)
    except (ValueError, TypeError):
        return None


def _one_line_insight(
    metric: str,
    count: int,
    tiers: str,
    year_min: Any,
    year_max: Any,
    has_gap: bool,
) -> str:
    y_range = ""
    if year_min is not None and year_max is not None and not (pd.isna(year_min) or pd.isna(year_max)):
        y_range = f" ({int(year_min)}–{int(year_max)})"
    gap_txt = " [Gap: add evidence]" if has_gap else ""
    return f"{metric}: {count} source(s) from {tiers}{y_range}.{gap_txt}"
