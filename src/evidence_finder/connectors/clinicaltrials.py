"""
ClinicalTrials.gov API v2 connector: search studies by condition and country,
return stub evidence with study count and link to search results.
No API key required.
"""

from urllib.parse import quote_plus
from typing import Any, Dict, List

import requests

from ..schema import EvidenceRecord

# ClinicalTrials.gov API v2
CT_API_V2 = "https://clinicaltrials.gov/api/v2/studies"


def search_clinical_trials(
    condition: str,
    country: str = None,
    page_size: int = 10,
) -> Dict[str, Any]:
    """
    Query ClinicalTrials.gov API v2 for studies matching condition and optional country.
    Returns dict with total_count, studies (list of minimal study info), search_url, error.
    """
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
        if data.get("nextPageToken"):
            total = max(total, 1)
    search_url = f"https://clinicaltrials.gov/search?cond={quote_plus(condition)}"
    if country:
        search_url += f"&locn={quote_plus(country)}"
    return {
        "total_count": total,
        "studies": studies[:page_size],
        "search_url": search_url,
        "error": None,
    }


def clinicaltrials_connector(
    indication: str,
    config: Dict[str, Any],
    country: str = None,
    **kwargs,
) -> List[EvidenceRecord]:
    """
    Search ClinicalTrials.gov for indication (and country); add one stub evidence row
    with study count and link. Tier: bronze.
    """
    country = country or kwargs.get("country") or ""
    out = search_clinical_trials(indication, country=country or None, page_size=5)
    if out.get("error"):
        return []
    total = out.get("total_count", 0)
    search_url = out.get("search_url", "https://clinicaltrials.gov/search")
    records: List[EvidenceRecord] = []
    records.append(
        EvidenceRecord(
            indication=indication,
            metric="clinical_trials_count",
            value=str(total),
            source_citation="ClinicalTrials.gov",
            source_tier="bronze",
            definition="Number of studies matching condition and location",
            population=None,
            year_or_range=None,
            geography=country or None,
            split_logic=None,
            source_url=search_url,
            notes=f"{total} studies; open link to view and filter.",
            confidence="low",
        )
    )
    return records


def clinicaltrials_connector_factory():
    """Returns a callable(indication, config, **kwargs) -> list[EvidenceRecord]."""
    def _connector(indication: str, config: Dict[str, Any], **kwargs) -> List[EvidenceRecord]:
        return clinicaltrials_connector(indication, config, **kwargs)
    return _connector
