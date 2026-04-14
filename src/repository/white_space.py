"""
White-space analysis: coverage matrix and one-page summary.
Identifies gaps where metrics × geography/year have no or weak evidence (stub only / missing).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from ..utils import is_stub_value as _is_stub_value


def build_coverage_matrix(
    evidence_df: pd.DataFrame,
    required_metrics: List[Dict[str, Any]],
    indication: str = "",
    geography: str = "",
) -> pd.DataFrame:
    """
    One row per required metric; columns: metric_id, label, coverage_status, n_sources, n_with_value, n_stub_only, source_list.
    coverage_status: "Has value" | "Stub only" | "Missing".
    """
    if evidence_df.empty:
        metrics_seen = {}
        metrics_with_value = {}
        metrics_stub = {}
        sources_by_metric = {}
    else:
        metrics_seen = evidence_df.groupby("metric").agg(
            n_sources=("source_citation", "nunique"),
            n_rows=("value", "count"),
        ).to_dict("index")
        _with_val = evidence_df[~evidence_df["value"].apply(_is_stub_value)].groupby("metric")
        with_value = _with_val.agg(
            n_with_value=("value", "count"),
        ).to_dict("index")
        def _first_10_sources(x):
            u = sorted(x.unique().astype(str))[:10]
            return "; ".join(u) if u else ""
        sources_by_metric_agg = _with_val["source_citation"].apply(_first_10_sources).to_dict()
        for k in with_value:
            with_value[k]["sources"] = sources_by_metric_agg.get(k, "")
        stub_only = evidence_df[evidence_df["value"].apply(_is_stub_value)].groupby("metric").agg(
            n_stub=("value", "count"),
        ).to_dict("index")
        metrics_with_value = {k: v["n_with_value"] for k, v in with_value.items()}
        metrics_stub = {k: v["n_stub"] for k, v in stub_only.items()}
        sources_by_metric = {k: v.get("sources", "") for k, v in with_value.items()}

    rows = []
    for m in required_metrics:
        mid = m.get("id", "")
        label = m.get("label", mid)
        n_sources = metrics_seen.get(mid, {}).get("n_sources", 0) or 0
        n_with = metrics_with_value.get(mid, 0)
        n_stub = metrics_stub.get(mid, 0)
        if n_with > 0:
            coverage_status = "Has value"
        elif n_stub > 0 or n_sources > 0:
            coverage_status = "Stub only"
        else:
            coverage_status = "Missing"
        rows.append({
            "indication": indication,
            "geography": geography,
            "metric_id": mid,
            "label": label,
            "coverage_status": coverage_status,
            "n_sources": n_sources,
            "n_with_value": n_with,
            "n_stub_only": n_stub,
            "source_list": sources_by_metric.get(mid, "")[:500],
        })
    return pd.DataFrame(rows)


def build_white_space_summary(
    coverage_df: pd.DataFrame,
    indication: str = "",
    geography: str = "",
) -> str:
    """
    One-page narrative summary: which metrics are covered, which have limited sources, which need reconciliation.
    """
    lines = [
        f"# White-space summary: {indication or 'All indications'} {geography or ''}",
        "",
        "## Coverage by metric",
        "",
    ]
    has_value = coverage_df[coverage_df["coverage_status"] == "Has value"]
    stub_only = coverage_df[coverage_df["coverage_status"] == "Stub only"]
    missing = coverage_df[coverage_df["coverage_status"] == "Missing"]

    if not has_value.empty:
        lines.append("**Covered (at least one extracted value):**")
        for _, r in has_value.iterrows():
            lines.append(f"- {r['label']} ({r['metric_id']}): {r['n_sources']} source(s), {r['n_with_value']} with value.")
        lines.append("")
    if not stub_only.empty:
        lines.append("**Stub only (link available, no datapoint extracted):**")
        for _, r in stub_only.iterrows():
            lines.append(f"- {r['label']} ({r['metric_id']}): {r['n_sources']} source(s). Consider manual lookup or improve extraction.")
        lines.append("")
    if not missing.empty:
        lines.append("**Missing (no source in evidence):**")
        for _, r in missing.iterrows():
            lines.append(f"- {r['label']} ({r['metric_id']}).")
        lines.append("")

    # One-paragraph executive summary
    n_covered = len(has_value)
    n_stub = len(stub_only)
    n_miss = len(missing)
    total = len(coverage_df)
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"Of {total} required/optional metrics: {n_covered} have at least one extracted value; "
        f"{n_stub} have only stub (See link) and may need manual entry or improved extraction; "
        f"{n_miss} have no source in the current evidence run."
    )
    if n_stub > 0 or n_miss > 0:
        lines.append("These gaps represent white-space: high-value areas to add sources or extraction for.")
    return "\n".join(lines)


def export_white_space(
    coverage_df: pd.DataFrame,
    summary_text: str,
    output_dir: Path,
    file_suffix: str = "",
) -> None:
    """Write white-space summary markdown only (coverage matrix omitted to reduce file count)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base = f"white_space_{file_suffix}" if file_suffix else "white_space"
    (output_dir / f"{base}_summary.md").write_text(summary_text, encoding="utf-8")
