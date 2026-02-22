"""
Export a consistent set of tables for Tableau / Power BI connection.
All tables go to one folder (and optionally one SQLite DB) so dashboards can point to a single location.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


# Standard table names for BI tools (easy to document and refresh)
EVIDENCE_TABLE = "evidence"
EVIDENCE_BY_METRIC_TABLE = "evidence_by_metric"
TOOL_READY_TABLE = "tool_ready"
KPI_TABLE = "kpi"
SCENARIO_REGISTRY_TABLE = "scenario_registry"
INSIGHTACE_EPI_TABLE = "insightace_epi"
SOURCE_LOG_TABLE = "source_log"
FORECAST_TABLE = "forecast"
INSIGHTS_SUMMARY_TABLE = "insights_summary"


def get_dashboard_table_names() -> List[str]:
    """Return ordered list of dashboard table names for documentation."""
    return [
        EVIDENCE_TABLE,
        EVIDENCE_BY_METRIC_TABLE,
        TOOL_READY_TABLE,
        KPI_TABLE,
        SCENARIO_REGISTRY_TABLE,
        INSIGHTACE_EPI_TABLE,
        SOURCE_LOG_TABLE,
        FORECAST_TABLE,
        INSIGHTS_SUMMARY_TABLE,
    ]


def export_dashboard_layer(
    output_dir: Path,
    evidence_df: Optional[pd.DataFrame] = None,
    evidence_by_metric_df: Optional[pd.DataFrame] = None,
    tool_ready_df: Optional[pd.DataFrame] = None,
    kpi_df: Optional[pd.DataFrame] = None,
    scenario_registry_df: Optional[pd.DataFrame] = None,
    insightace_epi_df: Optional[pd.DataFrame] = None,
    source_log_df: Optional[pd.DataFrame] = None,
    forecast_df: Optional[pd.DataFrame] = None,
    insights_summary_df: Optional[pd.DataFrame] = None,
    export_csv: bool = True,
    export_excel: bool = False,
    export_sqlite: bool = False,
    sqlite_db_name: str = "epidemiology_dashboard.db",
) -> Dict[str, Path]:
    """
    Write all provided DataFrames to output_dir with fixed names for BI tools.
    Returns dict of table_name -> path to CSV (or Excel if chosen).
    If export_sqlite=True, also writes all tables into one SQLite DB in output_dir.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # evidence_by_metric: evidence sorted by metric (clustered view for BI)
    _evidence_by_metric = evidence_by_metric_df
    if _evidence_by_metric is None and evidence_df is not None and not evidence_df.empty and "metric" in evidence_df.columns:
        _evidence_by_metric = evidence_df.sort_values("metric").reset_index(drop=True)
    tables: Dict[str, Optional[pd.DataFrame]] = {
        EVIDENCE_TABLE: evidence_df,
        EVIDENCE_BY_METRIC_TABLE: _evidence_by_metric,
        TOOL_READY_TABLE: tool_ready_df,
        KPI_TABLE: kpi_df,
        SCENARIO_REGISTRY_TABLE: scenario_registry_df,
        INSIGHTACE_EPI_TABLE: insightace_epi_df,
        SOURCE_LOG_TABLE: source_log_df,
        FORECAST_TABLE: forecast_df,
        INSIGHTS_SUMMARY_TABLE: insights_summary_df,
    }

    paths: Dict[str, Path] = {}
    for name, df in tables.items():
        if df is None or df.empty:
            continue
        if export_csv:
            p = output_dir / f"{name}.csv"
            df.to_csv(p, index=False)
            paths[name] = p
        if export_excel:
            px = output_dir / f"{name}.xlsx"
            df.to_excel(px, index=False)
            if name not in paths:
                paths[name] = px

    if export_sqlite:
        import sqlite3
        db_path = output_dir / sqlite_db_name
        conn = sqlite3.connect(str(db_path))
        try:
            for name, df in tables.items():
                if df is not None and not df.empty:
                    df.to_sql(name, conn, if_exists="replace", index=False)
        finally:
            conn.close()
        paths["_sqlite"] = db_path

    # Data dictionary and manifest for BI users
    manifest_rows = []
    dict_rows = []
    for name, df in tables.items():
        if df is None or df.empty:
            continue
        manifest_rows.append({
            "table_name": name,
            "row_count": len(df),
            "columns": ", ".join(df.columns.astype(str).tolist()),
            "file_csv": f"{name}.csv",
        })
        for col in df.columns:
            dict_rows.append({
                "table_name": name,
                "column_name": str(col),
                "dtype": str(df[col].dtype),
            })
    if manifest_rows:
        pd.DataFrame(manifest_rows).to_csv(output_dir / "manifest.csv", index=False)
    if dict_rows:
        pd.DataFrame(dict_rows).to_csv(output_dir / "data_dictionary.csv", index=False)

    return paths
