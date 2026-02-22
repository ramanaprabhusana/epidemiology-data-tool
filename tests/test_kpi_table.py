"""Tests for KPI table and conflict detection."""
import pandas as pd
import pytest
from pathlib import Path
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.repository.kpi_table import (
    load_required_metrics,
    compute_coverage,
    compute_conflicts,
    build_kpi_table,
)


def test_compute_coverage_empty():
    df = pd.DataFrame()
    required = [{"id": "incidence", "label": "Incidence", "required": True}]
    rows = compute_coverage(df, required)
    assert len(rows) == 1
    assert rows[0]["metric_id"] == "incidence"
    assert rows[0]["covered"] is False
    assert rows[0]["gap"] is True


def test_compute_coverage_covered():
    df = pd.DataFrame([{"metric": "incidence", "value": 100}])
    required = [{"id": "incidence", "label": "Incidence", "required": True}]
    rows = compute_coverage(df, required)
    assert rows[0]["covered"] is True
    assert rows[0]["gap"] is False
    assert rows[0]["evidence_count"] == 1


def test_compute_conflicts_empty():
    df = pd.DataFrame([{"metric": "incidence", "value": 100, "year_or_range": "2019", "population": "US"}])
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


def test_build_kpi_table(tmp_path):
    evidence = tmp_path / "evidence.csv"
    pd.DataFrame([
        {"indication": "X", "metric": "incidence", "value": 1, "source_citation": "Y", "source_tier": "gold"}
    ]).to_csv(evidence, index=False)
    metrics_config = tmp_path / "metrics.yaml"
    metrics_config.write_text("metrics:\n  - id: incidence\n    label: Incidence\n    required: true\n")
    out = tmp_path / "kpi.csv"
    build_kpi_table("X", evidence, metrics_config, out, include_conflicts=False)
    assert out.exists()
    df = pd.read_csv(out)
    assert "indication" in df.columns
    assert "metric_id" in df.columns
    assert len(df) >= 1
