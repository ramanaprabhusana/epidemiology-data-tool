"""
Data Builder: take evidence records, apply selected scenario options, produce tool-ready table.
Scenario options can be loaded from config/scenario_options.yaml (config-driven).
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import yaml

from .schema import ScenarioOption, ToolReadyRow


def load_scenario_options(config_path: Path) -> Tuple[List[ScenarioOption], Dict[str, str]]:
    """
    Load scenario options and default selection from YAML.
    Returns (list of ScenarioOption, default_selection dict mapping scenario_type -> option_id).
    If file missing or invalid, returns default in-code options.
    """
    path = Path(config_path)
    if not path.exists():
        opts = [
            ScenarioOption("growth_rate", "seer_trend", "SEER 5-y trend", "Based on SEER trend", "SEER", value_numeric=0.02),
            ScenarioOption("growth_rate", "literature_low", "Literature low", "Conservative growth", "Literature", value_numeric=0.01),
            ScenarioOption("stage_split", "source_a", "Source A distribution", "From registry A", "Registry A"),
        ]
        return opts, {"growth_rate": "seer_trend", "stage_split": "source_a"}
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    types = data.get("scenario_types", {})
    options: List[ScenarioOption] = []
    for scenario_type, items in types.items():
        for item in items or []:
            opt = ScenarioOption(
                scenario_type=scenario_type,
                option_id=item.get("option_id", ""),
                label=item.get("label", ""),
                rationale=item.get("rationale", ""),
                sources=item.get("sources", ""),
                value_numeric=item.get("value_numeric"),
                value_text=item.get("value_text"),
            )
            options.append(opt)
    default = data.get("default_selection", {}) or {"growth_rate": "seer_trend", "stage_split": "source_a"}
    if not options:
        opts = [
            ScenarioOption("growth_rate", "seer_trend", "SEER 5-y trend", "Based on SEER trend", "SEER", value_numeric=0.02),
            ScenarioOption("stage_split", "source_a", "Source A distribution", "From registry A", "Registry A"),
        ]
        return opts, default
    return options, default


def load_evidence_table(path: Path) -> pd.DataFrame:
    """Load evidence table (CSV/Excel) from Evidence Finder output."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path)


def build_scenario_registry(options: list[ScenarioOption], path: Path) -> None:
    """Write scenario options to CSV/Excel for dropdown and audit."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([o.to_row() for o in options])
    df.to_csv(path, index=False)


def build_tool_ready_table(
    evidence_df: pd.DataFrame,
    indication: str,
    selected_scenarios: dict[str, str],
) -> list[ToolReadyRow]:
    """
    Convert evidence DataFrame to tool-ready rows.
    selected_scenarios: e.g. {"growth_rate": "seer_trend", "stage_split": "source_a"}.
    Pilot: simple 1:1 mapping of evidence rows to ToolReadyRow; scenario labels stored on row.
    """
    rows: list[ToolReadyRow] = []
    for _, r in evidence_df.iterrows():
        year = None
        if pd.notna(r.get("year_or_range")):
            try:
                year = int(str(r["year_or_range"]).strip().split("-")[0])
            except (ValueError, TypeError):
                pass
        rows.append(
            ToolReadyRow(
                indication=indication,
                metric=r.get("metric", ""),
                year=year,
                split_type="stage" if r.get("split_logic") else None,
                split_value=r.get("split_logic") if isinstance(r.get("split_logic"), str) else None,
                value=r.get("value", 0),
                scenario_growth_rate=selected_scenarios.get("growth_rate"),
                scenario_stage_split=selected_scenarios.get("stage_split"),
                source=r.get("source_citation", ""),
                notes=r.get("notes"),
            )
        )
    return rows


def export_tool_ready(rows: list[ToolReadyRow], path: Path) -> None:
    """Export tool-ready table to CSV/Excel."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([x.to_row() for x in rows])
    df.to_csv(path, index=False)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df.to_excel(path, index=False)


# --- InsightACE Epidemiology (Beta) aligned export ---
# Matches the Disease Overview table: EPI Parameter (rows) x Year (columns), optional Low/High scenario.

def build_insightace_epidemiology_table(
    rows: list[ToolReadyRow],
    scenario_label: str = "High",
) -> pd.DataFrame:
    """
    Build a wide table for InsightACE Epidemiology (Beta) view:
    - Rows: EPI Parameter (Incidence, Prevalence, Stage I, Stage II, Stage III, etc.)
    - Columns: Sr. No., EPI Parameter, then one column per year (e.g. 2024, 2025, ...)
    - scenario_label: e.g. "Low" or "High" for the scenario toggle in the platform.
    """
    if not rows:
        return pd.DataFrame(columns=["Sr. No.", "EPI Parameter"])

    df = pd.DataFrame([x.to_row() for x in rows])
    # Pivot: (metric + split_value) as EPI Parameter, year as columns
    df["epi_param"] = df.apply(
        lambda r: r["split_value"] if r.get("split_value") else r["metric"],
        axis=1,
    )
    year_vals = df["year"].dropna()
    years = sorted(year_vals.astype(int).unique().tolist()) if len(year_vals) else []
    if not years:
        pivot = df[["epi_param", "value"]].drop_duplicates(subset=["epi_param"]).set_index("epi_param")
        pivot = pivot.rename(columns={"value": "value"})
        pivot = pivot.reset_index()
    else:
        pivot = df.pivot_table(
            index="epi_param",
            columns="year",
            values="value",
            aggfunc="first",
        ).reindex(columns=years)
        pivot = pivot.reset_index()
    pivot = pivot.rename(columns={"epi_param": "EPI Parameter"})
    pivot.insert(0, "Sr. No.", range(1, len(pivot) + 1))
    pivot.columns = [str(c) for c in pivot.columns]
    return pivot


def export_insightace_epidemiology(
    rows: list[ToolReadyRow],
    path: Path,
    scenario_label: str = "High",
) -> None:
    """
    Export epidemiology table in InsightACE Epidemiology (Beta) format.
    Use for ingestion or manual upload to the platform (Disease Overview → Epidemiology).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = build_insightace_epidemiology_table(rows, scenario_label=scenario_label)
    df.to_csv(path, index=False)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df.to_excel(path, index=False)
