"""
API-based evidence connectors: PubMed, ClinicalTrials.gov, WHO GHO.
Merged from individual connector files for simplicity.
Each connector returns List[EvidenceRecord] and has a factory function for the source registry.
"""

import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests

from ..schema import EvidenceRecord
from ..country_utils import pubmed_country_term, country_aliases

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
    retmax_per_query: int = 18, create_stub_evidence: bool = False,
    **kwargs: Any,
) -> List[EvidenceRecord]:
    """Search PubMed for indication + metric + epidemiology; optionally create stub evidence."""
    display = kwargs.get("indication_display") or indication
    expanded = kwargs.get("pubmed_queries")
    records: List[EvidenceRecord] = []

    if expanded and isinstance(expanded, list) and len(expanded) > 0:
        if not create_stub_evidence:
            return []
        for i, term in enumerate(expanded):
            out = search_pubmed(term, retmax=min(retmax_per_query, 25))
            time.sleep(0.35)
            count = int(out.get("count", 0) or 0)
            pmids_str = ", ".join(out.get("pmids", [])[:8])
            if len(out.get("pmids", [])) > 8:
                pmids_str += f" (+{len(out['pmids'])-8} more)"
            records.append(
                EvidenceRecord(
                    indication=display,
                    metric=f"literature_pubmed_q{i + 1}",
                    value=str(count),
                    source_citation="PubMed",
                    source_tier="silver",
                    definition="PubMed hit count (expanded epidemiology query, not title-only keyword match)",
                    population=None,
                    year_or_range=None,
                    geography=country,
                    split_logic=None,
                    source_url=f"https://pubmed.ncbi.nlm.nih.gov/?term={quote_plus(term)}",
                    notes=(f"Query: {term[:180]}. PMIDs (sample): {pmids_str}" if pmids_str else f"Query: {term[:180]}. {count} articles"),
                    confidence="low",
                    category="Literature & Research",
                )
            )
        return records

    if metrics is None:
        metrics = ["incidence", "prevalence", "mortality", "survival"]
    for metric in metrics:
        # Use canonical PubMed/MeSH country term for best recall
        geo_term = pubmed_country_term(country or "")
        term = f"{indication} {metric} epidemiology" + (f" {geo_term}" if geo_term else "")
        out = search_pubmed(term, retmax=retmax_per_query)
        time.sleep(0.35)
        if create_stub_evidence and out.get("count", 0) >= 0:
            count = out.get("count", 0)
            pmids_str = ", ".join(out.get("pmids", [])[:10])
            if len(out.get("pmids", [])) > 10:
                pmids_str += f" (+{len(out['pmids'])-10} more)"
            records.append(
                EvidenceRecord(
                    indication=display,
                    metric=f"literature_count_{metric}",
                    value=str(count),
                    source_citation="PubMed",
                    source_tier="silver",
                    definition=f"Number of PubMed articles (indication + {metric} + epidemiology)",
                    population=None,
                    year_or_range=None,
                    geography=country,
                    split_logic=None,
                    source_url=f"https://pubmed.ncbi.nlm.nih.gov/?term={term.replace(' ', '+')}",
                    notes=f"PMIDs (sample): {pmids_str}" if pmids_str else f"{count} articles",
                    confidence="low",
                    category="Literature & Research",
                )
            )
    return records


