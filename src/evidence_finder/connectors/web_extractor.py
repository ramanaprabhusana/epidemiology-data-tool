"""
Focused web extractor: extracts epidemiology data from web pages.
Replaces the 1686-line link_value_extractor.py with a simpler, more accurate approach.

Strategy:
1. Targeted extractors for known high-value sources (SEER, NCI, etc.)
2. Simple table/text extractor with strict indication + metric filtering
3. Fallback: return stub with reference link (honest about what we couldn't extract)

Key improvement: only accepts numbers that appear in text mentioning the target indication.
"""

import re
import time
import threading
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

REQUEST_DELAY = 0.3          # per-thread courtesy delay; parallel threads run concurrently
REQUEST_TIMEOUT = 15         # tighter timeout to fail-fast on slow servers
USER_AGENT = "Mozilla/5.0 (compatible; EpidemiologyDataTool/1.0; +https://github.com)"

# Per-domain rate limiter: prevents hammering the same server from multiple threads.
# Maps netloc -> last-access timestamp.
_domain_last_access: Dict[str, float] = {}
_domain_lock = threading.Lock()
_MIN_DOMAIN_INTERVAL = 1.0   # seconds between requests to the same domain


def _domain_wait(url: str) -> None:
    """Sleep if we recently hit the same domain, to avoid hammering one server."""
    try:
        netloc = urlparse(url).netloc or url
    except Exception:
        netloc = url
    with _domain_lock:
        last = _domain_last_access.get(netloc, 0.0)
        wait = _MIN_DOMAIN_INTERVAL - (time.time() - last)
        if wait > 0:
            # Release lock while sleeping so other domains are not blocked
            _domain_last_access[netloc] = time.time() + wait
        else:
            _domain_last_access[netloc] = time.time()
    if wait > 0:
        time.sleep(wait)


# Indication context for filtering
_indication: str = ""
_indication_aliases: List[str] = []
_indication_lock = threading.Lock()

