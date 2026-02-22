#!/usr/bin/env python3
"""
Pilot example: run Evidence Finder (from manual template) -> Data Builder -> KPI table.
Run from project root:
  python run_pilot_example.py
"""

from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"
OUTPUT = ROOT / "output"
TEMPLATES = ROOT / "templates"

def main():
    from src.evidence_finder.collector import (
        collect_for_indication,
        export_evidence_table,
        write_source_log,
    )
    from src.data_builder.builder import (
        load_evidence_table,
        build_tool_ready_table,
        export_tool_ready,
        export_insightace_epidemiology,
        build_scenario_registry,
    )
    from src.data_builder.schema import ScenarioOption
    from src.repository.kpi_table import build_kpi_table

    indication = "EXAMPLE"
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # 1) Evidence Finder: load from manual template (or future API)
    manual_path = TEMPLATES / "evidence_upload_template.csv"
    records, source_log = collect_for_indication(indication, CONFIG, manual_evidence_path=manual_path)
    evidence_path = OUTPUT / f"evidence_{indication}.csv"
    export_evidence_table(records, evidence_path)
    write_source_log(source_log, OUTPUT / f"source_log_{indication}.csv")
    print(f"Evidence table: {evidence_path} ({len(records)} rows)")

    # 2) Data Builder: scenario options + tool-ready table
    scenario_options = [
        ScenarioOption("growth_rate", "seer_trend", "SEER 5-y trend", "Based on SEER trend", "SEER", value_numeric=0.02),
        ScenarioOption("growth_rate", "literature_low", "Literature low", "Conservative growth", "Literature", value_numeric=0.01),
        ScenarioOption("stage_split", "source_a", "Source A distribution", "From registry A", "Registry A"),
    ]
    build_scenario_registry(scenario_options, OUTPUT / f"scenario_registry_{indication}.csv")

    selected = {"growth_rate": "seer_trend", "stage_split": "source_a"}
    evidence_df = load_evidence_table(evidence_path)
    tool_rows = build_tool_ready_table(evidence_df, indication, selected)
    tool_path = OUTPUT / f"tool_ready_{indication}.csv"
    export_tool_ready(tool_rows, tool_path)
    print(f"Tool-ready table: {tool_path} ({len(tool_rows)} rows)")

    # InsightACE Epidemiology (Beta) format: EPI Parameter x Year
    insightace_path = OUTPUT / f"insightace_epi_{indication}.csv"
    export_insightace_epidemiology(tool_rows, insightace_path, scenario_label="High")
    print(f"InsightACE epidemiology export: {insightace_path}")

    # 3) KPI table
    metrics_config = CONFIG / "required_metrics.yaml"
    kpi_path = OUTPUT / f"kpi_table_{indication}.csv"
    build_kpi_table(indication, evidence_path, metrics_config, kpi_path)
    print(f"KPI table: {kpi_path}")

    print("Done. Check the output/ folder.")


if __name__ == "__main__":
    main()
