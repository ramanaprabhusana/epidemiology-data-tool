"""
Reconciliation view: for each metric with multiple source values, show value by source, range, recommended value, note.
Supports "assumption-clear" and "validate, reconcile, standardize" from project plan.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..utils import is_stub_value as _is_stub_value, extract_first_numeric as _extract_first_numeric, tier_rank as _tier_rank


def build_reconciliation_table(
    evidence_df: pd.DataFrame,
    required_metrics: List[Dict[str, Any]],
    indication: str = "",
    geography: str = "",
    prefer_tier: str = "gold",
) -> pd.DataFrame:
    """
    One row per (metric, geography, year_or_range) that has multiple distinct numeric values;
    columns: metric_id, label, geography, year_or_range, value_by_source, range_min, range_max, recommended_value, recommended_source, note.
    recommended_value: from highest-tier source with a numeric value, or median if tie.
    """
    if evidence_df.empty:
        return pd.DataFrame(columns=[
            "indication", "geography", "metric_id", "label", "year_or_range",
            "value_by_source", "range_min", "range_max", "recommended_value", "recommended_source", "note",
        ])
    rows = []
    for m in required_metrics:
        mid = m.get("id", "")
        label = m.get("label", mid)
        sub = evidence_df[evidence_df["metric"] == mid]
        if sub.empty or len(sub) < 2:
            continue
        # Group by year_or_range (and optionally geography) to find conflicts
        sub = sub.copy()
        sub["year_or_range"] = sub.get("year_or_range", "").fillna("").astype(str)
        sub["geography"] = sub.get("geography", "").fillna("").astype(str)
        sub["_num"] = sub["value"].apply(_extract_first_numeric)
        sub = sub.dropna(subset=["_num"])
        if len(sub) < 2:
            continue
        sub["_tier_rank"] = sub["source_tier"].apply(_tier_rank)
        for (year_or_range, geo), grp in sub.groupby(["year_or_range", "geography"]):
            if len(grp) < 2:
                continue
            vals = grp["_num"].tolist()
            if len(set(round(v, 4) for v in vals)) < 2:
                continue
            value_by_source = "; ".join(
                f"{row['source_citation']}: {row['_num']}" for _, row in grp.iterrows()
            )
            range_min = min(vals)
            range_max = max(vals)
            # Recommended: best tier, then first by tier order
            grp_sorted = grp.sort_values("_tier_rank")
            rec_row = grp_sorted.iloc[0]
            recommended_value = rec_row["_num"]
            recommended_source = rec_row["source_citation"]
            note = f"Prefer {prefer_tier} when available; used {recommended_source}. Range {range_min}–{range_max} from {len(grp)} sources."
            rows.append({
                "indication": indication,
                "geography": geography or (rec_row.get("geography") or ""),
                "metric_id": mid,
                "label": label,
                "year_or_range": year_or_range or "",
                "value_by_source": value_by_source[:1000],
                "range_min": range_min,
                "range_max": range_max,
                "recommended_value": recommended_value,
                "recommended_source": recommended_source,
                "note": note,
            })
    return pd.DataFrame(rows)


def export_reconciliation(df: pd.DataFrame, output_path: Path, also_excel: bool = False) -> None:
    """Write reconciliation table to CSV and optionally Excel."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    if also_excel and not df.empty:
        df.to_excel(output_path.with_suffix(".xlsx"), index=False)


def compute_conflicts(evidence_df: pd.DataFrame) -> List[dict]:
    """
    Flag conflicts: same metric + same population/year but different values.
    Returns list of {metric, year_or_range, population, value_1, value_2, source_1, source_2, conflict_note}.
    """
    if evidence_df.empty or len(evidence_df) < 2:
        return []
    df = evidence_df.copy()
    df["year_or_range"] = df.get("year_or_range", "").fillna("").astype(str).str.strip()
    df["population"] = df.get("population", "").fillna("").astype(str).str.strip()
    conflicts = []
    for (metric, yr, pop), grp in df.groupby(["metric", "year_or_range", "population"]):
        if len(grp) < 2:
            continue
        vals = grp["value"].astype(str).str.strip()
        if vals.nunique() < 2:
            continue
        uniq = vals.unique().tolist()
        sources = grp["source_citation"].fillna("").astype(str).tolist()
        conflicts.append({
            "metric": metric,
            "year_or_range": yr or "(blank)",
            "population": pop or "(blank)",
            "value_1": uniq[0],
            "value_2": uniq[1] if len(uniq) > 1 else "",
            "source_1": sources[0] if sources else "",
            "source_2": sources[1] if len(sources) > 1 else "",
            "conflict_note": f"Different values for same metric/year/population: {uniq[0]} vs {uniq[1]}",
        })
    return conflicts
