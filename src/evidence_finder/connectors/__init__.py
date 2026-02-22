"""
Source connectors for Evidence Finder (e.g. PubMed, external links, ClinicalTrials.gov).
Each connector returns list[EvidenceRecord] for a given indication (and optional config, country).
Dynamic explorer (explore_all) runs every source listed in config/sources_to_explore.yaml.
"""

from .pubmed import search_pubmed, pubmed_connector, pubmed_connector_factory
from .external_links import external_links_connector, external_links_connector_factory
from .clinicaltrials import (
    search_clinical_trials,
    clinicaltrials_connector,
    clinicaltrials_connector_factory,
)
from .explore_all import (
    load_sources_to_explore,
    explore_all_sources,
    explore_all_connector_factory,
    build_reference_links,
)
from .who_gho import who_gho_connector, who_gho_connector_factory

__all__ = [
    "search_pubmed",
    "pubmed_connector",
    "pubmed_connector_factory",
    "external_links_connector",
    "external_links_connector_factory",
    "search_clinical_trials",
    "clinicaltrials_connector",
    "clinicaltrials_connector_factory",
    "load_sources_to_explore",
    "explore_all_sources",
    "explore_all_connector_factory",
    "build_reference_links",
    "who_gho_connector",
    "who_gho_connector_factory",
]
