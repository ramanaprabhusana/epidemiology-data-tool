"""
Source connectors for Evidence Finder.
API connectors (PubMed, ClinicalTrials.gov, WHO GHO) are in api_connectors.py.
Web extraction is in web_extractor.py.
Dynamic explorer (explore_all) runs every source listed in config/sources_to_explore.yaml.
"""

from .api_connectors import (
    search_pubmed,
    pubmed_connector,
    pubmed_connector_factory,
    search_clinical_trials,
    clinicaltrials_connector,
    clinicaltrials_connector_factory,
    who_gho_connector,
    who_gho_connector_factory,
)
from .explore_all import (
    load_sources_to_explore,
    explore_all_sources,
    explore_all_connector_factory,
    build_reference_links,
    load_curated_records,
)

__all__ = [
    "search_pubmed",
    "pubmed_connector",
    "pubmed_connector_factory",
    "search_clinical_trials",
    "clinicaltrials_connector",
    "clinicaltrials_connector_factory",
    "load_sources_to_explore",
    "explore_all_sources",
    "explore_all_connector_factory",
    "build_reference_links",
    "load_curated_records",
    "who_gho_connector",
    "who_gho_connector_factory",
]
