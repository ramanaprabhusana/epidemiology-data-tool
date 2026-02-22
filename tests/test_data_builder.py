"""Tests for Data Builder (scenario options from YAML, tool-ready build)."""
import pandas as pd
import pytest
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data_builder.builder import load_scenario_options, build_tool_ready_table, load_evidence_table


def test_load_scenario_options_from_yaml():
    path = ROOT / "config" / "scenario_options.yaml"
    if path.exists():
        options, default = load_scenario_options(path)
        assert len(options) >= 2
        assert "growth_rate" in default or "stage_split" in default
        types = {o.scenario_type for o in options}
        assert "growth_rate" in types or "stage_split" in types


def test_load_scenario_options_missing_file(tmp_path):
    options, default = load_scenario_options(tmp_path / "nonexistent.yaml")
    assert len(options) >= 1
    assert default.get("growth_rate") or default.get("stage_split")


def test_build_tool_ready_table():
    df = pd.DataFrame([
        {"metric": "incidence", "value": 100, "year_or_range": "2019", "source_citation": "SEER", "split_logic": None}
    ])
    rows = build_tool_ready_table(df, "CLL", {"growth_rate": "seer_trend", "stage_split": "source_a"})
    assert len(rows) == 1
    assert rows[0].indication == "CLL"
    assert rows[0].metric == "incidence"
