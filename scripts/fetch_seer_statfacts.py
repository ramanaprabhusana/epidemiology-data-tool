"""
fetch_seer_statfacts.py
-----------------------
Fetches real annual epidemiology data from SEER Cancer StatFacts pages and
updates the curated YAML files with gold-tier SEER values.

Usage:
    .venv/bin/python scripts/fetch_seer_statfacts.py              # all 6 indications
    .venv/bin/python scripts/fetch_seer_statfacts.py prostate     # single indication
    .venv/bin/python scripts/fetch_seer_statfacts.py prostate nhl # multiple

What it updates per YAML:
  - incidence_rate_{year}          (scrapeTable_01, SEER 12 preferred, SEER 8 fallback)
  - mortality_rate_{year}          (scrapeTable_01, Death Rate U.S. Observed)
  - five_year_survival_period_{year} (scrapeTable_01, 5-Yr Relative Survival Observed)
  - incidence_rate_{race}          (scrapeTable_04, cross-sectional 2020-2024)
  - mortality_rate_{race}          (scrapeTable_07, cross-sectional 2020-2024)
  - stage_localized_pct / stage_regional_pct / stage_distant_pct (scrapeTable_02)

All other existing YAML keys are preserved unchanged.
"""

import sys
import re
import requests
import yaml
from pathlib import Path
from bs4 import BeautifulSoup

# ── Configuration ────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent

SEER_PAGES = {
    "cll": {
        "url": "https://seer.cancer.gov/statfacts/html/clyl.html",
        "yaml": ROOT / "config/curated_data/cll.yaml",
        "label": "Chronic Lymphocytic Leukemia",
        "population": "All ages, both sexes",
    },
    "hodgkin": {
        "url": "https://seer.cancer.gov/statfacts/html/hodg.html",
        "yaml": ROOT / "config/curated_data/hodgkin.yaml",
        "label": "Hodgkin Lymphoma",
        "population": "All ages, both sexes",
    },
    "nhl": {
        "url": "https://seer.cancer.gov/statfacts/html/nhl.html",
        "yaml": ROOT / "config/curated_data/nhl.yaml",
        "label": "Non-Hodgkin Lymphoma",
        "population": "All ages, both sexes",
    },
    "gc": {
        "url": "https://seer.cancer.gov/statfacts/html/stomach.html",
        "yaml": ROOT / "config/curated_data/gc.yaml",
        "label": "Stomach (Gastric) Cancer",
        "population": "All ages, both sexes",
    },
    "ovarian": {
        "url": "https://seer.cancer.gov/statfacts/html/ovary.html",
        "yaml": ROOT / "config/curated_data/ovarian.yaml",
        "label": "Ovarian Cancer",
        "population": "All ages, females",
    },
    "prostate": {
        "url": "https://seer.cancer.gov/statfacts/html/prost.html",
        "yaml": ROOT / "config/curated_data/prostate.yaml",
        "label": "Prostate Cancer",
        "population": "All ages, males",
    },
}

# Race name → YAML-safe key slug
RACE_KEY = {
    "All Races": "all_races",
    "Hispanic": "hispanic",
    "Non-Hispanic American Indian/Alaska Native": "aian",
    "Non-Hispanic Asian/Pacific Islander": "asian_pacific_islander",
    "Non-Hispanic Black": "black",
    "Non-Hispanic White": "white_non_hispanic",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research-data-pipeline/1.0)"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean(val: str) -> str:
    """Strip whitespace and % signs."""
    return val.strip().rstrip("%").strip()


def _valid(val: str) -> bool:
    """True if the cell is a real numeric value (not '-' or empty)."""
    v = _clean(val)
    return bool(v) and v != "-"


def _entry(value, unit, year, population, definition, citation, url,
           category="Incidence Rate", geography="US"):
    return {
        "value": str(value),
        "unit": unit,
        "year": str(year),
        "geography": geography,
        "population": population,
        "definition": definition,
        "source_citation": citation,
        "source_url": url,
        "tier": "gold",
        "confidence": "high",
        "category": category,
    }


