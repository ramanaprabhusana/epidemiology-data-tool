#!/usr/bin/env python3
"""
Full pipeline: multi-level source finder -> Data Builder -> KPI -> Forecast -> Insights
-> Dashboard layer (CSV + optional SQLite) for Tableau / Power BI.
Run from project root: python run_full_pipeline_with_dashboard.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"
OUTPUT = ROOT / "output"
DASHBOARD_DIR = OUTPUT / "dashboard"
TEMPLATES = ROOT / "templates"


def main():
    import pandas as pd
    from src.evidence_finder.sources import collect_from_multiple_levels
    from src.evidence_finder.collector import export_evidence_table, write_source_log, records_to_dataframe
    from src.data_builder.builder import (
        load_evidence_table,
        build_tool_ready_table,
        export_tool_ready,
        export_insightace_epidemiology,
        build_scenario_registry,
        build_insightace_epidemiology_table,
    )
    from src.data_builder.schema import ScenarioOption
    from src.repository.kpi_table import build_kpi_table
    from src.analytics.forecast import build_forecast_table
    from src.analytics.insights import build_insights_summary
    from src.dashboard.export import export_dashboard_layer

    indication = "EXAMPLE"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Multi-level source finder (Gold -> Silver -> Bronze)
    manual_path = TEMPLATES / "evidence_upload_template.csv"
    records, source_log = collect_from_multiple_levels(indication, CONFIG, manual_evidence_path=manual_path)
    evidence_path = OUTPUT / f"evidence_{indication}.csv"
    export_evidence_table(records, evidence_path)
    source_log_path = OUTPUT / f"source_log_{indication}.csv"
    write_source_log(source_log, source_log_path)
    print(f"Multi-level evidence: {evidence_path} ({len(records)} rows)")

    # 2) Data Builder
    scenario_options = [
        ScenarioOption("growth_rate", "seer_trend", "SEER 5-y trend", "Based on SEER trend", "SEER", value_numeric=0.02),
        ScenarioOption("growth_rate", "literature_low", "Literature low", "Conservative growth", "Literature", value_numeric=0.01),
        ScenarioOption("stage_split", "source_a", "Source A distribution", "From registry A", "Registry A"),
    ]
    build_scenario_registry(scenario_options, OUTPUT / f"scenario_registry_{indication}.csv")
    selected = {"growth_rate": "seer_trend", "stage_split": "source_a"}
    evidence_df = load_evidence_table(evidence_path)
    tool_rows = build_tool_ready_table(evidence_df, indication, selected)
    export_tool_ready(tool_rows, OUTPUT / f"tool_ready_{indication}.csv")
    insightace_path = OUTPUT / f"insightace_epi_{indication}.csv"
    export_insightace_epidemiology(tool_rows, insightace_path, scenario_label="High")
    print(f"Tool-ready + InsightACE export: {insightace_path}")

    # 3) KPI table
    metrics_config = CONFIG / "required_metrics.yaml"
    kpi_path = OUTPUT / f"kpi_table_{indication}.csv"
    build_kpi_table(indication, evidence_path, metrics_config, kpi_path)
    kpi_df = pd.read_csv(kpi_path)
    print(f"KPI table: {kpi_path}")

    # 4) Forecast and insights
    forecast_df = build_forecast_table(evidence_df, indication, years_ahead=5)
    forecast_path = OUTPUT / f"forecast_{indication}.csv"
    forecast_df.to_csv(forecast_path, index=False)
    print(f"Forecast: {forecast_path} ({len(forecast_df)} rows)")

    evidence_df_for_insights = pd.read_csv(evidence_path)
    insights_df = build_insights_summary(evidence_df_for_insights, kpi_df=kpi_df, indication=indication)
    insights_path = OUTPUT / f"insights_summary_{indication}.csv"
    insights_df.to_csv(insights_path, index=False)
    print(f"Insights summary: {insights_path}")

    # 5) Dashboard layer for Tableau / Power BI
    tool_ready_df = pd.DataFrame([r.to_row() for r in tool_rows])
    insightace_epi_df = build_insightace_epidemiology_table(tool_rows, scenario_label="High")
    scenario_registry_df = pd.DataFrame([o.to_row() for o in scenario_options])
    source_log_df = pd.read_csv(source_log_path)

    paths = export_dashboard_layer(
        DASHBOARD_DIR,
        evidence_df=evidence_df_for_insights,
        tool_ready_df=tool_ready_df,
        kpi_df=kpi_df,
        scenario_registry_df=scenario_registry_df,
        insightace_epi_df=insightace_epi_df,
        source_log_df=source_log_df,
        forecast_df=forecast_df,
        insights_summary_df=insights_df,
        export_csv=True,
        export_sqlite=True,
        sqlite_db_name="epidemiology_dashboard.db",
    )
    print(f"Dashboard layer: {DASHBOARD_DIR}")
    print(f"  CSV tables: evidence, tool_ready, kpi, scenario_registry, insightace_epi, source_log, forecast, insights_summary")
    if "_sqlite" in paths:
        print(f"  SQLite: {paths['_sqlite']}")
    print("Done. Connect Tableau or Power BI to output/dashboard/ (CSV or .db).")


if __name__ == "__main__":
    main()