# Indication alias map - used to broaden text relevance matching during web extraction.
# Keys are substrings matched against the normalised indication label.
# Values are all terms that should count as a match in extracted page text.
_INDICATION_ALIAS_MAP = {
    # CLL
    "cll": [
        "cll", "chronic lymphocytic leukemia", "chronic lymphocytic leukaemia",
        "cll/sll", "small lymphocytic lymphoma", "sll", "b-cell cll",
    ],
    "chronic lymphocytic leukemia": [
        "cll", "chronic lymphocytic leukemia", "chronic lymphocytic leukaemia",
        "cll/sll", "small lymphocytic lymphoma",
    ],
    "chronic lymphocytic leukaemia": [
        "cll", "chronic lymphocytic leukemia", "chronic lymphocytic leukaemia",
    ],
    # Non-Hodgkin Lymphoma
    "non-hodgkin": [
        "non-hodgkin lymphoma", "non hodgkin lymphoma", "nhl",
        "b-cell lymphoma", "diffuse large b-cell", "dlbcl",
        "follicular lymphoma", "marginal zone lymphoma", "mantle cell lymphoma",
        "burkitt lymphoma", "lymphoma",
    ],
    "nhl": [
        "non-hodgkin lymphoma", "nhl", "b-cell lymphoma",
        "diffuse large b-cell", "follicular lymphoma", "lymphoma",
    ],
    # Hodgkin Lymphoma
    "hodgkin": [
        "hodgkin lymphoma", "hodgkin", "classical hodgkin",
        "reed-sternberg", "hodgkin disease", "hl",
    ],
    # Gastric / Stomach Cancer
    "gastric": [
        "gastric cancer", "stomach cancer", "gastric carcinoma",
        "stomach neoplasm", "gastric adenocarcinoma", "gc",
        "gastroesophageal cancer", "gastric tumour",
    ],
    "stomach": [
        "stomach cancer", "gastric cancer", "stomach neoplasm",
        "gastric carcinoma", "stomach carcinoma",
    ],
    # Ovarian Cancer
    "ovarian": [
        "ovarian cancer", "ovarian carcinoma", "ovarian neoplasm",
        "epithelial ovarian cancer", "ovarian tumour", "fallopian tube cancer",
        "peritoneal cancer",
    ],
    # Prostate Cancer
    "prostate": [
        "prostate cancer", "prostate carcinoma", "prostatic neoplasm",
        "prostatic cancer", "prostate adenocarcinoma", "pca",
    ],
    # Lung Cancer
    "lung": [
        "lung cancer", "lung carcinoma", "non-small cell lung cancer", "nsclc",
        "small cell lung cancer", "sclc", "lung neoplasm", "pulmonary cancer",
    ],
    "nsclc": [
        "non-small cell lung cancer", "nsclc", "lung cancer", "lung carcinoma",
    ],
    # Breast Cancer
    "breast": [
        "breast cancer", "breast carcinoma", "breast neoplasm",
        "breast tumour", "mammary cancer", "her2", "triple negative breast cancer",
    ],
    # Colorectal Cancer
    "colorectal": [
        "colorectal cancer", "colon cancer", "rectal cancer",
        "colorectal carcinoma", "crc", "bowel cancer",
    ],
    "colon": [
        "colon cancer", "colorectal cancer", "crc",
    ],
    # Pancreatic Cancer
    "pancreatic": [
        "pancreatic cancer", "pancreatic carcinoma", "pancreas cancer",
        "pancreatic ductal adenocarcinoma", "pdac",
    ],
    # Liver Cancer / HCC
    "hepatocellular": [
        "hepatocellular carcinoma", "hcc", "liver cancer", "hepatic cancer",
    ],
    "liver cancer": [
        "liver cancer", "hepatocellular carcinoma", "hcc", "hepatic cancer",
    ],
    # Bladder Cancer
    "bladder": [
        "bladder cancer", "urothelial carcinoma", "transitional cell carcinoma",
        "bladder carcinoma",
    ],
    # Kidney / Renal Cancer
    "renal": [
        "renal cell carcinoma", "rcc", "kidney cancer", "renal cancer",
        "clear cell carcinoma",
    ],
    "kidney": [
        "kidney cancer", "renal cell carcinoma", "rcc", "renal cancer",
    ],
    # Melanoma
    "melanoma": [
        "melanoma", "malignant melanoma", "cutaneous melanoma",
        "skin cancer", "metastatic melanoma",
    ],
    # Multiple Myeloma
    "myeloma": [
        "multiple myeloma", "myeloma", "plasma cell myeloma",
        "plasmacytoma", "mm",
    ],
    # Acute Myeloid Leukemia
    "aml": [
        "acute myeloid leukemia", "aml", "acute myelogenous leukemia",
        "acute myeloid leukaemia",
    ],
    "acute myeloid": [
        "acute myeloid leukemia", "aml", "acute myelogenous leukemia",
    ],
    # Acute Lymphoblastic Leukemia
    "all": [
        "acute lymphoblastic leukemia", "all", "acute lymphocytic leukemia",
        "acute lymphoid leukemia",
    ],
    # Cervical Cancer
    "cervical": [
        "cervical cancer", "cervical carcinoma", "cervix cancer",
        "uterine cervix cancer",
    ],
    # Endometrial / Uterine Cancer
    "endometrial": [
        "endometrial cancer", "uterine cancer", "endometrial carcinoma",
        "uterine corpus cancer",
    ],
    "uterine": [
        "uterine cancer", "endometrial cancer", "uterine carcinoma",
    ],
    # Head and Neck Cancer
    "head and neck": [
        "head and neck cancer", "head neck squamous cell carcinoma",
        "hnscc", "oral cancer", "pharyngeal cancer", "laryngeal cancer",
    ],
    # Thyroid Cancer
    "thyroid": [
        "thyroid cancer", "thyroid carcinoma", "papillary thyroid cancer",
        "follicular thyroid cancer",
    ],
    # Esophageal Cancer
    "esophageal": [
        "esophageal cancer", "oesophageal cancer", "esophageal carcinoma",
        "esophagus cancer",
    ],
}

# Epidemiology metric keywords
METRIC_KEYWORDS = {
    "incidence": ["incidence", "new cases", "newly diagnosed", "diagnosed with"],
    "prevalence": ["prevalence", "living with", "prevalent"],
    "mortality": ["mortality", "deaths", "died", "death rate"],
    "survival": ["survival", "5-year", "five-year", "overall survival"],
    "rate": ["rate", "per 100,000", "per 100000", "age-adjusted"],
}