def fetch_page(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_annual_trends(soup, cfg: dict) -> dict:
    """
    scrapeTable_01 columns (data rows):
      0: Year
      1: SEER 8 Observed    2: SEER 8 Modeled
      3: SEER 12 Observed   4: SEER 12 Modeled
      5: Death Rate Obs     6: Death Rate Modeled
      7: 5-Yr Surv Obs      8: 5-Yr Surv Modeled
    """
    table = soup.find("table", {"id": "scrapeTable_01"})
    if not table:
        print(f"  WARNING: scrapeTable_01 not found at {cfg['url']}")
        return {}

    url = cfg["url"]
    label = cfg["label"]
    pop = cfg["population"]
    citation_base = f"SEER Cancer Stat Facts: {label}. National Cancer Institute. Bethesda, MD, 2024"

    entries = {}
    for row in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) < 6:
            continue
        year = cells[0]
        if not year.isdigit():
            continue

        # Incidence rate: prefer SEER 12 (col 3), fall back to SEER 8 (col 1)
        inc_obs = cells[3] if _valid(cells[3]) else cells[1]
        mort_obs = cells[5] if len(cells) > 5 else ""
        surv_obs = cells[7] if len(cells) > 7 else ""
        # For survival: if observed is "-", use modeled trend
        surv_val = surv_obs if _valid(surv_obs) else (cells[8] if len(cells) > 8 else "")

        registry = "SEER 12" if _valid(cells[3]) else "SEER 8"

        if _valid(inc_obs):
            entries[f"incidence_rate_{year}"] = _entry(
                _clean(inc_obs),
                f"per 100k/yr (age-adjusted, {registry})",
                year, pop,
                f"Age-adjusted incidence rate per 100,000 — {registry} registry",
                citation_base, url, "Incidence Rate",
            )

        if _valid(mort_obs):
            entries[f"mortality_rate_{year}"] = _entry(
                _clean(mort_obs),
                "per 100k/yr (age-adjusted, U.S.)",
                year, pop,
                "Age-adjusted mortality rate per 100,000 — United States",
                citation_base, url, "Mortality Rate",
            )

        if _valid(surv_val):
            entries[f"five_year_survival_period_{year}"] = _entry(
                _clean(surv_val),
                "% 5-year relative survival (SEER 8)",
                year, pop,
                f"5-year relative survival rate — SEER 8 registry",
                citation_base, url, "Survival",
            )

    return entries


def parse_race_incidence(soup, cfg: dict) -> dict:
    """scrapeTable_04: race → incidence rate (cross-sectional, 2020–2024 avg)."""
    table = soup.find("table", {"id": "scrapeTable_04"})
    if not table:
        return {}

    url = cfg["url"]
    label = cfg["label"]
    pop_base = cfg["population"]
    citation = f"SEER Cancer Stat Facts: {label}. National Cancer Institute. Bethesda, MD, 2024 (2020-2024 average)"
    entries = {}

    for row in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        race_raw = cells[0].strip()
        rate_raw = cells[1].strip()
        # Skip "Sex-specific cancer type" placeholders
        if not _valid(rate_raw) or "sex-specific" in rate_raw.lower():
            continue
        race_key = RACE_KEY.get(race_raw)
        if not race_key:
            continue
        entries[f"incidence_rate_{race_key}"] = _entry(
            rate_raw, "per 100k/yr (age-adjusted)", "2020-2024",
            f"{pop_base}, {race_raw}",
            f"Age-adjusted incidence rate per 100,000 — {race_raw} — 2020–2024 average",
            citation, url, "Incidence Rate",
        )
    return entries


def parse_race_mortality(soup, cfg: dict) -> dict:
    """scrapeTable_07: race → mortality rate (cross-sectional, 2020–2024 avg)."""
    table = soup.find("table", {"id": "scrapeTable_07"})
    if not table:
        return {}

    url = cfg["url"]
    label = cfg["label"]
    pop_base = cfg["population"]
    citation = f"SEER Cancer Stat Facts: {label}. National Cancer Institute. Bethesda, MD, 2024 (2020-2024 average)"
    entries = {}

    for row in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        race_raw = cells[0].strip()
        rate_raw = cells[1].strip()
        if not _valid(rate_raw) or "sex-specific" in rate_raw.lower():
            continue
        race_key = RACE_KEY.get(race_raw)
        if not race_key:
            continue
        entries[f"mortality_rate_{race_key}"] = _entry(
            rate_raw, "per 100k/yr (age-adjusted)", "2020-2024",
            f"{pop_base}, {race_raw}",
            f"Age-adjusted mortality rate per 100,000 — {race_raw} — 2020–2024 average",
            citation, url, "Mortality Rate",
        )
    return entries


