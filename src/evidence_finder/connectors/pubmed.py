"""
PubMed (NCBI) source connector: search by indication + metric terms, return PMIDs and optional stub evidence.
No API key required; respect NCBI rate limits (e.g. 3 req/sec without key).
"""

import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from ..schema import EvidenceRecord

NCBI_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


def search_pubmed(
    term: str,
    retmax: int = 20,
    retmode: str = "json",
) -> Dict[str, Any]:
    """
    Run a PubMed search. Returns dict with keys: pmids (list), count, query_translation, error (if any).
    """
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
    idlist = esr.get("idlist", [])
    count = int(esr.get("count", 0))
    query_translation = esr.get("querytranslation", "")
    return {
        "pmids": idlist,
        "count": count,
        "query_translation": query_translation,
        "error": None,
    }


def build_search_term(indication: str, metric: str, country: Optional[str] = None) -> str:
    """Build a PubMed search term for epidemiology evidence."""
    parts = [indication, metric, "epidemiology"]
    if country:
        parts.append(country)
    return " ".join(parts)


def pubmed_connector(
    indication: str,
    config: Dict[str, Any],
    country: Optional[str] = None,
    metrics: Optional[List[str]] = None,
    retmax_per_query: int = 10,
    create_stub_evidence: bool = False,
) -> List[EvidenceRecord]:
    """
    PubMed connector for TieredSourceFinder. Searches for indication + metric + epidemiology;
    logs results to source_log via the finder. If create_stub_evidence=True, creates one
    stub evidence row per metric with value='See PMIDs' and notes with PMID list.
    """
    if metrics is None:
        metrics = ["incidence", "prevalence"]
    records: List[EvidenceRecord] = []
    for metric in metrics:
        term = build_search_term(indication, metric, country)
        out = search_pubmed(term, retmax=retmax_per_query)
        time.sleep(0.4)  # rate limit
        if create_stub_evidence and out.get("count", 0) >= 0:
            count = out.get("count", 0)
            pmids_str = ", ".join(out.get("pmids", [])[:10])
            if len(out.get("pmids", [])) > 10:
                pmids_str += f" (+{len(out['pmids'])-10} more)"
            records.append(
                EvidenceRecord(
                    indication=indication,
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
                )
            )
    return records


def pubmed_connector_factory(
    create_stub_evidence: bool = False,
    metrics: Optional[List[str]] = None,
):
    """Returns a callable(indication, config, **kwargs) -> list[EvidenceRecord] for use as source_connectors value."""
    def _connector(indication: str, config: Dict[str, Any], **kwargs) -> List[EvidenceRecord]:
        country = kwargs.get("country")
        return pubmed_connector(
            indication,
            config,
            country=country,
            metrics=metrics,
            create_stub_evidence=create_stub_evidence,
        )
    return _connector
