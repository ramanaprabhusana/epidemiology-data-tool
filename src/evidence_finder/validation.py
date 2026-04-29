"""
Evidence validation: schema check and validation report for evidence CSV/DataFrame.
Used before or during pipeline run to catch missing columns, invalid tiers, and data issues.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

REQUIRED_COLUMNS = {"indication", "metric", "value", "source_citation", "source_tier"}
VALID_TIERS = {"gold", "silver", "bronze"}
OPTIONAL_COLUMNS = {
    "definition", "population", "year_or_range", "geography",
    "split_logic", "source_url", "notes", "confidence",
    "cluster", "cluster_label", "full_name",  # added by clustering pipeline step
}

# Required columns for the bi_data export layer (evidence_data.csv + cluster columns)
BI_DATA_REQUIRED_COLUMNS = {
    "indication", "metric", "value", "source_citation", "source_tier",
    "cluster", "cluster_label",
}


def validate_evidence_df(df: pd.DataFrame) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validate an evidence DataFrame. Returns (is_valid, report_entries).
    Each report entry: {"level": "error"|"warning", "code": str, "message": str, "row": int|None}.
    """
    report: List[Dict[str, Any]] = []
    is_valid = True

    if df is None or df.empty:
        report.append({"level": "warning", "code": "empty", "message": "Evidence table is empty.", "row": None})
        return True, report  # empty is allowed (no rows to validate)

    # Required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        report.append({
            "level": "error",
            "code": "missing_columns",
            "message": f"Missing required columns: {sorted(missing)}. Required: {sorted(REQUIRED_COLUMNS)}.",
            "row": None,
        })
        is_valid = False

    # Tier values
    if "source_tier" in df.columns:
        tiers = df["source_tier"].astype(str).str.lower().str.strip()
        invalid = set(tiers.unique()) - VALID_TIERS - {""}
        invalid = {t for t in invalid if pd.notna(t) and t}
        if invalid:
            report.append({
                "level": "error",
                "code": "invalid_tier",
                "message": f"Invalid source_tier values: {sorted(invalid)}. Valid: {sorted(VALID_TIERS)}.",
                "row": None,
            })
            is_valid = False

    # Empty required fields (warning per row)
    for col in ["metric", "value", "source_citation"]:
        if col not in df.columns:
            continue
        empty = df[col].isna() | (df[col].astype(str).str.strip() == "")
        if empty.any():
            rows = df.index[empty].tolist()[:5]
            report.append({
                "level": "warning",
                "code": f"empty_{col}",
                "message": f"Rows with empty '{col}': {len(empty)} (e.g. rows {rows}).",
                "row": rows[0] if rows else None,
            })

    # Duplicate key (metric + year_or_range + geography): warning
    key_cols = [c for c in ["metric", "year_or_range", "geography"] if c in df.columns]
    if len(key_cols) >= 2:
        dupes = df.duplicated(subset=key_cols, keep=False)
        if dupes.any():
            report.append({
                "level": "warning",
                "code": "duplicate_key",
                "message": f"Duplicate metric/year/geography combinations: {dupes.sum()} rows. Consider consolidating.",
                "row": None,
            })

    return is_valid, report


def validate_bi_data_df(df: pd.DataFrame) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Validate the bi_data export schema (evidence_data.csv after clustering).
    Checks that cluster / cluster_label columns are present and sufficiently populated.
    Returns (is_valid, report_entries).
    """
    report: List[Dict[str, Any]] = []
    is_valid = True

    if df is None or df.empty:
        report.append({"level": "warning", "code": "empty", "message": "BI_Data table is empty.", "row": None})
        return True, report

    # Required bi_data columns
    missing = BI_DATA_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        report.append({
            "level": "error",
            "code": "missing_bi_columns",
            "message": f"BI_Data missing required columns: {sorted(missing)}",
            "row": None,
        })
        is_valid = False

    # Cluster fill-rate check — warn if >20% null (clustering should cover ~94%+)
    for col in ("cluster", "cluster_label"):
        if col in df.columns:
            null_pct = df[col].isna().mean() * 100
            if null_pct > 20:
                report.append({
                    "level": "warning",
                    "code": f"low_{col}_coverage",
                    "message": (
                        f"'{col}' is {null_pct:.1f}% null — expected <20% after clustering. "
                        "Re-run pipeline or check metric_clusters.yaml coverage."
                    ),
                    "row": None,
                })

    if not report:
        report.append({
            "level": "info",
            "code": "ok",
            "message": "BI_Data schema check passed.",
            "row": None,
        })

    return is_valid, report


def validate_evidence_file(path: Path) -> Tuple[bool, List[Dict[str, Any]]]:
    """Load CSV/Excel and run validate_evidence_df. Returns (is_valid, report)."""
    path = Path(path)
    if not path.exists():
        return False, [{"level": "error", "code": "file_missing", "message": f"File not found: {path}", "row": None}]
    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)
    except Exception as e:
        return False, [{"level": "error", "code": "read_error", "message": str(e), "row": None}]
    return validate_evidence_df(df)


def validation_report_to_df(report: List[Dict[str, Any]]) -> pd.DataFrame:
    """Turn report list into a DataFrame for display or export."""
    if not report:
        return pd.DataFrame(columns=["level", "code", "message", "row"])
    return pd.DataFrame(report)


def export_validation_report(
    report: List[Dict[str, Any]],
    output_dir: Path,
    file_suffix: str,
) -> Path:
    """
    Write validation report to CSV (audit trail).
    Returns csv_path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"validation_report_{file_suffix}.csv"
    df = validation_report_to_df(report)
    df.to_csv(csv_path, index=False)
    return csv_path