def parse_stage_distribution(soup, cfg: dict) -> dict:
    """scrapeTable_02: Localized/Regional/Distant/Unknown % and 5-yr survival."""
    table = soup.find("table", {"id": "scrapeTable_02"})
    if not table:
        return {}

    url = cfg["url"]
    label = cfg["label"]
    citation = f"SEER Cancer Stat Facts: {label}. National Cancer Institute. Bethesda, MD, 2024"
    entries = {}

    STAGE_MAP = {
        "localized": "stage_localized",
        "regional":  "stage_regional",
        "distant":   "stage_distant",
        "unknown":   "stage_unknown",
    }

    for row in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        stage_raw = cells[0].lower()
        pct_raw   = _clean(cells[1]) if len(cells) > 1 else ""
        surv_raw  = _clean(cells[2]) if len(cells) > 2 else ""

        for key_fragment, yaml_prefix in STAGE_MAP.items():
            if stage_raw.startswith(key_fragment):
                if _valid(pct_raw):
                    entries[f"{yaml_prefix}_pct"] = _entry(
                        pct_raw, "% of diagnosed cases",
                        "2024", cfg["population"],
                        f"Proportion of {label} cases diagnosed at {key_fragment} stage",
                        citation, url, "Stage Distribution",
                    )
                if _valid(surv_raw):
                    entries[f"{yaml_prefix}_5yr_survival"] = _entry(
                        surv_raw, "% 5-year relative survival",
                        "2024", cfg["population"],
                        f"5-year relative survival for {key_fragment}-stage {label}",
                        citation, url, "Survival",
                    )
                break
    return entries


# ── Main ──────────────────────────────────────────────────────────────────────

def process_indication(key: str, cfg: dict):
    print(f"\n{'='*60}")
    print(f"  {key.upper()} — {cfg['label']}")
    print(f"  URL: {cfg['url']}")
    print(f"{'='*60}")

    yaml_path = cfg["yaml"]
    if not yaml_path.exists():
        print(f"  ERROR: YAML not found at {yaml_path}")
        return

    # Fetch
    print("  Fetching SEER page...", end=" ", flush=True)
    soup = fetch_page(cfg["url"])
    print("OK")

    # Parse all tables
    new_entries = {}
    annual     = parse_annual_trends(soup, cfg)
    race_inc   = parse_race_incidence(soup, cfg)
    race_mort  = parse_race_mortality(soup, cfg)
    stage      = parse_stage_distribution(soup, cfg)

    new_entries.update(annual)
    new_entries.update(race_inc)
    new_entries.update(race_mort)
    new_entries.update(stage)

    print(f"  Parsed: {len(annual)} annual trend entries, "
          f"{len(race_inc)} race-incidence, {len(race_mort)} race-mortality, "
          f"{len(stage)} stage entries")

    # Load existing YAML
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    existing = data.get("metrics", {})
    added = updated = skipped = 0

    for k, v in new_entries.items():
        if k not in existing:
            added += 1
        else:
            updated += 1
        existing[k] = v

    data["metrics"] = existing

    # Write back preserving structure
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False,
                  default_flow_style=False, width=120)

    print(f"  Updated {yaml_path.name}: {added} added, {updated} overwritten")
    print(f"  Total metrics in YAML: {len(existing)}")


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(SEER_PAGES.keys())

    invalid = [t for t in targets if t not in SEER_PAGES]
    if invalid:
        print(f"Unknown indication(s): {invalid}")
        print(f"Valid keys: {list(SEER_PAGES.keys())}")
        sys.exit(1)

    print(f"Fetching SEER data for: {targets}")
    for key in targets:
        process_indication(key, SEER_PAGES[key])

    print(f"\n{'='*60}")
    print("  Done. All curated YAMLs updated with real SEER data.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
