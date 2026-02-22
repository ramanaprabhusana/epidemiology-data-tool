"""
WHO GHO OData API connector: fetch real numeric values for health indicators by country.
Puts extracted values in the value column (e.g. life expectancy, mortality rates).
"""

from typing import Any, Dict, List, Optional

import requests

from ..schema import EvidenceRecord

GHO_BASE = "https://ghoapi.azureedge.net/api"

# Map common country names/codes to WHO dimension codes (ISO3 where possible)
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
    """
    Fetch indicator data from WHO GHO API. Optional filter by country (SpatialDimension).
    Returns list of records with Value, TimeDimension, etc.
    """
    url = f"{GHO_BASE}/{indicator_code}"
    params = {"$top": top}
    if country_code:
        params["$filter"] = f"SpatialDim eq '{country_code}'"
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        return data.get("value", [])
    except Exception:
        return []


def who_gho_connector(
    indication: str,
    config: Dict[str, Any],
    country: str = None,
    **kwargs,
) -> List[EvidenceRecord]:
    """
    Fetch WHO GHO indicators for the country and add evidence rows with extracted numeric values.
    Uses life expectancy and other available indicators to populate the value column.
    """
    country = country or kwargs.get("country") or ""
    gho_country = _country_to_gho_code(country)
    records: List[EvidenceRecord] = []

    # Life expectancy at birth (WHOSIS_000001) - usually available for most countries
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
                dim1 = row.get("Dim1", "")
                records.append(
                    EvidenceRecord(
                        indication=indication,
                        metric="life_expectancy_at_birth",
                        value=val_str,
                        source_citation="WHO GHO",
                        source_tier="gold",
                        definition="Life expectancy at birth (years)",
                        population=dim1 or None,
                        year_or_range=year,
                        geography=country or None,
                        split_logic=None,
                        source_url="https://www.who.int/data/gho/data/indicators",
                        notes=f"WHO GHO indicator WHOSIS_000001; country={gho_country}",
                        confidence="high",
                    )
                )
                break
    else:
        # Try without country filter to get global or latest
        life_exp = fetch_gho_indicator("WHOSIS_000001", None, top=1)
        if life_exp and life_exp[0].get("Value") is not None:
            records.append(
                EvidenceRecord(
                    indication=indication,
                    metric="life_expectancy_at_birth_global",
                    value=str(life_exp[0]["Value"]),
                    source_citation="WHO GHO",
                    source_tier="silver",
                    definition="Life expectancy at birth (years, global/latest)",
                    population=None,
                    year_or_range=None,
                    geography=country or None,
                    split_logic=None,
                    source_url="https://www.who.int/data/gho/data/indicators",
                    notes="WHO GHO; no country filter applied.",
                    confidence="medium",
                )
            )

    # Age-standardized NCD mortality if available (indicator code may vary)
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
                    records.append(
                        EvidenceRecord(
                            indication=indication,
                            metric="ncd_mortality_30_70_pct",
                            value=val_str,
                            source_citation="WHO GHO",
                            source_tier="gold",
                            definition="Probability of dying 30-70 from NCDs (%)",
                            population=None,
                            year_or_range=row.get("TimeDimensionBegin", "")[:4] if row.get("TimeDimensionBegin") else None,
                            geography=country or None,
                            split_logic=None,
                            source_url="https://www.who.int/data/gho/data/indicators",
                            notes=f"WHO GHO NCD_MORT_30_70; country={gho_country}",
                            confidence="high",
                        )
                    )
                    break
        except Exception:
            pass

    return records


def who_gho_connector_factory():
    """Returns a callable(indication, config, **kwargs) -> list[EvidenceRecord]."""
    def _connector(indication: str, config: Dict[str, Any], **kwargs) -> List[EvidenceRecord]:
        return who_gho_connector(indication, config, **kwargs)
    return _connector
