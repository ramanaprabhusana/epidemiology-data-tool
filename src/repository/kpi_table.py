"""
KPI-style table: required metrics, coverage, gaps, conflicts, validated vs AI.
Build from evidence table + required_metrics config; write to CSV/Excel.
"""

from pathlib import Path
from typing import Any, List, Optional

import pandas as pd
import yaml


def load_required_metrics(config_path: Path) -> list[dict[str, Any]]:
    """Load required_metrics.yaml for an indication."""
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)
    return data.get("metrics", [])


def compute_coverage(evidence_df: pd.DataFrame, required_metrics: list[dict]) -> list[dict]:
    """
    For each required metric, check if we have at least one evidence row.
    Returns list of {metric_id, label, required, covered, count, gap}.
    """
    if evidence_df.empty:
        metrics_seen = {}
    else:
        metrics_seen = evidence_df.groupby("metric").agg(count=("value", "count")).to_dict()["count"]
    rows = []
    for m in required_metrics:
        mid = m.get("id", "")
        label = m.get("label", mid)
        required = m.get("required", True)
        count = metrics_seen.get(mid, 0)
        covered = count > 0
        rows.append({
            "metric_id": mid,
            "label": label,
            "required": required,
            "covered": covered,
            "evidence_count": count,
            "gap": required and not covered,
        })
    return rows


def compute_conflicts(evidence_df: pd.DataFrame) -> List[dict]:
    """
    Flag conflicts: same metric + same population/year (or same year) but different values.
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


def build_kpi_table(
    indication: str,
    evidence_path: Path,
    required_metrics_path: Path,
    output_path: Path,
    include_conflicts: bool = True,
    conflicts_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Build KPI table (coverage, gaps) and write to output_path. Optionally write conflicts to separate CSV."""
    evidence_path = Path(evidence_path)
    required_metrics_path = Path(required_metrics_path)
    output_path = Path(output_path)
    if evidence_path.suffix.lower() == ".csv":
        evidence_df = pd.read_csv(evidence_path)
    else:
        evidence_df = pd.read_excel(evidence_path)
    required = load_required_metrics(required_metrics_path)
    coverage = compute_coverage(evidence_df, required)
    df = pd.DataFrame(coverage)
    df.insert(0, "indication", indication)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    if include_conflicts:
        conflicts = compute_conflicts(evidence_df)
        if conflicts:
            cdf = pd.DataFrame(conflicts)
            cdf.insert(0, "indication", indication)
            out = Path(conflicts_path) if conflicts_path else output_path.parent / (output_path.stem + "_conflicts.csv")
            out = Path(out)
            out.parent.mkdir(parents=True, exist_ok=True)
            cdf.to_csv(out, index=False)
    return df
