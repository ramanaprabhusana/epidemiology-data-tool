"""
API-based evidence connectors: PubMed, ClinicalTrials.gov, WHO GHO.
Merged from individual connector files for simplicity.
Each connector returns List[EvidenceRecord] and has a factory function for the source registry.
"""

import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlencode

import requests

from ..schema import EvidenceRecord

# ============================================================
# PubMed (NCBI) connector
# ============================================================

NCBI_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


def search_pubmed(term: str, retmax: int = 20, retmode: str = "json") -> Dict[str, Any]:
    """Run a PubMed search. Returns dict with pmids, count, query_translation, error."""
    params = {"db": "pubmed", "term": term, "retmax": retmax, "retmode": retmode}
    try:
        r = requests.get(NCBI_ESEARCH, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {"pmids": [], "count": 0, "error": str(e)}

    error = data.get("esearchresult", {}).get("errorlist", {}).get("phrasesessionerror")
    if error:
        return {"pmids": [], "count": 0, "error": error}

    esr = data.get("esearchresult", {})
    return {
        "pmids": esr.get("idlist", []),
        "count": int(esr.get("count", 0)),
        "query_translation": esr.get("querytranslation", ""),
        "error": None,
    }


def pubmed_connector(
    indication: str, config: Dict[str, Any],
    country: Optional[str] = None, metrics: Optional[List[str]] = None,
    retmax_per_query: int = 10, create_stub_evidence: bool = False,
) -> List[EvidenceRecord]:
    """Search PubMed for indication + metric + epidemiology; optionally create stub evidence."""
    if metrics is None:
        metrics = ["incidence", "prevalence"]
    records: List[EvidenceRecord] = []
    for metric in metrics:
        term = f"{indication} {metric} epidemiology" + (f" {country}" if country else "")
        out = search_pubmed(term, retmax=retmax_per_query)
        time.sleep(0.4)
        if create_stub_evidence and out.get("count", 0) >= 0:
            count = out.get("count", 0)
            pmids_str = ", ".join(out.get("pmids", [])[:10])
            if len(out.get("pmids", [])) > 10:
                pmids_str += f" (+{len(out['pmids'])-10} more)"
            records.append(EvidenceRecord(
                indication=indication, metric=f"literature_count_{metric}",
                value=str(count), source_citation="PubMed", source_tier="silver",
                definition=f"Number of PubMed articles (indication + {metric} + epidemiology)",
                population=None, year_or_range=None, geography=country,
                split_logic=None,
                source_url=f"https://pubmed.ncbi.nlm.nih.gov/?term={term.replace(' ', '+')}",
                notes=f"PMIDs (sample): {pmids_str}" if pmids_str else f"{count} articles",
                confidence="low",
                category="Literature & Research",
            ))
    return records


def pubmed_connector_factory(create_stub_evidence: bool = False, metrics: Optional[List[str]] = None):
    """Returns callable(indication, config, **kwargs) -> list[EvidenceRecord]."""
    def _connector(indication: str, config: Dict[str, Any], **kwargs) -> List[EvidenceRecord]:
        return pubmed_connector(indication, config, country=kwargs.get("country"),
                                metrics=metrics, create_stub_evidence=create_stub_evidence)
    return _connector


# ============================================================
# ClinicalTrials.gov API v2 connector
# ============================================================

CT_API_V2 = "https://clinicaltrials.gov/api/v2/studies"


def search_clinical_trials(condition: str, country: str = None, page_size: int = 10) -> Dict[str, Any]:
    """Query ClinicalTrials.gov API v2 for studies matching condition."""
    params = {"query.cond": condition, "pageSize": min(page_size, 100)}
    try:
        r = requests.get(CT_API_V2, params=params, timeout=15)
        r.raise_for_status()
        data = r.json() if r.content else {}
    except Exception as e:
        return {"total_count": 0, "studies": [], "search_url": "", "error": str(e)}
    if not isinstance(data, dict):
        return {"total_count": 0, "studies": [], "search_url": "", "error": "Invalid response"}

    studies = data.get("studies") or []
    total = data.get("totalCount")
    if total is None:
        total = len(studies)
    search_url = f"https://clinicaltrials.gov/search?cond={quote_plus(condition)}"
    if country:
        search_url += f"&locn={quote_plus(country)}"
    return {"total_count": total, "studies": studies[:page_size], "search_url": search_url, "error": None}


def clinicaltrials_connector(indication: str, config: Dict[str, Any], country: str = None, **kwargs) -> List[EvidenceRecord]:
    """Search ClinicalTrials.gov and return stub evidence with study count."""
    country = country or kwargs.get("country") or ""
    out = search_clinical_trials(indication, country=country or None, page_size=5)
    if out.get("error"):
        return []
    total = out.get("total_count", 0)
    return [EvidenceRecord(
        indication=indication, metric="clinical_trials_count", value=str(total),
        source_citation="ClinicalTrials.gov", source_tier="bronze",
        definition="Number of studies matching condition and location",
        population=None, year_or_range=None, geography=country or None, split_logic=None,
        source_url=out.get("search_url", "https://clinicaltrials.gov/search"),
        notes=f"{total} studies; open link to view and filter.", confidence="low",
        category="Literature & Research",
    )]


def clinicaltrials_connector_factory():
    """Returns callable(indication, config, **kwargs) -> list[EvidenceRecord]."""
    def _connector(indication: str, config: Dict[str, Any], **kwargs) -> List[EvidenceRecord]:
        return clinicaltrials_connector(indication, config, **kwargs)
    return _connector


# ============================================================
# WHO GHO OData API connector
# ============================================================

GHO_BASE = "https://ghoapi.azureedge.net/api"

COUNTRY_MAP = {
    "us": "USA", "usa": "USA", "united states": "USA",
    "uk": "GBR", "gbr": "GBR", "united kingdom": "GBR",
    "de": "DEU", "deu": "DEU", "germany": "DEU",
    "fr": "FRA", "fra": "FRA", "france": "FRA",
    "eu5": "FRA", "eu": "FRA",
}


def _country_to_gho_code(country: str) -> Optional[str]:
    if not country or not str(country).strip():
        return None
    c = str(country).strip().lower()
    return COUNTRY_MAP.get(c) or (c.upper() if len(c) == 2 else None)


def fetch_gho_indicator(indicator_code: str, country_code: str = None, top: int = 5) -> List[Dict]:
    """Fetch indicator data from WHO GHO API."""
    url = f"{GHO_BASE}/{indicator_code}"
    params = {"$top": top}
    if country_code:
        params["$filter"] = f"SpatialDim eq '{country_code}'"
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        return r.json().get("value", [])
    except Exception:
        return []


def who_gho_connector(indication: str, config: Dict[str, Any], country: str = None, **kwargs) -> List[EvidenceRecord]:
    """Fetch WHO GHO indicators (life expectancy, NCD mortality) for the country."""
    country = country or kwargs.get("country") or ""
    gho_country = _country_to_gho_code(country)
    records: List[EvidenceRecord] = []

    # Life expectancy at birth
    if gho_country:
        life_exp = fetch_gho_indicator("WHOSIS_000001", gho_country, top=3)
        for row in life_exp[:2]:
            val = row.get("NumericValue") or row.get("Value")
            if val is not None and str(val).strip() != "":
                try:
                    val_str = f"{float(val):.2f}"
                except (TypeError, ValueError):
                    val_str = str(val)
                year = row.get("TimeDimensionBegin", "")[:4] if row.get("TimeDimensionBegin") else None
                records.append(EvidenceRecord(
                    indication=indication, metric="life_expectancy_at_birth", value=val_str,
                    source_citation="WHO GHO", source_tier="gold",
                    definition="Life expectancy at birth (years)",
                    population=row.get("Dim1") or None, year_or_range=year,
                    geography=country or None, split_logic=None,
                    source_url="https://www.who.int/data/gho/data/indicators",
                    notes=f"WHO GHO indicator WHOSIS_000001; country={gho_country}",
                    confidence="high",
                    category="Global Epidemiology",
                ))
                break

    # NCD mortality
    if gho_country:
        try:
            ncd_mort = fetch_gho_indicator("NCD_MORT_30_70", gho_country, top=2)
            for row in ncd_mort[:1]:
                val = row.get("NumericValue") or row.get("Value")
                if val is not None and str(val).strip() != "":
                    try:
                        val_str = f"{float(val):.2f}"
                    except (TypeError, ValueError):
                        val_str = str(val)
                    records.append(EvidenceRecord(
                        indication=indication, metric="ncd_mortality_30_70_pct", value=val_str,
                        source_citation="WHO GHO", source_tier="gold",
                        definition="Probability of dying 30-70 from NCDs (%)",
                        population=None,
                        year_or_range=row.get("TimeDimensionBegin", "")[:4] if row.get("TimeDimensionBegin") else None,
                        geography=country or None, split_logic=None,
                        source_url="https://www.who.int/data/gho/data/indicators",
                        notes=f"WHO GHO NCD_MORT_30_70; country={gho_country}",
                        confidence="high",
                        category="Global Epidemiology",
                    ))
                    break
        except Exception:
            pass

    return records


def who_gho_connector_factory():
    """Returns callable(indication, config, **kwargs) -> list[EvidenceRecord]."""
    def _connector(indication: str, config: Dict[str, Any], **kwargs) -> List[EvidenceRecord]:
        return who_gho_connector(indication, config, **kwargs)
    return _connector
