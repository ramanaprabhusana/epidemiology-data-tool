"""Tests for pipeline runner (path resolution, run without dashboard)."""
import pytest
import pandas as pd
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pipeline.runner import run_pipeline, _safe_name, _consolidate_csvs_to_excel


def test_safe_name():
    assert _safe_name("CLL") == "CLL"
    assert _safe_name("Lung Cancer") == "Lung_Cancer"
    assert " " not in _safe_name("  a  ") and _safe_name("  a  ")


def test_consolidate_csvs_to_excel(tmp_path):
    """Consolidation writes a single xlsx with one sheet per CSV."""
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    pd.DataFrame({"x": [1, 2]}).to_csv(a, index=False)
    pd.DataFrame({"y": [3, 4]}).to_csv(b, index=False)
    paths = {"evidence": str(a), "source_log": str(b)}
    out = tmp_path / "consolidated.xlsx"
    _consolidate_csvs_to_excel(paths, out)
    assert out.exists()
    xl = pd.ExcelFile(out)
    assert len(xl.sheet_names) == 2
    assert "evidence" in xl.sheet_names
    assert "source_log" in xl.sheet_names


def test_run_pipeline_example_no_dashboard(tmp_path):
    """Run pipeline for Example indication, no dashboard, to a temp output dir."""
    result = run_pipeline(
        indication="Example",
        country=None,
        evidence_path=ROOT / "templates" / "evidence_upload_template.csv",
        config_dir=ROOT / "config",
        output_dir=tmp_path,
        export_dashboard=False,
        include_forecast=False,
        use_pubmed=False,
    )
    assert result["success"] is True
    assert result["record_count"] >= 1
    assert "evidence" in result["paths"]
    assert "kpi" in result["paths"]
    assert (tmp_path / "evidence_Example.csv").exists() or any("evidence" in p for p in result["paths"].values())


def test_run_pipeline_validation_in_result():
    """Pipeline result includes validation_report when validate_evidence=True."""
    from pathlib import Path
    result = run_pipeline(
        indication="CLL",
        country="US",
        config_dir=ROOT / "config",
        output_dir=ROOT / "output",
        export_dashboard=False,
        validate_evidence=True,
        use_pubmed=False,
    )
    assert "validation_report" in result
    assert "validation_passed" in result
