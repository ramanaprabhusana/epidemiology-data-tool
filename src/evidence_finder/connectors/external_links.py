"""
External links connector: for a given indication and country, add stub evidence rows
with direct links to authoritative epidemiology sources (GLOBOCAN, CI5, SEER, WHO, ClinicalTrials.gov).
No API keys required; helps users discover sources they may not know about.
"""

from urllib.parse import quote_plus
from typing import Any, Dict, List

from ..schema import EvidenceRecord

# Curated source URLs (search or landing pages by disease/country)
GLOBOCAN_BASE = "https://gco.iarc.who.int/today/en/dataviz"
CI5_BASE = "https://ci5.iarc.who.int/ci5-xii/tables"
SEER_EXPLORER = "https://seer.cancer.gov/statistics-network/explorer"
WHO_GHO = "https://www.who.int/data/gho/data/indicators"
WHO_DATA_HUB = "https://data.who.int"
CLINICALTRIALS_BASE = "https://clinicaltrials.gov/search"
NCI_CANCER_GOV = "https://www.cancer.gov/about-cancer/understanding/statistics"
CDC_NCHS = "https://www.cdc.gov/nchs"
EUROSTAT = "https://ec.europa.eu/eurostat"


def _search_url(base: str, query: str) -> str:
    """Append query as fragment or query string for sources that support search."""
    q = quote_plus(query)
    if "?" in base:
        return f"{base}&q={q}"
    return f"{base}?q={q}"


def external_links_connector(
    indication: str,
    config: Dict[str, Any],
    country: str = None,
    **kwargs,
) -> List[EvidenceRecord]:
    """
    Create stub evidence records with links to external epidemiology sources
    so users can search for the indication and country. Tier: bronze (discovery).
    """
    country = country or kwargs.get("country") or ""
    indication_clean = (indication or "").strip() or "cancer"
    search_term = f"{indication_clean} {country}".strip()

    records: List[EvidenceRecord] = []

    # GLOBOCAN (IARC) - global cancer incidence/mortality by cancer type and country
    records.append(
        EvidenceRecord(
            indication=indication or "cancer",
            metric="incidence_links",
            value="Search GLOBOCAN for incidence/mortality by country",
            source_citation="IARC GLOBOCAN",
            source_tier="bronze",
            definition="Global Cancer Observatory – incidence, mortality, prevalence by cancer site and country",
            population=None,
            year_or_range=None,
            geography=country or None,
            split_logic=None,
            source_url=GLOBOCAN_BASE,
            notes="Open GLOBOCAN → select cancer type and country for estimates.",
            confidence="high",
        )
    )

    # Cancer Incidence in Five Continents (CI5)
    records.append(
        EvidenceRecord(
            indication=indication or "cancer",
            metric="registry_links",
            value="CI5 registry tables by cancer site and region",
            source_citation="IARC CI5",
            source_tier="bronze",
            definition="Cancer Incidence in Five Continents – registry-level data by site",
            population=None,
            year_or_range=None,
            geography=country or None,
            split_logic=None,
            source_url=CI5_BASE,
            notes="Browse by cancer site (ICD-10) and registry/country.",
            confidence="high",
        )
    )

    # SEER (US only) – suggest when country is US
    if country and country.upper() in ("US", "USA", "UNITED STATES"):
        records.append(
            EvidenceRecord(
                indication=indication or "cancer",
                metric="seer_explorer",
                value="US incidence/trends – use SEER Explorer",
                source_citation="NCI SEER",
                source_tier="gold",
                definition="Surveillance, Epidemiology, and End Results – US cancer statistics",
                population="US",
                year_or_range=None,
                geography="US",
                split_logic=None,
                source_url=SEER_EXPLORER,
                notes="SEER*Explorer: filter by cancer site and demographics.",
                confidence="high",
            )
        )
        records.append(
            EvidenceRecord(
                indication=indication or "cancer",
                metric="nci_statistics",
                value="NCI cancer statistics and understanding",
                source_citation="NCI",
                source_tier="gold",
                definition="National Cancer Institute statistics and data tools",
                population="US",
                year_or_range=None,
                geography="US",
                split_logic=None,
                source_url=NCI_CANCER_GOV,
                notes="Links to SEER, CIS, and other NCI data.",
                confidence="high",
            )
        )

    # WHO GHO
    records.append(
        EvidenceRecord(
            indication=indication or "cancer",
            metric="who_gho",
            value="WHO Global Health Observatory indicators",
            source_citation="WHO GHO",
            source_tier="silver",
            definition="WHO health data by indicator and country",
            population=None,
            year_or_range=None,
            geography=country or None,
            split_logic=None,
            source_url=WHO_GHO,
            notes="Search indicators; filter by country.",
            confidence="medium",
        )
    )

    # WHO Data Hub (new)
    records.append(
        EvidenceRecord(
            indication=indication or "cancer",
            metric="who_data_hub",
            value="WHO World Health Data Hub",
            source_citation="WHO Data Hub",
            source_tier="silver",
            definition="Unified WHO data portal",
            population=None,
            year_or_range=None,
            geography=country or None,
            split_logic=None,
            source_url=WHO_DATA_HUB,
            notes="Browse or search datasets by topic and geography.",
            confidence="medium",
        )
    )

    # ClinicalTrials.gov – trials for condition in country
    ct_url = _search_url(CLINICALTRIALS_BASE, search_term)
    records.append(
        EvidenceRecord(
            indication=indication or "cancer",
            metric="clinical_trials_links",
            value="Search ClinicalTrials.gov for trials in this indication/country",
            source_citation="ClinicalTrials.gov",
            source_tier="bronze",
            definition="Registry of clinical studies – condition and location",
            population=None,
            year_or_range=None,
            geography=country or None,
            split_logic=None,
            source_url=ct_url,
            notes="Filter by condition and country for trial count and links.",
            confidence="low",
        )
    )

    # CDC/NCHS (US)
    if country and country.upper() in ("US", "USA", "UNITED STATES"):
        records.append(
            EvidenceRecord(
                indication=indication or "cancer",
                metric="cdc_nchs",
                value="CDC National Center for Health Statistics",
                source_citation="CDC NCHS",
                source_tier="gold",
                definition="US vital and health statistics",
                population="US",
                year_or_range=None,
                geography="US",
                split_logic=None,
                source_url=CDC_NCHS,
                notes="Data tools and publications by topic.",
                confidence="high",
            )
        )

    # Eurostat (EU countries)
    eu_codes = {"UK", "DE", "FR", "EU5", "EU", "GERMANY", "FRANCE", "UNITED KINGDOM"}
    if country and country.upper() in eu_codes:
        records.append(
            EvidenceRecord(
                indication=indication or "cancer",
                metric="eurostat",
                value="Eurostat health and cause-of-death data",
                source_citation="Eurostat",
                source_tier="silver",
                definition="EU official statistics – health and mortality",
                population=None,
                year_or_range=None,
                geography=country or None,
                split_logic=None,
                source_url=EUROSTAT,
                notes="Search for cancer or cause of death by country.",
                confidence="medium",
            )
        )

    return records


def external_links_connector_factory():
    """Returns a callable(indication, config, **kwargs) -> list[EvidenceRecord]."""
    def _connector(indication: str, config: Dict[str, Any], **kwargs) -> List[EvidenceRecord]:
        return external_links_connector(indication, config, **kwargs)
    return _connector
