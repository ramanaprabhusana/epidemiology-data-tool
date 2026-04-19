"""
Dynamic source explorer: load sources from config/sources_to_explore.yaml and explore every
configured source for the chosen indication and country. Link-type sources produce one stub
evidence row per source; api-type sources call the registered connector (e.g. clinicaltrials, pubmed).
Add or remove sources in the YAML to change what the tool explores (no code change).
"""

from pathlib import Path
from urllib.parse import quote_plus
from typing import Any, Dict, List
import time

import yaml

from ..schema import EvidenceRecord
from ..indication_context import (
    curated_slug_candidates,
    pubmed_expanded_queries,
    trial_search_conditions,
)


def _bundled_pipeline_config_dir() -> Path:
    """config/ at pipeline root (parent of src/)."""
    return Path(__file__).resolve().parents[3] / "config"


def load_curated_records(config_dir: Path, indication: str, country: str) -> List[EvidenceRecord]:
    """
    Load curated epidemiology data from config/curated_data/{indication_slug}.yaml.
    Returns high-quality EvidenceRecord instances with gold tier and real numeric values.
    This is the primary data source — far more reliable than web scraping.
    """
    # Map long UI labels to curated_data/{slug}.yaml (e.g. NHL -> nhl.yaml)
    candidates = curated_slug_candidates(indication or "")
    roots = [Path(config_dir)]
    bundled = _bundled_pipeline_config_dir()
    if bundled.resolve() != Path(config_dir).resolve():
        roots.append(bundled)

    curated_path = None
    for root in roots:
        for slug in candidates:
            p = root / "curated_data" / f"{slug}.yaml"
            if p.exists():
                curated_path = p
                break
        if curated_path is not None:
            break
    if curated_path is None:
        return []

    try:
        with open(curated_path, "r") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return []

    metrics = data.get("metrics", {})
    if not isinstance(metrics, dict):
        return []

    records = []
    for metric_id, info in metrics.items():
        if not isinstance(info, dict):
            continue
        # Allow all curated data through — global/regional context is valuable
        # The category and geography columns let users filter downstream
        # Strip year suffix from metric ID: "incidence_2024" -> metric="incidence", year=2024
        import re as _re
        _year_suffix = _re.search(r"_(\d{4})$", metric_id)
        clean_metric = metric_id[:_year_suffix.start()] if _year_suffix else metric_id
        year_val = _year_suffix.group(1) if _year_suffix else str(info.get("year", ""))
        # If YAML already has a year field, prefer it over the suffix
        if info.get("year"):
            year_val = str(info["year"])
        rec = EvidenceRecord(
            indication=indication or data.get("indication", ""),
            metric=clean_metric,
            value=str(info.get("value", "")),
            source_citation=info.get("source_citation", "Curated reference"),
            source_tier=info.get("tier", "gold"),
            definition=info.get("definition", ""),
            population=info.get("population"),
            year_or_range=year_val,
            geography=info.get("geography", country or ""),
            split_logic=None,
            source_url=info.get("source_url", ""),
            notes=f"Curated reference value ({info.get('unit', '')})",
            confidence=info.get("confidence", "high"),
            category=info.get("category", ""),
        )
        records.append(rec)
    return records

# Registry of API connector factories: connector_id -> (lambda **kwargs -> callable(indication, config, **kwargs))
def _get_registry():
    from .api_connectors import clinicaltrials_connector_factory, pubmed_connector_factory, who_gho_connector_factory
    return {
        "clinicaltrials": lambda **kw: clinicaltrials_connector_factory(),
        "pubmed": lambda **kw: pubmed_connector_factory(
            create_stub_evidence=kw.get("add_pubmed_stubs", True),
        ),
        "who_gho": lambda **kw: who_gho_connector_factory(),
    }


def _apply_placeholders(url: str, indication: str, country: str) -> str:
    indication = (indication or "").strip()
    country = (country or "").strip()
    return url.replace("{indication}", indication).replace("{country}", country).replace(
        "{indication_encoded}", quote_plus(indication)
    ).replace("{country_encoded}", quote_plus(country))


