"""
Multi-level source finder: discover and aggregate evidence from multiple sources by tier.
Runs Gold → Silver → Bronze in order; each tier can have multiple sources (manual, API, file).
Designed for extensibility: add new source connectors without changing the tier logic.
"""

from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

import pandas as pd
import yaml

from .schema import EvidenceRecord


# Tier order for multi-level discovery (highest confidence first)
DEFAULT_TIER_ORDER = ("gold", "silver", "bronze")


def load_source_tiers(config_path: Path) -> dict[str, Any]:
    """Load source_tiers.yaml."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_tier_order(tiers_config: dict[str, Any]) -> List[str]:
    """Return ordered list of tier names (gold, silver, bronze by default)."""
    order = list(tiers_config.get("tiers", {}).keys())
    return [t for t in DEFAULT_TIER_ORDER if t in order] or order


class TieredSourceFinder:
    """
    Finds evidence from multiple sources at different levels (tiers).
    - Processes tiers in order: Gold → Silver → Bronze.
    - Each tier can contribute multiple evidence items (from CSV, API, etc.).
    - Aggregates all into one evidence list and a detailed source log.
    """

    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self.tiers_config = load_source_tiers(self.config_path)
        self.tier_order = get_tier_order(self.tiers_config)

    def list_sources_by_tier(self) -> dict[str, list[str]]:
        """Return {tier: [source_name, ...]} for display or logging."""
        tiers = self.tiers_config.get("tiers", {})
        return {
            tier: [s.get("name", "?") for s in tiers.get(tier, {}).get("sources", [])]
            for tier in self.tier_order
        }

    def collect_from_dataframe(
        self,
        indication: str,
        df: pd.DataFrame,
        tier: str,
        source_name: str,
        country_override: Optional[str] = None,
    ) -> List[EvidenceRecord]:
        """Convert a DataFrame (with standard evidence columns) into EvidenceRecords for a given tier/source.
        If country_override is set, geography on each record is set to that (e.g. user-selected country).
        """
        records = []
        for _, row in df.iterrows():
            def _v(k, default=None):
                val = row.get(k, default)
                return None if (val is None or (isinstance(val, float) and pd.isna(val))) else str(val).strip() or None
            geography = (country_override or _v("geography")) or None
            records.append(
                EvidenceRecord(
                    indication=indication,
                    metric=_v("metric") or "",
                    value=row.get("value", ""),
                    source_citation=_v("source_citation") or source_name,
                    source_tier=tier,
                    definition=_v("definition"),
                    population=_v("population"),
                    year_or_range=_v("year_or_range"),
                    geography=geography,
                    split_logic=_v("split_logic"),
                    source_url=_v("source_url"),
                    notes=_v("notes"),
                    confidence=_v("confidence"),
                )
            )
        return records

    def run(
        self,
        indication: str,
        manual_evidence_path: Optional[Path] = None,
        source_connectors: Optional[dict[str, Callable[..., List[EvidenceRecord]]]] = None,
        country: Optional[str] = None,
        connector_kwargs: Optional[dict] = None,
    ) -> Tuple[List[EvidenceRecord], List[dict]]:
        """
        Run multi-level discovery: for each tier (gold → silver → bronze), gather evidence
        from manual upload and any registered connectors. Returns (all_records, source_log).
        source_connectors: optional dict mapping "tier:source_name" to a callable(indication, config, **kwargs) -> list[EvidenceRecord].
        connector_kwargs: optional dict passed to each connector (e.g. country=...).
        """
        all_records: List[EvidenceRecord] = []
        source_log: List[dict] = []

        # 1) Load manual evidence once (CSV): each row can have source_tier or default to gold
        if manual_evidence_path and Path(manual_evidence_path).exists():
            try:
                df = pd.read_csv(manual_evidence_path)
            except Exception:
                df = pd.DataFrame()
            if not df.empty:
                if "source_tier" in df.columns:
                    tier_col = df["source_tier"].astype(str).str.lower().str.strip().fillna("")
                    for tier in self.tier_order:
                        sub = df[tier_col == tier]
                        if not sub.empty:
                            recs = self.collect_from_dataframe(indication, sub, tier, "manual_upload", country_override=country)
                            all_records.extend(recs)
                            source_log.append({"tier": tier, "source": "manual_upload", "path": str(manual_evidence_path), "rows": len(recs)})
                else:
                    recs = self.collect_from_dataframe(indication, df, self.tier_order[0], "manual_upload", country_override=country)
                    all_records.extend(recs)
                    source_log.append({"tier": self.tier_order[0], "source": "manual_upload", "path": str(manual_evidence_path), "rows": len(recs)})

        # 2) Run optional connectors per tier/source (e.g. APIs)
        if source_connectors:
            tier_sources = self.tiers_config.get("tiers", {})
            for tier in self.tier_order:
                for src in tier_sources.get(tier, {}).get("sources", []):
                    name = src.get("name", "?")
                    key = f"{tier}:{name}"
                    if key in source_connectors:
                        try:
                            kwargs = dict(connector_kwargs or {})
                            recs = source_connectors[key](indication, self.tiers_config, **kwargs)
                            all_records.extend(recs)
                            source_log.append({"tier": tier, "source": name, "rows": len(recs), "status": "ok"})
                        except Exception as e:
                            source_log.append({"tier": tier, "source": name, "rows": 0, "status": "error", "error": str(e)})

        return all_records, source_log


def collect_from_multiple_levels(
    indication: str,
    config_dir: Path,
    manual_evidence_path: Optional[Path] = None,
    connectors: Optional[dict] = None,
    country: Optional[str] = None,
    connector_kwargs: Optional[dict] = None,
) -> Tuple[List[EvidenceRecord], List[dict]]:
    """
    Convenience: run TieredSourceFinder and return (records, source_log).
    If country is provided, evidence records are tagged with that geography.
    connector_kwargs (e.g. {"country": country}) is passed to each connector.
    """
    config_path = config_dir / "source_tiers.yaml"
    finder = TieredSourceFinder(config_path)
    kwargs = dict(connector_kwargs or {})
    if country is not None and "country" not in kwargs:
        kwargs["country"] = country
    return finder.run(
        indication,
        manual_evidence_path=manual_evidence_path,
        source_connectors=connectors,
        country=country,
        connector_kwargs=kwargs or None,
    )
