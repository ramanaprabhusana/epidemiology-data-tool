"""
KPI scorecard: per-metric coverage, best value, agreement, validation readiness.
Builds on evidence table + required_metrics; outputs one row per metric with
best_value, source, range_min, range_max, n_sources, agreement_flag, validation_status.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml

from ..utils import is_stub_value as _is_stub_value, extract_first_numeric as _extract_first_numeric, tier_rank as _tier_rank


def load_required_metrics(config_path: Path) -> list[dict[str, Any]]:
    """Load required_metrics.yaml for an indication."""
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)
    return data.get("metrics", [])


def _agreement_within_pct(values: List[float], pct: float = 20.0) -> Tuple[bool, str]:
    """
    Check if values agree within pct% (relative to median).
    Returns (agree, description e.g. "3 of 3 agree" or "2 of 3 agree; 1 outlier").
    """
    if len(values) < 2:
        return True, f"{len(values)} source(s)"
    vals = sorted(values)
    med = vals[len(vals) // 2]
    if med == 0:
        return all(v == 0 for v in vals), f"{len(values)} source(s)"
    within = [v for v in vals if abs(v - med) / med <= pct / 100.0]
    n_agree = len(within)
    if n_agree == len(vals):
        return True, f"{n_agree} of {len(vals)} agree"
    return False, f"{n_agree} of {len(vals)} agree; {len(vals) - n_agree} outlier(s)"


def build_kpi_scorecard(
    evidence_df: pd.DataFrame,
    required_metrics: List[Dict[str, Any]],
    indication: str = "",
    agreement_pct: float = 20.0,
) -> pd.DataFrame:
    """
    Build one row per required metric with:
    metric_id, label, required, best_value, best_source, range_min, range_max,
    n_sources, n_with_value, agreement_flag, validation_status.
    Uses evidence_df columns computed_confidence or confidence if present for validation_status.
    """
    if evidence_df.empty:
        rows = []
        for m in required_metrics:
            rows.append({
                "indication": indication,
                "metric_id": m.get("id", ""),
                "label": m.get("label", m.get("id", "")),
                "required": m.get("required", True),
                "best_value": "",
                "best_source": "",
                "range_min": "",
                "range_max": "",
                "n_sources": 0,
                "n_with_value": 0,
                "agreement_flag": "no data",
                "validation_status": "No source",
            })
        return pd.DataFrame(rows)

    conf_col = "computed_confidence" if "computed_confidence" in evidence_df.columns else ("confidence" if "confidence" in evidence_df.columns else None)

    rows = []
    for m in required_metrics:
        mid = m.get("id", "")
        label = m.get("label", mid)
        required = m.get("required", True)
        sub = evidence_df[evidence_df["metric"] == mid]
        if sub.empty:
            # Fallback: try evidence_ids aliases defined in required_metrics config
            evidence_ids = m.get("evidence_ids", [])
            if evidence_ids:
                sub = evidence_df[evidence_df["metric"].isin(evidence_ids)]
        if sub.empty:
            rows.append({
                "indication": indication,
                "metric_id": mid,
                "label": label,
                "required": required,
                "best_value": "",
                "best_source": "",
                "range_min": "",
                "range_max": "",
                "n_sources": 0,
                "n_with_value": 0,
                "agreement_flag": "no data",
                "validation_status": "No source",
            })
            continue

        n_sources = sub["source_citation"].nunique()
        # Numeric values: (value, source, tier)
        numeric_list: List[Tuple[float, str, int]] = []
        for _, r in sub.iterrows():
            num = _extract_first_numeric(r.get("value"))
            if num is not None:
                numeric_list.append((num, str(r.get("source_citation", "")), _tier_rank(r.get("source_tier"))))
        n_with_value = len(numeric_list)

        if not numeric_list:
            best_value = ""
            best_source = sub.iloc[0]["source_citation"] if len(sub) else ""
            range_min = ""
            range_max = ""
            agree, agreement_flag = False, "no numeric values"
            validation_status = "Needs review" if n_sources > 0 else "No source"
        else:
            # Best: prefer gold, then first numeric
            numeric_list.sort(key=lambda x: (x[2], -x[0]))  # tier asc, then value desc
            best_value = numeric_list[0][0]
            best_source = numeric_list[0][1]
            vals = [x[0] for x in numeric_list]
            range_min = min(vals)
            range_max = max(vals)
            agree, agreement_flag = _agreement_within_pct(vals, pct=agreement_pct)

            # Validation status
            has_high_conf = False
            if conf_col and conf_col in evidence_df.columns:
                sub_conf = evidence_df[evidence_df["metric"] == mid]
                if not sub_conf.empty:
                    has_high_conf = (sub_conf[conf_col].astype(str).str.lower() == "high").any()
            has_gold = any(x[2] == 0 for x in numeric_list)
            if n_sources == 0:
                validation_status = "No source"
            elif agree and (has_high_conf or has_gold):
                validation_status = "Ready"
            elif not agree or n_with_value == 0:
                validation_status = "Needs review"
            else:
                validation_status = "Needs review"
        rows.append({
            "indication": indication,
            "metric_id": mid,
            "label": label,
            "required": required,
            "best_value": best_value if isinstance(best_value, (int, float)) else best_value,
            "best_source": best_source,
            "range_min": range_min if numeric_list else "",
            "range_max": range_max if numeric_list else "",
            "n_sources": n_sources,
            "n_with_value": n_with_value,
            "agreement_flag": agreement_flag,
            "validation_status": validation_status,
        })
    return pd.DataFrame(rows)


def export_kpi_scorecard(
    scorecard_df: pd.DataFrame,
    output_path: Path,
    also_excel: bool = False,
) -> None:
    """Write KPI scorecard to CSV and optionally Excel."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scorecard_df.to_csv(output_path, index=False)
    if also_excel:
        excel_path = output_path.with_suffix(".xlsx")
        scorecard_df.to_excel(excel_path, index=False)
