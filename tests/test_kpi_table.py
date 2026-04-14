"""Tests for KPI scorecard and conflict detection (migrated from kpi_table tests)."""
import pandas as pd
import pytest
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.repository.scorecard import load_required_metrics
from src.repository.reconciliation import compute_conflicts


def test_compute_conflicts_empty():
    df = pd.DataFrame([{"metric": "incidence", "value": 100, "year_or_range": "2019", "population": "US", "source_citation": "A"}])
    conflicts = compute_conflicts(df)
    assert len(conflicts) == 0


def test_compute_conflicts_two_values():
    df = pd.DataFrame([
        {"metric": "incidence", "value": 100, "year_or_range": "2019", "population": "US", "source_citation": "A"},
        {"metric": "incidence", "value": 120, "year_or_range": "2019", "population": "US", "source_citation": "B"},
    ])
    conflicts = compute_conflicts(df)
    assert len(conflicts) == 1
    assert conflicts[0]["value_1"] == "100" or conflicts[0]["value_2"] == "120"
    assert "conflict_note" in conflicts[0]


def test_load_required_metrics(tmp_path):
    metrics_config = tmp_path / "metrics.yaml"
    metrics_config.write_text("metrics:\n  - id: incidence\n    label: Incidence\n    required: true\n")
    metrics = load_required_metrics(metrics_config)
    assert len(metrics) == 1
    assert metrics[0]["id"] == "incidence"