def set_indication_context(indication: str) -> None:
    """Set the target indication for filtering. Thread-safe; call once before parallel dives."""
    global _indication, _indication_aliases
    ind = (indication or "").strip().lower()
    aliases = [ind] if ind else []
    for key, alias_list in _INDICATION_ALIAS_MAP.items():
        if key in ind:
            aliases = list(set(aliases + alias_list))
            break
    with _indication_lock:
        _indication = ind
        _indication_aliases = aliases


def _fetch_page(url: str) -> Optional[str]:
    """Fetch page HTML with domain-aware rate limiting."""
    if not HAS_REQUESTS or not url or not url.startswith("http"):
        return None
    _domain_wait(url)   # polite per-domain delay (replaces blanket time.sleep)
    try:
        r = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None


def _text_mentions_indication(text: str) -> bool:
    """Check if text mentions the target indication."""
    if not _indication_aliases:
        return True
    text_lower = text.lower()
    return any(alias in text_lower for alias in _indication_aliases)


def _classify_metric(text: str) -> str:
    """Determine the metric type from surrounding text."""
    text_lower = text.lower()
    for metric, keywords in METRIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return metric
    return "value"


def _is_plausible_number(s: str) -> bool:
    """Check if a string represents a plausible epidemiology number (not a year, ID, etc.)."""
    s_clean = s.replace(",", "").replace(" ", "")
    try:
        n = float(s_clean)
    except ValueError:
        return False
    # Reject years
    if 1900 <= n <= 2050 and "." not in s_clean:
        return False
    # Reject version numbers like 2.2025
    if re.match(r"^\d+\.\d{4}$", s_clean):
        return False
    # Accept reasonable epidemiology values
    if n >= 0.01:
        return True
    return False


