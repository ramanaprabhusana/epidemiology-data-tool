"""
Standalone pipeline for epidemiology evidence.
Share this file with your teammate along with the notebook.
No config files or project structure needed: provide an evidence CSV and run.

Usage:
    from pipeline_standalone import run_pipeline_standalone
    result = run_pipeline_standalone(
        indication="CLL",
        country="US",
        evidence_csv_path="evidence.csv",
        output_dir="./output",
    )
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

# Dependencies: pandas only. Install with: pip install pandas openpyxl


# --- Default metrics (used when no config) ---
DEFAULT_REQUIRED_METRICS = [
    {"id": "incidence", "label": "Incidence", "required": True},
    {"id": "prevalence", "label": "Prevalence", "required": True},
    {"id": "diagnosed_prevalence", "label": "Diagnosed prevalence", "required": False},
    {"id": "stage_distribution", "label": "Stage distribution", "required": True},
]

# --- Minimal evidence CSV template ---
EVIDENCE_TEMPLATE_CSV = """indication,metric,value,source_citation,source_tier,definition,population,year_or_range,geography,split_logic,source_url,notes,confidence
CLL,incidence,21000,SEER Stat Fact,gold,New cases per year,US adults,2019,US,,https://seer.cancer.gov,,high
CLL,prevalence,200000,CDC estimate,silver,Point prevalence,US,2018-2019,US,,,Reconciled with SEER,medium
"""


def _safe_name(s: str) -> str:
    return s.replace(" ", "_").replace(",", "").strip() or "unknown"


def _add_year_column(df: pd.DataFrame) -> pd.DataFrame:
    """Parse year from year_or_range; add year column."""
    if df is None or df.empty:
        return df
    if "year_or_range" not in df.columns:
        df = df.copy()
        df["year"] = pd.NA
        return df

    def parse_year(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        s = str(val).strip()
        if not s:
            return None
        try:
            for part in s.replace("-", " ").split():
                if len(part) >= 4 and part[:4].isdigit():
                    return int(part[:4])
        except (ValueError, TypeError):
            pass
        return None

    out = df.copy()
    out["year"] = df["year_or_range"].apply(parse_year)
    cols = list(out.columns)
    if "year_or_range" in cols and "year" in cols:
        cols.remove("year")
        idx = cols.index("year_or_range") + 1
        cols.insert(idx, "year")
        out = out[cols]
    return out


def _is_stub_value(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    s = str(value).strip().lower()
    return "see link" in s or s == "" or s == "nan"


def _extract_first_numeric(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s or _is_stub_value(value):
        return None
    s_clean = re.sub(r"\s*\([^)]*\)\s*", " ", s)
    match = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+\.\d+|\d+)", s_clean.replace(" ", ""))
    if not match:
        return None
    try:
        num = float(match.group(1).replace(",", ""))
        if 1e-2 <= num <= 1e8 or (0 < num < 1e-2 and "." in match.group(1)):
            return num
        if 1900 <= num <= 2030:
            return None
        return num
    except (ValueError, TypeError):
        return None


def _tier_rank(tier: Any) -> int:
    t = str(tier).strip().lower() if tier and not (isinstance(tier, float) and pd.isna(tier)) else "bronze"
    return 0 if t == "gold" else (1 if t == "silver" else 2)


def _tier_score(source_tier: Any) -> int:
    weights = {"gold": 35, "silver": 22, "bronze": 15}
    if source_tier is None or (isinstance(source_tier, float) and pd.isna(source_tier)):
        return 15
    t = str(source_tier).strip().lower()
    return weights.get(t, 15)


def _completeness_score(row: Union[Dict, pd.Series]) -> int:
    total = 0
    for field in ["definition", "year_or_range", "geography", "population"]:
        val = row.get(field, None) if hasattr(row, "get") else getattr(row, field, None)
        if val is not None and not (isinstance(val, float) and pd.isna(val)):
            s = str(val).strip()
            if s and s.lower() not in ("nan", ""):
                total += 6
    return min(total, 25)


def _recency_score(row: Union[Dict, pd.Series], current_year: int = 2025) -> int:
    yr = row.get("year_or_range", None) if hasattr(row, "get") else getattr(row, "year_or_range", None)
    if yr is None or (isinstance(yr, float) and pd.isna(yr)):
        return 0
    s = str(yr).strip()
    if not s:
        return 0
    match = re.search(r"20\d{2}|19\d{2}", s)
    if not match:
        return 0
    y = int(match.group(0))
    if y >= current_year - 1:
        return 5
    if y >= current_year - 5:
        return 3
    return 0


def compute_confidence_score(row: Union[Dict, pd.Series]) -> int:
    tier_pts = _tier_score(row.get("source_tier") if hasattr(row, "get") else getattr(row, "source_tier", None))
    value = row.get("value") if hasattr(row, "get") else getattr(row, "value", None)
    ext_pts = 30 if not _is_stub_value(value) else 0
    comp_pts = _completeness_score(row)
    rec_pts = _recency_score(row)
    return min(100, max(0, tier_pts + ext_pts + comp_pts + rec_pts))


def get_confidence_label(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def add_computed_confidence(evidence_df: pd.DataFrame) -> pd.DataFrame:
    if evidence_df.empty:
        evidence_df = evidence_df.copy()
        evidence_df["computed_confidence_score"] = []
        evidence_df["computed_confidence"] = []
        return evidence_df
    evidence_df = evidence_df.copy()
    scores = evidence_df.apply(compute_confidence_score, axis=1)
    evidence_df["computed_confidence_score"] = scores
    evidence_df["computed_confidence"] = scores.apply(get_confidence_label)
    return evidence_df


def compute_conflicts(evidence_df: pd.DataFrame) -> List[dict]:
    if evidence_df.empty or len(evidence_df) < 2:
        return []
    df = evidence_df.copy()
    df["year_or_range"] = df["year_or_range"].fillna("").astype(str).str.strip() if "year_or_range" in df.columns else ""
    df["population"] = df["population"].fillna("").astype(str).str.strip() if "population" in df.columns else ""
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
        })
    return conflicts


def _agreement_within_pct(values: List[float], pct: float = 20.0) -> Tuple[bool, str]:
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
    required_metrics: List[Dict],
    indication: str = "",
) -> pd.DataFrame:
    rows = []
    conf_col = "computed_confidence" if "computed_confidence" in evidence_df.columns else "confidence"
    for m in required_metrics:
        mid = m.get("id", "")
        label = m.get("label", mid)
        required = m.get("required", True)
        sub = evidence_df[evidence_df["metric"] == mid] if "metric" in evidence_df.columns else pd.DataFrame()
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
        numeric_list = []
        for _, r in sub.iterrows():
            num = _extract_first_numeric(r.get("value"))
            if num is not None:
                numeric_list.append((num, str(r.get("source_citation", "")), _tier_rank(r.get("source_tier"))))
        n_with_value = len(numeric_list)
        if not numeric_list:
            rows.append({
                "indication": indication,
                "metric_id": mid,
                "label": label,
                "required": required,
                "best_value": "",
                "best_source": sub.iloc[0]["source_citation"] if len(sub) else "",
                "range_min": "", "range_max": "",
                "n_sources": n_sources,
                "n_with_value": n_with_value,
                "agreement_flag": "no numeric values",
                "validation_status": "Needs review" if n_sources > 0 else "No source",
            })
            continue
        numeric_list.sort(key=lambda x: (x[2], -x[0]))
        best_value = numeric_list[0][0]
        best_source = numeric_list[0][1]
        vals = [x[0] for x in numeric_list]
        agree, agreement_flag = _agreement_within_pct(vals)
        has_high_conf = False
        if conf_col in evidence_df.columns:
            sub_conf = evidence_df[evidence_df["metric"] == mid]
            if not sub_conf.empty:
                has_high_conf = (sub_conf[conf_col].astype(str).str.lower() == "high").any()
        has_gold = any(x[2] == 0 for x in numeric_list)
        validation_status = "Ready" if (agree and (has_high_conf or has_gold)) else "Needs review"
        rows.append({
            "indication": indication,
            "metric_id": mid,
            "label": label,
            "required": required,
            "best_value": best_value,
            "best_source": best_source,
            "range_min": min(vals),
            "range_max": max(vals),
            "n_sources": n_sources,
            "n_with_value": n_with_value,
            "agreement_flag": agreement_flag,
            "validation_status": validation_status,
        })
    return pd.DataFrame(rows)


def build_tool_ready_table(evidence_df: pd.DataFrame, indication: str) -> pd.DataFrame:
    rows = []
    for _, r in evidence_df.iterrows():
        year = None
        if pd.notna(r.get("year_or_range")):
            try:
                year = int(str(r["year_or_range"]).strip().split("-")[0])
            except (ValueError, TypeError):
                pass
        rows.append({
            "indication": indication,
            "metric": r.get("metric", ""),
            "year": year,
            "split_type": "stage" if r.get("split_logic") else "",
            "split_value": r.get("split_logic") if isinstance(r.get("split_logic"), str) else "",
            "value": r.get("value", 0),
            "source": r.get("source_citation", ""),
            "notes": r.get("notes", ""),
        })
    return pd.DataFrame(rows)


def build_insightace_table(tool_ready_df: pd.DataFrame) -> pd.DataFrame:
    if tool_ready_df.empty:
        return pd.DataFrame(columns=["Sr. No.", "EPI Parameter"])
    df = tool_ready_df.copy()
    df["epi_param"] = df.apply(
        lambda r: r["split_value"] if r.get("split_value") else r["metric"],
        axis=1,
    )
    year_vals = df["year"].dropna()
    years = sorted(year_vals.astype(int).unique().tolist()) if len(year_vals) else []
    if not years:
        pivot = df[["epi_param", "value"]].drop_duplicates(subset=["epi_param"]).set_index("epi_param").reset_index()
        pivot = pivot.rename(columns={"epi_param": "EPI Parameter"})
    else:
        pivot = df.pivot_table(index="epi_param", columns="year", values="value", aggfunc="first").reindex(columns=years)
        pivot = pivot.reset_index()
        pivot = pivot.rename(columns={"epi_param": "EPI Parameter"})
    pivot.insert(0, "Sr. No.", range(1, len(pivot) + 1))
    pivot.columns = [str(c) for c in pivot.columns]
    return pivot


def run_pipeline_standalone(
    indication: str,
    country: str,
    evidence_csv_path: str,
    output_dir: str = "./output",
    required_metrics: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Run the pipeline using only an evidence CSV. No config files or project structure needed.

    Args:
        indication: Disease/indication (e.g. CLL, Lung Cancer).
        country: Geography (e.g. US, UK).
        evidence_csv_path: Path to evidence CSV with columns: indication, metric, value,
            source_citation, source_tier, definition, population, year_or_range, geography,
            split_logic, source_url, notes, confidence.
        output_dir: Where to write output files.
        required_metrics: Optional list of {id, label, required}; uses default if None.

    Returns:
        Dict with success, message, paths, evidence_df, kpi_df, tool_ready_df, record_count.
    """
    output_dir = Path(output_dir)
    evidence_path = Path(evidence_csv_path)
    if not evidence_path.exists():
        return {
            "success": False,
            "message": f"Evidence file not found: {evidence_path}",
            "paths": {},
            "evidence_df": None,
            "kpi_df": None,
            "tool_ready_df": None,
            "record_count": 0,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    ind_safe = _safe_name(indication)
    country_safe = _safe_name(country)
    file_suffix = f"{ind_safe}_{country_safe}".rstrip("_")

    try:
        evidence_df = pd.read_csv(evidence_path)
        if evidence_df.empty:
            return {
                "success": False,
                "message": "Evidence CSV is empty.",
                "paths": {},
                "evidence_df": evidence_df,
                "kpi_df": None,
                "tool_ready_df": None,
                "record_count": 0,
            }

        # Tag geography if provided
        if country:
            evidence_df = evidence_df.copy()
            evidence_df["geography"] = evidence_df.get("geography", pd.Series()).fillna(country)

        evidence_df = _add_year_column(evidence_df)
        evidence_df = add_computed_confidence(evidence_df)
        evidence_df_sorted = evidence_df.sort_values("metric").reset_index(drop=True) if "metric" in evidence_df.columns else evidence_df

        # Export evidence
        evidence_out = output_dir / f"evidence_by_metric_{file_suffix}.csv"
        evidence_df_sorted.to_csv(evidence_out, index=False)

        # Tool-ready
        tool_ready_df = build_tool_ready_table(evidence_df, indication)
        tool_path = output_dir / f"tool_ready_{file_suffix}.csv"
        tool_ready_df.to_csv(tool_path, index=False)

        # InsightACE export
        insightace_df = build_insightace_table(tool_ready_df)
        insightace_path = output_dir / f"insightace_epi_{file_suffix}.csv"
        insightace_df.to_csv(insightace_path, index=False)

        # Conflicts
        conflicts = compute_conflicts(evidence_df)
        if conflicts:
            cdf = pd.DataFrame(conflicts)
            cdf.insert(0, "indication", indication)
            conflicts_path = output_dir / f"kpi_conflicts_{file_suffix}.csv"
            cdf.to_csv(conflicts_path, index=False)

        # KPI scorecard
        metrics = required_metrics if required_metrics else DEFAULT_REQUIRED_METRICS
        scorecard_df = build_kpi_scorecard(evidence_df, metrics, indication=indication)
        scorecard_path = output_dir / f"kpi_scorecard_{file_suffix}.csv"
        scorecard_df.to_csv(scorecard_path, index=False)

        return {
            "success": True,
            "message": f"Pipeline complete. {len(evidence_df)} evidence rows; outputs in {output_dir}",
            "paths": {
                "evidence": str(evidence_out),
                "tool_ready": str(tool_path),
                "insightace_epi": str(insightace_path),
                "kpi_scorecard": str(scorecard_path),
            },
            "evidence_df": evidence_df,
            "kpi_df": scorecard_df,
            "tool_ready_df": tool_ready_df,
            "record_count": len(evidence_df),
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Pipeline error: {e}",
            "paths": {},
            "evidence_df": None,
            "kpi_df": None,
            "tool_ready_df": None,
            "record_count": 0,
        }


def write_template_evidence(path: str = "evidence_template.csv") -> None:
    """Write a minimal evidence CSV template for the teammate to fill in."""
    Path(path).write_text(EVIDENCE_TEMPLATE_CSV, encoding="utf-8")