def _country_matches_filter(country: str, country_filter: List[str]) -> bool:
    if not country_filter:
        return True
    c = (country or "").strip().lower()
    return any((f or "").strip().lower() == c for f in country_filter)


def load_sources_to_explore(config_dir: Path) -> List[Dict[str, Any]]:
    """Load and return the list of sources from config/sources_to_explore.yaml."""
    path = config_dir / "sources_to_explore.yaml"
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return data.get("sources") or []
    except Exception:
        return []


def explore_all_sources(
    indication: str,
    config: Dict[str, Any],
    country: str = None,
    config_dir: Path = None,
    use_pubmed: bool = True,
    add_pubmed_stubs: bool = True,
    **kwargs,
) -> List[EvidenceRecord]:
    """
    Explore every source listed in config/sources_to_explore.yaml for this indication and country.
    - type=link: build URL from template, apply country_filter, create one stub EvidenceRecord.
    - type=api: if enabled (and enabled_when satisfied), call the registered connector and extend records.
    """
    country = country or kwargs.get("country") or ""
    indication_clean = (indication or "").strip() or "cancer"
    display_indication = indication_clean
    api_kwargs = dict(kwargs)
    api_kwargs["indication_display"] = display_indication
    api_kwargs["trial_conditions"] = trial_search_conditions(display_indication)
    api_kwargs["pubmed_queries"] = pubmed_expanded_queries(display_indication, country)

    if config_dir is None:
        config_dir = _bundled_pipeline_config_dir()
    config_dir = Path(config_dir)
    sources = load_sources_to_explore(config_dir)
    # Process link sources by extract_priority (1 first, then 2, then rest) so high-value sources get deep-dive before time cap
    def _source_order(s: dict) -> tuple:
        if s.get("type") != "link":
            return (1, 0)  # API sources after link sources
        return (0, int(s.get("extract_priority") or 99))
    sources = sorted(sources, key=_source_order)
    all_records: List[EvidenceRecord] = []
    registry = _get_registry()
    link_records_added = 0  # for deep-dive limit

    # PHASE 0: Load curated data first — this is the most reliable source.
    curated_records = load_curated_records(config_dir, indication_clean, country)
    all_records.extend(curated_records)
    curated_metrics = {r.metric for r in curated_records}

    # Set indication context for the web extractor so it filters
    # for indication-specific data (e.g., only CLL numbers, not all-cancer).
    try:
        from .web_extractor import set_indication_context
        set_indication_context(indication_clean)
    except Exception:
        pass

    # Cap total run time (e.g. 30 min) so we never run indefinitely
    max_run_seconds = kwargs.get("max_run_seconds")
    run_deadline = None  # float timestamp or None
    if max_run_seconds is not None and max_run_seconds > 0:
        run_deadline = time.time() + max_run_seconds

    for src in sources:
        if not isinstance(src, dict):
            continue
        src_id = src.get("id") or src.get("name") or "unknown"
        tier = (src.get("tier") or "bronze").lower()
        name = src.get("name") or src_id

        # Optional: skip this source if enabled_when is not satisfied
        enabled_when = src.get("enabled_when")
        if enabled_when:
            if enabled_when == "use_pubmed" and not use_pubmed:
                continue
            if enabled_when in kwargs and not kwargs.get(enabled_when):
                continue

        # Link-type sources: add one evidence row per source; then deep-dive into the URL to extract values when possible.
        if src.get("type") == "link":
            country_filter = src.get("country_filter")
            if isinstance(country_filter, str):
                country_filter = [country_filter]
            if not _country_matches_filter(country, country_filter or []):
                continue
            url_raw = src.get("url") or ""
            url = _apply_placeholders(url_raw, indication_clean, country)
            stub_value = "See link for incidence, prevalence, and KPIs"
            # Determine proper metric label: use the configured metric, or
            # infer from the extracted value labels. Fallback to source ID
            # only if the source is a reference link (no data extracted).
            configured_metric = src.get("metric") or ""
            # If metric is just the source id (e.g. "aacr", "bmj"), it's not
            # a real epidemiology metric — use a descriptive label instead.
            valid_metrics = {"incidence", "prevalence", "mortality", "survival",
                           "incidence_rate", "prevalence_rate", "cases", "link",
                           "clinical_trials_count", "literature_count",
                           "life_expectancy_at_birth"}
            if configured_metric and configured_metric.lower() in valid_metrics:
                metric_label = configured_metric
            else:
                metric_label = f"{src_id}_links"

            rec = EvidenceRecord(
                indication=display_indication or "cancer",
                metric=metric_label,
                value=stub_value,
                source_citation=name,
                source_tier=tier,
                definition=src.get("definition"),
                population=None,
                year_or_range=None,
                geography=country or None,
                split_logic=None,
                source_url=url,
                notes=src.get("notes"),
                confidence=src.get("confidence", "medium"),
            )
            all_records.append(rec)
            link_records_added += 1
            # Web extraction: single-page extraction per source (no recursive link following)
            # Skip if we're past the run-time cap or if curated data already covers this metric
            deep_dive_links = kwargs.get("deep_dive_links", True)
            max_deep_dive = int(kwargs.get("max_deep_dive_links", 100))
            if run_deadline is not None and time.time() >= run_deadline:
                rec.notes = (rec.notes or "") + " [Skipped: time limit]"
            elif metric_label in curated_metrics:
                rec.notes = (rec.notes or "") + " [Skipped: curated value available]"
            elif deep_dive_links and url and link_records_added <= max_deep_dive:
                try:
                    from .web_extractor import deep_dive_link_record
                    extracted = deep_dive_link_record(
                        url, delay=True, indication=indication_clean, country=country, deadline=run_deadline
                    )
                    if extracted and len(str(extracted).strip()) > 0:
                        rec.value = extracted
                        rec.notes = (rec.notes or "") + " [Value extracted]"
                    else:
                        rec.notes = (rec.notes or "") + " [No datapoints found]"
                except Exception:
                    rec.notes = (rec.notes or "") + " [Extraction error]"
            continue
        if src.get("type") == "api":
            connector_id = src.get("connector_id")
            if not connector_id or connector_id not in registry:
                continue
            try:
                factory = registry[connector_id]
                connector = factory(
                    **api_kwargs,
                    add_pubmed_stubs=add_pubmed_stubs,
                    use_pubmed=use_pubmed,
                )
                # api_kwargs already includes country; do not pass country twice (breaks PubMed connector).
                recs = connector(indication_clean, config, **api_kwargs)
                all_records.extend(recs)
            except Exception:
                pass
    return all_records