def pubmed_connector_factory(create_stub_evidence: bool = False, metrics: Optional[List[str]] = None):
    """Returns callable(indication, config, **kwargs) -> list[EvidenceRecord]."""

    def _connector(indication: str, config: Dict[str, Any], **kwargs) -> List[EvidenceRecord]:
        return pubmed_connector(
            indication,
            config,
            country=kwargs.get("country"),
            metrics=metrics,
            create_stub_evidence=create_stub_evidence,
            **kwargs,
        )

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
    display = kwargs.get("indication_display") or indication
    conditions = kwargs.get("trial_conditions")
    if not conditions:
        conditions = [indication]
    best_total = 0
    best_url = "https://clinicaltrials.gov/search"
    parts: List[str] = []
    for cond in conditions:
        out = search_clinical_trials(cond, country=country or None, page_size=25)
        if out.get("error"):
            continue
        total = int(out.get("total_count", 0) or 0)
        parts.append(f"{cond[:48]}: {total}")
        if total > best_total:
            best_total = total
            best_url = out.get("search_url", best_url) or best_url
        time.sleep(0.2)
    notes = f"{best_total} studies (best of {len(conditions)} condition phrasings). " + "; ".join(parts[:4])
    return [
        EvidenceRecord(
            indication=display,
            metric="clinical_trials_count",
            value=str(best_total),
            source_citation="ClinicalTrials.gov",
            source_tier="bronze",
            definition="Number of studies matching condition (best count across expanded condition strings)",
            population=None,
            year_or_range=None,
            geography=country or None,
            split_logic=None,
            source_url=best_url,
            notes=notes[:900],
            confidence="low",
            category="Literature & Research",
        )
    ]


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
    # United States
    "us": "USA", "usa": "USA", "united states": "USA",
    "united states of america": "USA", "america": "USA",
    "u.s.": "USA", "u.s.a.": "USA", "american": "USA",
    # United Kingdom
    "uk": "GBR", "gbr": "GBR", "united kingdom": "GBR",
    "great britain": "GBR", "england": "GBR", "britain": "GBR",
    "gb": "GBR", "british": "GBR", "scotland": "GBR",
    "wales": "GBR", "northern ireland": "GBR",
    # Germany
    "de": "DEU", "deu": "DEU", "germany": "DEU",
    "deutschland": "DEU", "german": "DEU", "bundesrepublik": "DEU",
    # France
    "fr": "FRA", "fra": "FRA", "france": "FRA",
    "french": "FRA", "republique francaise": "FRA",
    # Canada
    "ca": "CAN", "can": "CAN", "canada": "CAN", "canadian": "CAN",
    # Japan
    "jp": "JPN", "jpn": "JPN", "japan": "JPN",
    "japanese": "JPN", "nippon": "JPN", "nihon": "JPN",
    # China
    "cn": "CHN", "chn": "CHN", "china": "CHN",
    "chinese": "CHN", "prc": "CHN",
    "people's republic of china": "CHN", "peoples republic of china": "CHN",
    "mainland china": "CHN", "zhongguo": "CHN",
    # Australia
    "au": "AUS", "aus": "AUS", "australia": "AUS",
    "australian": "AUS", "oz": "AUS",
    # South Korea
    "kr": "KOR", "kor": "KOR", "south korea": "KOR",
    "korea": "KOR", "republic of korea": "KOR", "korean": "KOR",
    # Italy
    "it": "ITA", "ita": "ITA", "italy": "ITA",
    "italian": "ITA", "italia": "ITA",
    # Spain
    "es": "ESP", "esp": "ESP", "spain": "ESP",
    "spanish": "ESP", "espana": "ESP",
    # Netherlands
    "nl": "NLD", "nld": "NLD", "netherlands": "NLD",
    "holland": "NLD", "dutch": "NLD",
    # Sweden
    "se": "SWE", "swe": "SWE", "sweden": "SWE", "swedish": "SWE",
    # Norway
    "no": "NOR", "nor": "NOR", "norway": "NOR", "norwegian": "NOR",
    # Denmark
    "dk": "DNK", "dnk": "DNK", "denmark": "DNK", "danish": "DNK",
    # Finland
    "fi": "FIN", "fin": "FIN", "finland": "FIN", "finnish": "FIN",
    # Belgium
    "be": "BEL", "bel": "BEL", "belgium": "BEL", "belgian": "BEL",
    # Switzerland
    "ch": "CHE", "che": "CHE", "switzerland": "CHE", "swiss": "CHE",
    # Austria
    "at": "AUT", "aut": "AUT", "austria": "AUT", "austrian": "AUT",
    # India
    "in": "IND", "ind": "IND", "india": "IND", "indian": "IND",
    # Brazil
    "br": "BRA", "bra": "BRA", "brazil": "BRA",
    "brasil": "BRA", "brazilian": "BRA",
    # Mexico
    "mx": "MEX", "mex": "MEX", "mexico": "MEX", "mexican": "MEX",
    # Russia
    "ru": "RUS", "rus": "RUS", "russia": "RUS",
    "russian": "RUS", "russian federation": "RUS",
    # South Africa
    "za": "ZAF", "zaf": "ZAF", "south africa": "ZAF", "south african": "ZAF",
    # Saudi Arabia
    "sa": "SAU", "sau": "SAU", "saudi arabia": "SAU",
    "ksa": "SAU", "saudi": "SAU",
    # Turkey
    "tr": "TUR", "tur": "TUR", "turkey": "TUR",
    "turkish": "TUR", "turkiye": "TUR",
    # Singapore
    "sg": "SGP", "sgp": "SGP", "singapore": "SGP", "singaporean": "SGP",
    # Taiwan
    "tw": "TWN", "twn": "TWN", "taiwan": "TWN", "chinese taipei": "TWN",
    # Portugal
    "pt": "PRT", "prt": "PRT", "portugal": "PRT", "portuguese": "PRT",
    # Poland
    "pl": "POL", "pol": "POL", "poland": "POL", "polish": "POL",
    # Israel
    "il": "ISR", "isr": "ISR", "israel": "ISR", "israeli": "ISR",
    # New Zealand
    "nz": "NZL", "nzl": "NZL", "new zealand": "NZL", "aotearoa": "NZL",
    # EU aggregates (kept for backward compat)
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
    display = kwargs.get("indication_display") or indication
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
                    indication=display, metric="life_expectancy_at_birth", value=val_str,
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
                        indication=display, metric="ncd_mortality_30_70_pct", value=val_str,
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
