"""Tests for evidence validation."""
import pandas as pd
import pytest
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evidence_finder.validation import validate_evidence_df, validate_evidence_file, VALID_TIERS, REQUIRED_COLUMNS


def test_validate_empty_df():
    ok, report = validate_evidence_df(pd.DataFrame())
    assert ok is True
    assert any(e.get("code") == "empty" for e in report)


def test_validate_missing_columns():
    df = pd.DataFrame([{"metric": "incidence", "value": 1}])  # missing indication, source_citation, source_tier
    ok, report = validate_evidence_df(df)
    assert ok is False
    assert any(e.get("code") == "missing_columns" for e in report)


def test_validate_invalid_tier():
    df = pd.DataFrame([
        {"indication": "X", "metric": "incidence", "value": 1, "source_citation": "Y", "source_tier": "platinum"}
    ])
    ok, report = validate_evidence_df(df)
    assert ok is False
    assert any(e.get("code") == "invalid_tier" for e in report)


def test_validate_ok():
    df = pd.DataFrame([
        {"indication": "CLL", "metric": "incidence", "value": 100, "source_citation": "SEER", "source_tier": "gold"}
    ])
    ok, report = validate_evidence_df(df)
    assert ok is True
    assert not any(e.get("level") == "error" for e in report)


def test_validate_file_missing():
    ok, report = validate_evidence_file(Path("/nonexistent/file.csv"))
    assert ok is False
    assert any(e.get("code") == "file_missing" for e in report)


def test_validate_file_exists():
    path = ROOT / "templates" / "evidence_cll.csv"
    if path.exists():
        ok, report = validate_evidence_file(path)
        assert ok is True
