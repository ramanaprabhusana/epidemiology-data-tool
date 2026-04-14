"""
Evidence collection: load tier config, collect from sources, output evidence table + source log.
Pilot: manual CSV/Excel input or one API (e.g. PubMed) to prove the flow.
"""

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .schema import EvidenceRecord


def load_source_tiers(config_path: Path) -> dict[str, Any]:
    """Load source_tiers.yaml."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def records_to_dataframe(records: list[EvidenceRecord]) -> pd.DataFrame:
    """Convert evidence records to DataFrame for export."""
    if not records:
        return pd.DataFrame()
    return pd.DataFrame([r.to_row() for r in records])


def export_evidence_table(records: list[EvidenceRecord], path: Path) -> None:
    """Export evidence table to CSV (and optionally Excel)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = records_to_dataframe(records)
    df.to_csv(path, index=False)
    if path.suffix.lower() == ".xlsx" or path.suffix.lower() == ".xls":
        df.to_excel(path, index=False)


def write_source_log(entries: list[dict[str, Any]], path: Path) -> None:
    """Write source log (sources queried, what was found/excluded)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(entries)
    df.to_csv(path, index=False)


def export_evidence_by_metric(evidence_df: pd.DataFrame, path: Path) -> None:
    """
    Group evidence rows by metric and export to CSV.
    Each metric forms a cluster; rows are sorted by metric so all incidence
    data appears together, then prevalence, etc.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if evidence_df.empty:
        evidence_df.to_csv(path, index=False)
        return
    if "metric" not in evidence_df.columns:
        evidence_df.to_csv(path, index=False)
        return
    df = evidence_df.sort_values("metric").reset_index(drop=True)
    df.to_csv(path, index=False)


# Placeholder: collect from one indication (e.g. load from manual CSV for pilot)
def collect_for_indication(
    indication: str,
    config_dir: Path,
    manual_evidence_path: Path | None = None,
) -> tuple[list[EvidenceRecord], list[dict]]:
    """
    For pilot: load config and optionally a manual evidence CSV.
    Later: add API calls (PubMed, SEER, etc.) that append to records and source_log.
    """
    config_path = config_dir / "source_tiers.yaml"
    tiers = load_source_tiers(config_path)
    records: list[EvidenceRecord] = []
    source_log: list[dict] = []

    if manual_evidence_path and manual_evidence_path.exists():
        df = pd.read_csv(manual_evidence_path)
        for _, row in df.iterrows():
            records.append(
                EvidenceRecord(
                    indication=indication,
                    metric=row.get("metric", ""),
                    value=row.get("value", ""),
                    source_citation=row.get("source_citation", ""),
                    source_tier=row.get("source_tier", "silver"),
                    definition=row.get("definition"),
                    population=row.get("population"),
                    year_or_range=str(row.get("year_or_range", "")) if pd.notna(row.get("year_or_range")) else None,
                    geography=row.get("geography"),
                    split_logic=row.get("split_logic"),
                    source_url=row.get("source_url"),
                    notes=row.get("notes"),
                    confidence=row.get("confidence"),
                )
            )
        source_log.append({"source": "manual_upload", "path": str(manual_evidence_path), "rows": len(records)})

    return records, source_log