def explore_all_connector_factory():
    """Returns a callable(indication, config, **kwargs) that explores all configured sources (API-only for evidence; links go to reference_links)."""
    def _connector(indication: str, config: Dict[str, Any], **kwargs) -> List[EvidenceRecord]:
        return explore_all_sources(indication, config, **kwargs)
    return _connector


def build_reference_links(
    config_dir: Path,
    indication: str,
    country: str,
) -> List[Dict[str, str]]:
    """
    Build list of {source_name, url, metric} for all link-type sources in sources_to_explore.yaml.
    Used to write reference_links CSV (no extracted value; user can open these to find data).
    """
    sources = load_sources_to_explore(config_dir)
    indication_clean = (indication or "").strip() or "cancer"
    out: List[Dict[str, str]] = []
    for src in sources:
        if not isinstance(src, dict) or src.get("type") != "link":
            continue
        country_filter = src.get("country_filter")
        if isinstance(country_filter, str):
            country_filter = [country_filter]
        if not _country_matches_filter(country, country_filter or []):
            continue
        name = src.get("name") or src.get("id") or "?"
        url_raw = src.get("url") or ""
        url = _apply_placeholders(url_raw, indication_clean, country)
        out.append({
            "source_name": name,
            "metric": src.get("metric") or "link",
            "url": url,
            "definition": (src.get("definition") or "")[:200],
        })
    return out
