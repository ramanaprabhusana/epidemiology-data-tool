"""Curated slug resolution for long UI labels and common variants."""

from pathlib import Path

import pytest

from src.evidence_finder.indication_context import (
    curated_slug_candidates,
    pubmed_expanded_queries,
    trial_search_conditions,
)
from src.evidence_finder.connectors.explore_all import load_curated_records


@pytest.mark.parametrize(
    "label,expected_first_slug",
    [
        ("Non-Hodgkin Lymphoma (excl. DLBCL)", "nhl"),
        ("Non-Hodgkin Lymphoma (NHL)", "nhl"),
        ("Non\u2013Hodgkin Lymphoma (excl. DLBCL)", "nhl"),
        ("Non Hogdkin Lymphoma", "nhl"),
        ("NHL (excl. DLBCL)", "nhl"),
    ],
)
def test_nhl_curated_slug_first(label: str, expected_first_slug: str) -> None:
    c = curated_slug_candidates(label)
    assert c[0] == expected_first_slug


def test_load_curated_fallback_wrong_config_dir(tmp_path: Path) -> None:
    """If primary config_dir has no curated_data, still load bundled nhl.yaml."""
    empty_cfg = tmp_path / "config"
    empty_cfg.mkdir()
    (empty_cfg / "sources_to_explore.yaml").write_text("sources: []\n", encoding="utf-8")
    recs = load_curated_records(empty_cfg, "Non-Hodgkin Lymphoma (excl. DLBCL)", "US")
    assert len(recs) >= 20
    metrics = {r.metric for r in recs}
    # Metric names updated to SEER-enriched keys (incidence_rate_YYYY / mortality_rate_YYYY)
    assert any(m.startswith("incidence_rate_") or m.startswith("mortality_rate_") for m in metrics)


def test_trial_search_nhl_unicode_dash() -> None:
    conds = trial_search_conditions("Non\u2013Hodgkin lymphoma")
    assert "NHL" in conds


def test_pubmed_nhl_excl_workbook_label() -> None:
    qs = pubmed_expanded_queries("Non-Hodgkin Lymphoma (excl. DLBCL)", None)
    assert any("non-hodgkin" in q.lower() for q in qs)