NUMBER_RE = re.compile(r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")
PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _extract_from_text(text: str) -> List[Tuple[str, str]]:
    """Extract numbers from text that mentions the indication and epidemiology keywords."""
    if not _text_mentions_indication(text):
        return []

    results = []
    text_lower = text.lower()

    # Only extract from sentences/paragraphs that contain metric keywords
    has_metric_keyword = any(
        kw in text_lower
        for kws in METRIC_KEYWORDS.values()
        for kw in kws
    )
    if not has_metric_keyword:
        return []

    # Extract percentages
    for m in PERCENT_RE.finditer(text):
        val = m.group(1)
        try:
            n = float(val)
            if 0 <= n <= 100:
                metric = _classify_metric(text_lower[max(0, m.start()-100):m.end()+100])
                results.append((metric, f"{val}%"))
        except ValueError:
            pass

    # Extract numbers
    for m in NUMBER_RE.finditer(text):
        val = m.group(1)
        if not _is_plausible_number(val):
            continue
        # Check that a metric keyword is within 200 chars of this number
        start = max(0, m.start() - 200)
        end = min(len(text), m.end() + 200)
        window = text_lower[start:end]
        if not any(kw in window for kws in METRIC_KEYWORDS.values() for kw in kws):
            continue
        # Require indication mention within 500 chars
        wider_start = max(0, m.start() - 500)
        wider_end = min(len(text), m.end() + 500)
        wider_window = text_lower[wider_start:wider_end]
        if _indication_aliases and not any(a in wider_window for a in _indication_aliases):
            continue
        metric = _classify_metric(window)
        results.append((metric, val))

    return results


def _extract_from_tables(soup: "BeautifulSoup") -> List[Tuple[str, str]]:
    """Extract numbers from HTML tables that mention the indication."""
    if not HAS_BS4 or not soup:
        return []
    results = []
    for table in soup.find_all("table")[:20]:
        table_text = table.get_text(separator=" ", strip=True)
        if not _text_mentions_indication(table_text):
            # Check surrounding context
            caption = table.find("caption")
            prev = table.find_previous(["h1", "h2", "h3", "h4", "p"])
            ctx = ""
            if caption:
                ctx += caption.get_text(separator=" ", strip=True)
            if prev:
                ctx += " " + prev.get_text(separator=" ", strip=True)
            if not _text_mentions_indication(ctx):
                continue

        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            row_text = " ".join(c.get_text(separator=" ", strip=True) for c in cells)
            results.extend(_extract_from_text(row_text))

    return results


# --- Targeted extractors for specific high-value sources ---

def _extract_seer_statfacts(soup: "BeautifulSoup", url: str) -> List[Tuple[str, str]]:
    """Extract from SEER Cancer Stat Facts pages (well-structured HTML)."""
    results = []
    if not HAS_BS4 or not soup:
        return results

    # SEER stat facts have specific data in stat containers
    for container in soup.find_all(["div", "section", "p", "li", "td"], limit=200):
        text = container.get_text(separator=" ", strip=True)
        if len(text) > 20 and _text_mentions_indication(text):
            results.extend(_extract_from_text(text))

    # Also extract from tables
    results.extend(_extract_from_tables(soup))

    return results


def _extract_nci_statistics(soup: "BeautifulSoup", url: str) -> List[Tuple[str, str]]:
    """Extract from NCI cancer statistics pages."""
    results = []
    if not HAS_BS4 or not soup:
        return results

    for tag in soup.find_all(["p", "li", "td", "div"], limit=150):
        text = tag.get_text(separator=" ", strip=True)
        if len(text) > 20 and _text_mentions_indication(text):
            results.extend(_extract_from_text(text))

    results.extend(_extract_from_tables(soup))
    return results


# Map of URL patterns to targeted extractors
TARGETED_EXTRACTORS = {
    "seer.cancer.gov/statfacts": _extract_seer_statfacts,
    "seer.cancer.gov": _extract_seer_statfacts,
    "cancer.gov/types": _extract_nci_statistics,
    "cancer.gov/about-cancer/understanding/statistics": _extract_nci_statistics,
}


def _dedupe_and_format(found: List[Tuple[str, str]], max_values: int = 15) -> Optional[str]:
    """Deduplicate and format extracted values, prioritizing labeled metrics."""
    seen_vals: Set[str] = set()
    ordered = []
    for label in ("incidence", "prevalence", "mortality", "survival", "rate", "value"):
        for lbl, val in found:
            if lbl != label:
                continue
            vnorm = val.replace(",", "").replace(" ", "").replace("%", "")
            if vnorm in seen_vals:
                continue
            # Skip tiny bare numbers (likely noise)
            try:
                n = float(vnorm)
                if n < 10 and lbl == "value":
                    continue
            except ValueError:
                pass
            seen_vals.add(vnorm)
            ordered.append((lbl, val))

    if not ordered:
        return None
    ordered = ordered[:max_values]
    parts = [f"{v} ({lbl})" for lbl, v in ordered]
    return "; ".join(parts) if len(parts) > 1 else ordered[0][1]


def extract_from_url(url: str, indication: str = "", country: str = "") -> Optional[str]:
    """
    Extract epidemiology data from a single URL.
    Returns formatted string of extracted values, or None if nothing useful found.
    No recursive link following - single page only.
    """
    if not HAS_BS4 or not HAS_REQUESTS:
        return None

    # Set indication context (thread-safe; no-op if already set to same value)
    if indication:
        set_indication_context(indication)

    html = _fetch_page(url)
    if not html:
        return None

    try:
        soup = BeautifulSoup(html, "html.parser")
        # Remove non-content elements
        for tag in soup(["style", "script", "nav", "footer", "header", "aside"]):
            tag.decompose()
    except Exception:
        return None

    found: List[Tuple[str, str]] = []

    # Try targeted extractor first
    url_lower = url.lower()
    for pattern, extractor in TARGETED_EXTRACTORS.items():
        if pattern in url_lower:
            found.extend(extractor(soup, url))
            break

    # General extraction from body text
    if not found:
        body = soup.find("body") or soup
        for tag in body.find_all(["p", "li", "td", "div", "section"], limit=100):
            text = tag.get_text(separator=" ", strip=True)
            if len(text) > 30:
                found.extend(_extract_from_text(text))
        found.extend(_extract_from_tables(soup))

    return _dedupe_and_format(found)


def deep_dive_link_record(
    url: str,
    delay: bool = True,
    indication: str = "",
    country: str = "",
    deadline: Optional[float] = None,
) -> Optional[str]:
    """
    Extract datapoints from a URL. Compatible with the old link_value_extractor API.
    Now does single-page extraction only (no recursive link following).
    """
    if deadline is not None and time.time() >= deadline:
        return None
    return extract_from_url(url, indication=indication, country=country)
