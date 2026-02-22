"""
Multi-level deep-dive extraction: PERSISTENT search until datapoints are found.
Follows search results → articles → references → company sites with retries and fallbacks.
Supports optional HTTP/HTTPS proxy (config or env) for web scraping.
"""

import os
import re
import time
from pathlib import Path
from typing import List, Optional, Tuple, Set, Dict, Any
from urllib.parse import urljoin, urlparse

import requests

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

REQUEST_DELAY = 0.7  # Balanced for speed vs rate limits
REQUEST_TIMEOUT = 20  # Timeout per page
MAX_RETRIES = 2  # Retries for transient failures
MAX_VISITED_PER_RUN = 65  # Hard cap URLs per extraction run; slight increase for journal-heavy sources
USER_AGENT = "Mozilla/5.0 (compatible; EpidemiologyDataTool/1.0; +https://github.com)"

# Proxy: loaded from config/scraper.yaml or env (HTTP_PROXY, HTTPS_PROXY). Rotation index for proxy_list.
_proxy_list: List[str] = []
_proxy_index = 0


def _load_scraper_config() -> Dict[str, Any]:
    """Load config/scraper.yaml (proxy settings). Uses custom config_dir if set via set_config_dir_for_proxy()."""
    config_dir = getattr(_load_scraper_config, "_config_dir", None)
    if config_dir is None:
        config_dir = Path(__file__).resolve().parents[2] / "config"
    path = Path(config_dir) / "scraper.yaml"
    if not path.exists():
        return getattr(_load_scraper_config, "_cached", {}) or {}
    try:
        import yaml
        with open(path, "r") as f:
            out = yaml.safe_load(f) or {}
        _load_scraper_config._cached = out  # type: ignore[attr-defined]
        return out
    except Exception:
        return getattr(_load_scraper_config, "_cached", {}) or {}


def _get_proxies_for_request() -> Optional[Dict[str, str]]:
    """Return proxies dict for requests.get, or None. Uses proxy_url, proxy_list (round-robin), or env."""
    global _proxy_list, _proxy_index
    cfg = _load_scraper_config()
    if not cfg.get("use_proxy"):
        # Still respect env if set (common for debugging)
        http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if http_proxy or https_proxy:
            return {"http": http_proxy or https_proxy or "", "https": https_proxy or http_proxy or ""}
        return None

    proxy_url = cfg.get("proxy_url") or ""
    if proxy_url and isinstance(proxy_url, str):
        return {"http": proxy_url, "https": proxy_url}

    pl = cfg.get("proxy_list")
    if pl and isinstance(pl, list) and len(pl) > 0:
        if not _proxy_list:
            _proxy_list = [str(p).strip() for p in pl if p]
        if _proxy_list:
            url = _proxy_list[_proxy_index % len(_proxy_list)]
            _proxy_index += 1
            return {"http": url, "https": url}

    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if http_proxy or https_proxy:
        return {"http": http_proxy or https_proxy or "", "https": https_proxy or http_proxy or ""}
    return None


def set_config_dir_for_proxy(config_dir: Optional[Path]) -> None:
    """Use this config dir for scraper.yaml (proxy settings). Call at start of pipeline run."""
    if config_dir is None:
        _load_scraper_config._config_dir = None  # type: ignore[attr-defined]
        return
    _load_scraper_config._config_dir = Path(config_dir).resolve()  # type: ignore[attr-defined]
    _load_scraper_config._cached = {}  # type: ignore[attr-defined]  # force reload

SEARCH_HOSTS = ("scholar.google.com", "google.com", "bing.com", "duckduckgo.com")
SEARCH_PATTERNS = ("/scholar?", "search?", "q=", "query=")

JOURNAL_HOSTS = (
    "thelancet.com", "nejm.org", "jamanetwork.com", "nature.com", "bmj.com",
    "sciencedirect.com", "onlinelibrary.wiley.com", "link.springer.com", "springer.com",
    "academic.oup.com", "annalsofoncology.org", "ejcancer.com", "aacrjournals.org",
    "ascopubs.org", "cochranelibrary.com", "ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov",
    "esmo.org", "medscape.com", "cancer.net", "tripdatabase.com", "pubmed.ncbi.nlm.nih.gov",
)
JOURNAL_SEARCH_PATTERNS = ("/action/doSearch", "dosearch", "/search", "searchresults", "search?q=", "q=", "term=", "query=", "qs=")
ARTICLE_PATH_PATTERNS = ("/article/", "/articles/", "/fulltext", "/fullarticle", "/doi/", "/content/", "/science/article/", "/journals/", "/cdsr/", "/full", "/abstract", "/pdf/", "/fullarticle", "/article-abstract", "/pubmed/", "/pmc/articles/", "/pub/", "/view/")

COMPANY_HOSTS = (
    "pfizer.com", "merck.com", "novartis.com", "roche.com", "bms.com", "bristol-myers.com",
    "gsk.com", "glaxosmithkline.com", "sanofi.com", "astrazeneca.com", "abbvie.com",
    "amgen.com", "gilead.com", "biogen.com", "regeneron.com", "moderna.com",
    "biomarin.com", "vertex.com", "illumina.com", "qiagen.com", "janssen.com", "johnson-johnson.com",
)
COMPANY_DATA_PATTERNS = ("/disease/", "/indication/", "/therapeutic-area/", "/research/", "/data/", "/statistics/", "/epidemiology/", "/prevalence/", "/incidence/", "/burden/", "/patient/")

REFERENCE_PATTERNS = ("/reference", "/citation", "/cited-by", "/references", "/bibliography", "/doi/", "doi.org", "/cite", "/bib")

# Org/reference sites with statistics/epidemiology content (per-host extraction)
ORG_SITE_HOSTS = (
    "cancer.net", "medscape.com", "rarediseases.org", "nord.org", "esmo.org", "astro.org",
    "ecco-org.eu", "uicc.org", "wcrf.org", "tripdatabase.com", "tga.gov.au", "go.drugbank.com",
    "drugbank.com", "ema.europa.eu", "opentrials.net", "clinicaltrialsregister.eu",
)

# Interactive data portals that need special handling
DATA_PORTAL_HOSTS = (
    "gco.iarc.who.int", "iarc.who.int",  # GLOBOCAN
    "seer.cancer.gov", "cancer.gov",  # SEER, NCI
    "who.int/data", "data.who.int",  # WHO Data Hub
    "ci5.iarc.who.int",  # CI5
    "wonder.cdc.gov", "cdc.gov",  # CDC WONDER
    "statecancerprofiles.cancer.gov",  # State Cancer Profiles
    "healthdata.org",  # IHME
    "oecd.org",  # OECD Health
)
DATA_PORTAL_PATTERNS = ("/dataviz", "/explorer", "/data", "/statistics", "/dashboard", "/visualization", "/api/", "/data/")

KPI_KEYWORDS = (
    "incidence", "prevalence", "cases", "patients", "new cases", "diagnosed",
    "per 100,000", "per 100000", "per 100k", "rate", "estimated", "annual",
    "mortality", "survival", "percent", "%", "percentage", "epidemiology",
    "burden", "prevalence rate", "incidence rate", "diagnosis", "morbidity",
    "statistics", "statistic", "estimate", "number of", "total", "findings",
    "reported", "observed", "study", "population", "cohort",
)

NUMBER_PATTERN = re.compile(r"\b(\d{1,3}(?:[, \u00a0]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\b")
PERCENT_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*%|\b(\d+(?:\.\d+)?)\s+percent\b")


def _get_page_with_selenium(url: str) -> Optional[str]:
    """Fetch page with headless Chrome. Used as fallback when requests fails (e.g. JS-rendered content)."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument(f"--user-agent={USER_AGENT}")
        driver = webdriver.Chrome(options=opts)
        try:
            driver.set_page_load_timeout(REQUEST_TIMEOUT)
            driver.get(url)
            return driver.page_source
        finally:
            driver.quit()
    except Exception:
        return None


def _get_page_text(url: str, retry: int = 0, _try_without_proxy: bool = False) -> Optional[str]:
    """Fetch with retry logic. Uses proxy from config/scraper.yaml or HTTP_PROXY/HTTPS_PROXY if use_proxy is true.
    Falls back to Selenium (headless Chrome) when requests fails and use_selenium_fallback is true."""
    if not url or not url.startswith("http"):
        return None
    proxies = None if _try_without_proxy else _get_proxies_for_request()
    try:
        r = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
            proxies=proxies,
        )
        if r.status_code == 200:
            return r.text
        if r.status_code in (403, 429, 500, 502, 503) and retry < MAX_RETRIES:
            time.sleep(REQUEST_DELAY * (retry + 2))
            return _get_page_text(url, retry + 1, _try_without_proxy=_try_without_proxy)
        r.raise_for_status()
        return r.text
    except Exception:
        # If we used a proxy and failed, retry once without proxy (free proxies often fail)
        if not _try_without_proxy and proxies and retry < MAX_RETRIES:
            time.sleep(REQUEST_DELAY)
            return _get_page_text(url, retry=0, _try_without_proxy=True)
        if retry < MAX_RETRIES:
            time.sleep(REQUEST_DELAY * (retry + 1))
            return _get_page_text(url, retry + 1, _try_without_proxy=_try_without_proxy)
        # Selenium fallback when requests exhausts retries
        cfg = _load_scraper_config()
        if cfg.get("use_selenium_fallback"):
            time.sleep(REQUEST_DELAY)
            return _get_page_with_selenium(url)
        return None


def _is_search_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower().replace("www.", "")
        combined = (parsed.path or "").lower() + " " + (parsed.query or "").lower()
        return any(h in host for h in SEARCH_HOSTS) and any(p in combined for p in SEARCH_PATTERNS)
    except Exception:
        return False


def _is_journal_search_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower().replace("www.", "")
        combined = (parsed.path or "").lower() + " " + (parsed.query or "").lower()
        if not any(h in host for h in JOURNAL_HOSTS):
            return False
        search_lower = [p.lower() for p in JOURNAL_SEARCH_PATTERNS]
        return any(p in combined for p in search_lower)
    except Exception:
        return False


def _is_journal_article_url(url: str) -> bool:
    """Check if URL is a journal article page (not just search)."""
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower().replace("www.", "")
        path = (parsed.path or "").lower()
        # Check if it's a journal host
        if not any(h in host for h in JOURNAL_HOSTS):
            return False
        # Check if path matches article patterns
        return any(pat in path for pat in ARTICLE_PATH_PATTERNS)
    except Exception:
        return False


def _extract_from_journal_article(soup: "BeautifulSoup", url: str) -> List[Tuple[str, str]]:
    """
    DEEP-DIVE extraction specifically for journal articles - TRIANGULATE data from multiple sections.
    CRITICAL: Must deep-dive into RESULTS, CONCLUSIONS, and OBSERVATIONS sections for each journal.
    Triangulates data across sections to ensure comprehensive extraction.
    """
    found = []
    if not HAS_BS4 or not soup:
        return found
    
    try:
        host = (urlparse(url).netloc or "").lower().replace("www.", "")
        # Per-host section class/id patterns for Results, Conclusions, Abstract (publisher-specific)
        journal_section_patterns = {
            "thelancet.com": (r"result|conclusion|abstract|finding|summary|article-section|section-content", ["section", "div", "article"]),
            "nejm.org": (r"result|conclusion|abstract|article-body|full-text|section", ["section", "div", "article"]),
            "jamanetwork.com": (r"abstract|results|conclusion|article-body|full-text|content", ["section", "div", "article"]),
            "nature.com": (r"abstract|result|conclusion|article-body|c-article-body|section", ["section", "div", "article"]),
            "bmj.com": (r"abstract|result|conclusion|article-body|full-text|section", ["section", "div", "article"]),
            "sciencedirect.com": (r"abstract|result|conclusion|article-body|body|section", ["section", "div", "article"]),
            "onlinelibrary.wiley.com": (r"abstract|result|conclusion|article-section|body|section", ["section", "div", "article"]),
            "link.springer.com": (r"abstract|result|conclusion|main-content|body|section", ["section", "div", "article"]),
            "springer.com": (r"abstract|result|conclusion|main-content|body|section", ["section", "div", "article"]),
            "academic.oup.com": (r"abstract|result|conclusion|article-body|section", ["section", "div", "article"]),
            "ascopubs.org": (r"abstract|result|conclusion|article-body|fulltext|section", ["section", "div", "article"]),
            "cochranelibrary.com": (r"abstract|result|conclusion|full-text|section", ["section", "div", "article"]),
            "annalsofoncology.org": (r"abstract|result|conclusion|article-body|section", ["section", "div", "article"]),
            "ejcancer.com": (r"abstract|result|conclusion|article-body|section", ["section", "div", "article"]),
            "aacrjournals.org": (r"abstract|result|conclusion|article-body|section", ["section", "div", "article"]),
            "ncbi.nlm.nih.gov": (r"abstract|result|conclusion|article-body|fullview|section", ["section", "div", "article"]),
            "pmc.ncbi.nlm.nih.gov": (r"abstract|result|conclusion|article-body|tsec|section", ["section", "div", "article"]),
        }
        for pattern_host, (section_regex, tag_types) in journal_section_patterns.items():
            if pattern_host not in host:
                continue
            section_re = re.compile(section_regex, re.I)
            for tag in soup.find_all(tag_types, class_=section_re)[:30]:
                text = tag.get_text(separator=" ", strip=True)
                if len(text) > 80:
                    found.extend(_extract_numbers_from_text(text[:150000], require_kpi_context=True))
                    found.extend(_extract_percentages_from_text(text))
            for tag in soup.find_all(tag_types, id=section_re)[:20]:
                text = tag.get_text(separator=" ", strip=True)
                if len(text) > 80:
                    found.extend(_extract_numbers_from_text(text[:100000], require_kpi_context=True))
                    found.extend(_extract_percentages_from_text(text))
            break  # One host only

        # ===== CRITICAL SECTION 1: RESULTS - DEEP DIVE =====
        # Results section is PRIMARY source - extract comprehensively
        results_selectors = [
            {"class": re.compile(r"result", re.I)},
            {"id": re.compile(r"result", re.I)},
            {"data-section": re.compile(r"result", re.I)},
            {"section": "results"},
            {"data-title": re.compile(r"result", re.I)},
        ]
        results_texts = []
        for selector in results_selectors:
            for tag in soup.find_all(["section", "div", "article"], selector)[:20]:  # More results sections
                text = tag.get_text(separator=" ", strip=True)
                if len(text) > 50:  # Any meaningful results text
                    results_texts.append(text)
                    # Extract from results text
                    found.extend(_extract_numbers_from_text(text, require_kpi_context=True))
                    found.extend(_extract_percentages_from_text(text))
                    # Extract from ALL tables in results section
                    for table in tag.find_all("table")[:20]:
                        found.extend(_extract_from_tables(BeautifulSoup(str(table), "html.parser")))
                    # Extract from ALL paragraphs in results
                    for p in tag.find_all(["p", "li", "div"])[:50]:
                        p_text = p.get_text(separator=" ", strip=True)
                        if len(p_text) > 20:
                            found.extend(_extract_numbers_from_text(p_text, require_kpi_context=True))
                            found.extend(_extract_percentages_from_text(p_text))
        
        # ===== CRITICAL SECTION 2: CONCLUSIONS - DEEP DIVE =====
        # Conclusions often summarize key findings - extract comprehensively
        conclusions_selectors = [
            {"class": re.compile(r"conclusion", re.I)},
            {"id": re.compile(r"conclusion", re.I)},
            {"data-section": re.compile(r"conclusion", re.I)},
            {"section": "conclusions"},
            {"data-title": re.compile(r"conclusion", re.I)},
        ]
        conclusions_texts = []
        for selector in conclusions_selectors:
            for tag in soup.find_all(["section", "div", "article"], selector)[:20]:
                text = tag.get_text(separator=" ", strip=True)
                if len(text) > 50:
                    conclusions_texts.append(text)
                    # Extract from conclusions text
                    found.extend(_extract_numbers_from_text(text, require_kpi_context=True))
                    found.extend(_extract_percentages_from_text(text))
                    # Extract from paragraphs in conclusions
                    for p in tag.find_all(["p", "li", "div"])[:50]:
                        p_text = p.get_text(separator=" ", strip=True)
                        if len(p_text) > 20:
                            found.extend(_extract_numbers_from_text(p_text, require_kpi_context=True))
                            found.extend(_extract_percentages_from_text(p_text))
        
        # ===== CRITICAL SECTION 3: OBSERVATIONS - DEEP DIVE =====
        # Observations section - extract comprehensively
        observations_selectors = [
            {"class": re.compile(r"observation", re.I)},
            {"id": re.compile(r"observation", re.I)},
            {"data-section": re.compile(r"observation", re.I)},
            {"data-title": re.compile(r"observation", re.I)},
        ]
        observations_texts = []
        for selector in observations_selectors:
            for tag in soup.find_all(["section", "div", "article"], selector)[:20]:
                text = tag.get_text(separator=" ", strip=True)
                if len(text) > 50:
                    observations_texts.append(text)
                    found.extend(_extract_numbers_from_text(text, require_kpi_context=True))
                    found.extend(_extract_percentages_from_text(text))
                    for p in tag.find_all(["p", "li", "div"])[:50]:
                        p_text = p.get_text(separator=" ", strip=True)
                        if len(p_text) > 20:
                            found.extend(_extract_numbers_from_text(p_text, require_kpi_context=True))
                            found.extend(_extract_percentages_from_text(p_text))
        
        # ===== TRIANGULATION: Cross-reference data across sections =====
        # Combine all section texts and extract again for triangulation
        all_section_texts = " ".join(results_texts + conclusions_texts + observations_texts)
        if len(all_section_texts) > 100:
            # Extract from combined text (triangulation)
            found.extend(_extract_numbers_from_text(all_section_texts[:200000], require_kpi_context=True))
            found.extend(_extract_percentages_from_text(all_section_texts))
        
        # ===== SECTION 4: Abstract - also important =====
        abstract_selectors = [
            {"class": re.compile(r"abstract", re.I)},
            {"id": re.compile(r"abstract", re.I)},
            {"data-section": re.compile(r"abstract", re.I)},
            {"section": "abstract"},
        ]
        for selector in abstract_selectors:
            for tag in soup.find_all(["section", "div", "p"], selector)[:10]:
                text = tag.get_text(separator=" ", strip=True)
                if len(text) > 50:
                    found.extend(_extract_numbers_from_text(text, require_kpi_context=True))
                    found.extend(_extract_percentages_from_text(text))
        
        # ===== SECTION 5: Methods - sample sizes, patient counts =====
        methods_selectors = [
            {"class": re.compile(r"method", re.I)},
            {"id": re.compile(r"method", re.I)},
            {"data-section": re.compile(r"method", re.I)},
        ]
        for selector in methods_selectors:
            for tag in soup.find_all(["section", "div"], selector)[:10]:
                text = tag.get_text(separator=" ", strip=True)
                if len(text) > 100:
                    found.extend(_extract_numbers_from_text(text[:100000], require_kpi_context=False))
        
        # ===== SECTION 6: Extract from ALL tables in the article =====
        found.extend(_extract_from_tables(soup))
        
        # ===== SECTION 7: Extract from figure captions (often contain key statistics) =====
        for fig in soup.find_all(["figure", "figcaption", "div"], class_=re.compile(r"figure|fig|caption", re.I))[:30]:
            text = fig.get_text(separator=" ", strip=True)
            if len(text) > 20:
                found.extend(_extract_numbers_from_text(text, require_kpi_context=True))
                found.extend(_extract_percentages_from_text(text))
        
        # ===== SECTION 8: Extract from supplementary material links - DEEP DIVE =====
        for a in soup.find_all("a", href=True)[:100]:  # More links
            href = a.get("href", "").lower()
            text = (a.get_text() or "").lower()
            if any(x in href or x in text for x in ["supplement", "supplementary", "data", "repository", "dataset", "table", "figure", "s1", "s2", "s3", "appendix"]):
                full_link = urljoin(url, a.get("href", ""))
                if full_link.startswith("http") and full_link not in [url]:
                    time.sleep(REQUEST_DELAY * 0.5)
                    supp_text = _get_page_text(full_link)
                    if supp_text and HAS_BS4:
                        try:
                            supp_soup = BeautifulSoup(supp_text, "html.parser")
                            supp_body = supp_soup.get_text(separator=" ", strip=True)
                            # Deep-dive into supplementary materials
                            found.extend(_extract_numbers_from_text(supp_body[:200000], require_kpi_context=True))
                            found.extend(_extract_from_tables(supp_soup))
                            # Also extract from results/conclusions in supplementary
                            for section in supp_soup.find_all(["section", "div"], class_=re.compile(r"result|conclusion|observation", re.I))[:10]:
                                s_text = section.get_text(separator=" ", strip=True)
                                found.extend(_extract_numbers_from_text(s_text, require_kpi_context=True))
                        except:
                            pass
        
        # ===== SECTION 9: Extract from data availability sections =====
        for tag in soup.find_all(["section", "div"], class_=re.compile(r"data.*avail|availability|repository", re.I))[:10]:
            text = tag.get_text(separator=" ", strip=True)
            found.extend(_extract_numbers_from_text(text, require_kpi_context=False))
        
        # ===== SECTION 10: Extract from highlights/key findings sections =====
        for tag in soup.find_all(["section", "div", "ul", "ol"], class_=re.compile(r"highlight|key.*find|summary|finding|takeaway", re.I))[:20]:
            text = tag.get_text(separator=" ", strip=True)
            found.extend(_extract_numbers_from_text(text, require_kpi_context=True))
            found.extend(_extract_percentages_from_text(text))
        
        # ===== SECTION 11: Extract from discussion section (often summarizes results) =====
        discussion_selectors = [
            {"class": re.compile(r"discussion", re.I)},
            {"id": re.compile(r"discussion", re.I)},
            {"data-section": re.compile(r"discussion", re.I)},
        ]
        for selector in discussion_selectors:
            for tag in soup.find_all(["section", "div"], selector)[:10]:
                text = tag.get_text(separator=" ", strip=True)
                if len(text) > 100:
                    found.extend(_extract_numbers_from_text(text[:100000], require_kpi_context=True))
                    found.extend(_extract_percentages_from_text(text))
        
        # ===== SECTION 12: Extract from ALL paragraphs in the article body =====
        # Sometimes data is in regular paragraphs not in specific sections
        for p in soup.find_all(["p", "div", "li"])[:200]:  # More paragraphs
            p_text = p.get_text(separator=" ", strip=True)
            # Look for paragraphs with epidemiology keywords
            if len(p_text) > 50 and any(kw in p_text.lower() for kw in ["incidence", "prevalence", "cases", "patients", "rate", "percent", "%", "mortality", "survival"]):
                found.extend(_extract_numbers_from_text(p_text, require_kpi_context=True))
                found.extend(_extract_percentages_from_text(p_text))
        
    except Exception:
        pass
    
    return found


def _is_org_site(url: str) -> bool:
    """Check if URL is an org/reference site we handle with per-host extraction."""
    try:
        host = (urlparse(url).netloc or "").lower().replace("www.", "")
        return any(h in host for h in ORG_SITE_HOSTS)
    except Exception:
        return False


def _extract_from_org_site(soup: "BeautifulSoup", url: str) -> List[Tuple[str, str]]:
    """Extract datapoints from org/reference sites (Cancer.net, Medscape, NORD, etc.) using main content areas."""
    found: List[Tuple[str, str]] = []
    if not HAS_BS4 or not soup:
        return found
    try:
        host = (urlparse(url).netloc or "").lower().replace("www.", "")
        # Main content selectors (role=main, id=content, class=content/main/article-body)
        main_selectors = [
            ("[role='main']", "css"),
            ("#content", "css"),
            ("#main", "css"),
            ("main", "tag"),
            (".content", "css"),
            (".main-content", "css"),
            (".article-body", "css"),
            (".article-content", "css"),
            (".entry-content", "css"),
            (".post-content", "css"),
            (".body", "css"),
            ("article", "tag"),
        ]
        for sel, sel_type in main_selectors:
            try:
                if sel_type == "css":
                    tags = soup.select(sel)[:15]
                else:
                    tags = soup.find_all(sel, limit=15)
            except Exception:
                tags = []
            for tag in tags:
                text = tag.get_text(separator=" ", strip=True)
                if len(text) > 200:
                    found.extend(_extract_numbers_from_text(text[:200000], require_kpi_context=True))
                    found.extend(_extract_percentages_from_text(text))
                    found.extend(_extract_from_tables(BeautifulSoup(str(tag), "html.parser")))

        # Sections that often contain epidemiology/statistics
        stats_section_re = re.compile(r"statistic|epidemiology|incidence|prevalence|rate|burden|overview|key.*point|fact|number|data", re.I)
        for tag in soup.find_all(["section", "div", "article"], class_=stats_section_re)[:25]:
            text = tag.get_text(separator=" ", strip=True)
            if len(text) > 100:
                found.extend(_extract_numbers_from_text(text[:100000], require_kpi_context=True))
                found.extend(_extract_percentages_from_text(text))
        for tag in soup.find_all(["section", "div"], id=stats_section_re)[:15]:
            text = tag.get_text(separator=" ", strip=True)
            if len(text) > 100:
                found.extend(_extract_numbers_from_text(text[:80000], require_kpi_context=True))
                found.extend(_extract_percentages_from_text(text))

        # Cancer.net / Medscape style: dl, lists with "Incidence", "Prevalence" headings
        for tag in soup.find_all(["dl", "ul", "ol"])[:30]:
            text = tag.get_text(separator=" ", strip=True)
            if len(text) > 50 and any(kw in text.lower() for kw in ["incidence", "prevalence", "rate", "percent", "cases", "patients"]):
                found.extend(_extract_numbers_from_text(text, require_kpi_context=True))
                found.extend(_extract_percentages_from_text(text))

        # All tables on page (org sites often put stats in tables)
        found.extend(_extract_from_tables(soup))

        # Paragraphs with epidemiology keywords (broader scan)
        for p in soup.find_all(["p", "div", "li", "td"])[:150]:
            p_text = p.get_text(separator=" ", strip=True)
            if len(p_text) > 40 and any(kw in p_text.lower() for kw in ["incidence", "prevalence", "cases", "rate", "%", "percent", "mortality", "survival", "estimated", "statistics"]):
                found.extend(_extract_numbers_from_text(p_text, require_kpi_context=True))
                found.extend(_extract_percentages_from_text(p_text))
    except Exception:
        pass
    return found


def _is_company_site(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower().replace("www.", "")
        return any(c in host for c in COMPANY_HOSTS)
    except Exception:
        return False


def _get_all_links_from_soup(soup: "BeautifulSoup", base_url: str, max_links: int = 30, filter_patterns: Optional[List[str]] = None) -> List[str]:
    """Extract all relevant links from a page - more aggressive."""
    if not HAS_BS4 or not soup:
        return []
    try:
        base_parsed = urlparse(base_url)
        base_netloc = (base_parsed.netloc or "").lower().replace("www.", "")
        seen = set()
        out = []
        for a in soup.find_all("a", href=True)[:200]:  # Check more links
            href = (a.get("href") or "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
                continue
            full = urljoin(base_url, href)
            if full in seen:
                continue
            try:
                p = urlparse(full)
                netloc = (p.netloc or "").lower().replace("www.", "")
                path = (p.path or "").lower()
            except Exception:
                continue
            if filter_patterns:
                if not any(pat in path or pat in href.lower() for pat in filter_patterns):
                    continue
            seen.add(full)
            out.append(full)
            if len(out) >= max_links:
                break
        return out
    except Exception:
        return []


def _get_search_result_links(soup: "BeautifulSoup", base_url: str) -> List[str]:
    """From Google Scholar/search results, extract article/result links - ULTRA AGGRESSIVE."""
    if not HAS_BS4 or not soup:
        return []
    links = []
    # Google Scholar: look for <h3><a> or <a> with class containing "gs_"
    for h3 in soup.find_all("h3")[:30]:  # Increased from 20
        a = h3.find("a", href=True)
        if a:
            href = a.get("href", "")
            if href.startswith("http") or href.startswith("/"):
                full = urljoin(base_url, href)
                if full not in links:
                    links.append(full)
    # Also check <a> tags with text that looks like article titles
    for a in soup.find_all("a", href=True)[:120]:
        href = a.get("href", "")
        text = (a.get_text() or "").strip()
        if len(text) > 15 and len(text) < 250 and ("http" in href or href.startswith("/")):
            full = urljoin(base_url, href)
            if full not in links and not any(x in full.lower() for x in ["javascript:", "mailto:", "#"]):
                links.append(full)
    return links[:12]


def _get_journal_search_result_links(soup: "BeautifulSoup", base_url: str) -> List[str]:
    """Extract article links from journal search result pages using per-host patterns."""
    if not HAS_BS4 or not soup:
        return []
    try:
        host = (urlparse(base_url).netloc or "").lower().replace("www.", "")
    except Exception:
        return []
    links = []
    seen = set()
    path_lower = (urlparse(base_url).path or "").lower()

    # Generic: any <a> whose href matches article paths
    for a in soup.find_all("a", href=True)[:200]:
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or "javascript:" in href.lower():
            continue
        full = urljoin(base_url, href)
        if full in seen:
            continue
        full_lower = full.lower()
        if any(pat in full_lower for pat in ARTICLE_PATH_PATTERNS):
            seen.add(full)
            links.append(full)
        # Also accept links that look like article detail (e.g. /doi/..., /article/...)
        if "/doi/" in full_lower or "/article/" in full_lower or "/fulltext" in full_lower or "/content/" in full_lower or "/pub/" in full_lower or "/pmc/articles/" in full_lower:
            if full not in seen:
                seen.add(full)
                links.append(full)

    # Per-host: result list items often wrap the title link
    result_item_selectors = [
        ("thelancet.com", ["div.search-result-item", "li.search__item", "article", "div[data-article]"]),
        ("nejm.org", ["div.article-result", "li.result-item", "article", "div.search-result"]),
        ("jamanetwork.com", ["div.result-item", "article.search-result", "li.result"]),
        ("nature.com", ["article[itemtype*='Article']", "div.c-card", "li.search-result", "div.result-item"]),
        ("bmj.com", ["div.result-item", "li.search-result", "article"]),
        ("sciencedirect.com", ["div.result-list-content", "li.result-item", "article"]),
        ("onlinelibrary.wiley.com", ["div.result-item", "li.article", "div.article-item"]),
        ("link.springer.com", ["li.results-list__item", "article", "div.result-item"]),
        ("academic.oup.com", ["div.search-result", "li.result", "article"]),
        ("ascopubs.org", ["div.article-result", "li.result-item", "div.search-result"]),
        ("cochranelibrary.com", ["div.search-result", "li.result", "article"]),
        ("annalsofoncology.org", ["div.article-item", "li.result", "article"]),
        ("ejcancer.com", ["div.article-result", "li.result", "article"]),
        ("aacrjournals.org", ["div.search-result", "li.result", "article"]),
        ("ncbi.nlm.nih.gov", ["div.rslt", "div.result", "article"]),
        ("pmc.ncbi.nlm.nih.gov", ["div.results", "div.pmc-search-result", "article"]),
    ]
    for pattern_host, selectors in result_item_selectors:
        if pattern_host not in host:
            continue
        for sel in selectors:
            try:
                tags = soup.select(sel)[:25] if ("[" in sel or "." in sel) else soup.find_all(sel.split("[")[0].split(".")[0].strip() or "div", class_=re.compile(r"result|item|article", re.I))[:25]
            except Exception:
                tags = []
            for tag in tags:
                for link_tag in tag.find_all("a", href=True)[:3]:
                    href = link_tag.get("href", "")
                    if not href or href.startswith("#"):
                        continue
                    full = urljoin(base_url, href)
                    if full in seen:
                        continue
                    full_lower = full.lower()
                    if any(pat in full_lower for pat in ARTICLE_PATH_PATTERNS) or "/doi/" in full_lower or "/article/" in full_lower or "/pub/" in full_lower or "/pmc/" in full_lower:
                        seen.add(full)
                        links.append(full)
        break  # Only one host matches

    # Fallback: div/li with class containing result, item, article -> first link
    if not links:
        for tag in soup.find_all(["div", "li", "article"], class_=re.compile(r"result|item|article|paper|entry|hit", re.I))[:40]:
            for a in tag.find_all("a", href=True)[:2]:
                href = a.get("href", "")
                if href.startswith("http") or href.startswith("/"):
                    full = urljoin(base_url, href)
                    if full not in seen:
                        path = (urlparse(full).path or "").lower()
                        if any(pat in path for pat in ("/article/", "/doi/", "/fulltext", "/content/", "/pub/", "/pmc/", "/view/", "/full")):
                            seen.add(full)
                            links.append(full)
    return links[:25]


def _get_reference_links(soup: "BeautifulSoup", base_url: str) -> List[str]:
    """From an article page, find links to references/citations - ULTRA AGGRESSIVE for journal articles - CONTINUE UNTIL VALUES FOUND."""
    if not HAS_BS4 or not soup:
        return []
    links = []
    # Look for sections with "reference", "citation", "bibliography" - ULTRA AGGRESSIVE
    for tag in soup.find_all(["section", "div", "ul", "ol"], class_=re.compile(r"reference|citation|bibliography|ref", re.I))[:50]:  # Increased from 20
        for a in tag.find_all("a", href=True)[:100]:  # Increased from 50
            href = a.get("href", "")
            if href.startswith("http") or href.startswith("/"):
                full = urljoin(base_url, href)
                if any(pat in full.lower() for pat in REFERENCE_PATTERNS) or "doi.org" in full.lower() or "pubmed" in full.lower() or "pmc" in full.lower() or "ncbi" in full.lower():
                    if full not in links:
                        links.append(full)
    # Also check links with "doi" or "reference" in text - ULTRA AGGRESSIVE
    for a in soup.find_all("a", href=True)[:500]:  # Increased from 300
        href = a.get("href", "")
        text = (a.get_text() or "").lower()
        if ("doi" in text or "reference" in text or "citation" in text or "pubmed" in text or "pmc" in text or "ncbi" in text) and (href.startswith("http") or href.startswith("/")):
            full = urljoin(base_url, href)
            if full not in links:
                links.append(full)
    # Also look for DOI patterns in text (e.g., "doi:10.1234/abc") - MORE AGGRESSIVE
    doi_pattern = re.compile(r'doi[:\s]+(10\.\d+/[^\s\)]+)', re.I)
    for text_elem in soup.find_all(["p", "div", "li", "span", "section"])[:500]:  # Increased from 200
        text = text_elem.get_text() or ""
        for match in doi_pattern.finditer(text):
            doi = match.group(1)
            doi_url = f"https://doi.org/{doi}"
            if doi_url not in links:
                links.append(doi_url)
    # Also look for PubMed IDs (e.g., "PMID: 12345678") - MORE AGGRESSIVE
    pmid_pattern = re.compile(r'pmid[:\s]+(\d+)', re.I)
    for text_elem in soup.find_all(["p", "div", "li", "span", "section"])[:500]:  # Increased from 200
        text = text_elem.get_text() or ""
        for match in pmid_pattern.finditer(text):
            pmid = match.group(1)
            pmid_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            if pmid_url not in links:
                links.append(pmid_url)
    return links[:40]  # Bounded; enough for journal-heavy sources


def _normalize_num(s: str) -> str:
    return s.replace("\u00a0", " ").replace(",", "").strip()


def _is_plausible_datapoint(s: str, allow_small: bool = False) -> bool:
    s_clean = _normalize_num(s).replace(" ", "")
    try:
        n = float(s_clean)
    except ValueError:
        return False
    if 1900 <= n <= 2030 and "." not in s_clean:
        return False
    if n >= 100:
        return True
    if 0.01 <= n <= 100:
        return True
    if allow_small and 1 <= n < 100 and "." in s_clean:
        return True
    return False


def _extract_percentages_from_text(text: str) -> List[Tuple[str, str]]:
    results = []
    for m in PERCENT_PATTERN.finditer(text):
        g1, g2 = m.group(1), m.group(2)
        val = (g1 or g2 or "").strip()
        if val:
            try:
                n = float(val)
                if 0 <= n <= 100:
                    results.append(("percent", f"{val}%"))
            except ValueError:
                pass
    return results


def _extract_numbers_from_text(text: str, require_kpi_context: bool = False) -> List[Tuple[str, str]]:
    results = []
    text_lower = text.lower()
    for m in NUMBER_PATTERN.finditer(text):
        val = m.group(1)
        if not val or not _is_plausible_datapoint(val, allow_small=True):
            continue
        if require_kpi_context:
            start = max(0, m.start() - 150)  # Wider context to capture more journal/org content
            end = min(len(text), m.end() + 150)
            window = text_lower[start:end]
            if not any(kw in window for kw in KPI_KEYWORDS):
                continue
        label = "value"
        start = max(0, m.start() - 80)
        end = min(len(text), m.end() + 80)
        window = text_lower[start:end]
        if "incidence" in window and "prevalence" not in window:
            label = "incidence"
        elif "prevalence" in window:
            label = "prevalence"
        elif "cases" in window or "patients" in window or "new cases" in window:
            label = "cases"
        elif "rate" in window or "per 100" in window:
            label = "rate"
        elif "mortality" in window or "death" in window:
            label = "mortality"
        elif "survival" in window:
            label = "survival"
        results.append((label, val))
    return results


def _extract_from_tables(soup: "BeautifulSoup") -> List[Tuple[str, str]]:
    if not HAS_BS4 or soup is None:
        return []
    results = []
    for table in soup.find_all("table")[:50]:  # Increased from 35 - extract from more tables
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            row_text = " ".join(c.get_text(separator=" ", strip=True) for c in cells).lower()
            for cell in cells:
                text = cell.get_text(separator=" ", strip=True)
                for m in PERCENT_PATTERN.finditer(text):
                    g1, g2 = m.group(1), m.group(2)
                    v = (g1 or g2 or "").strip()
                    if v:
                        try:
                            if 0 <= float(v) <= 100:
                                results.append(("percent", f"{v}%"))
                        except ValueError:
                            pass
                for m in NUMBER_PATTERN.finditer(text):
                    val = m.group(1)
                    if val and _is_plausible_datapoint(val, allow_small=True):
                        label = "value"
                        if "incidence" in row_text and "prevalence" not in row_text:
                            label = "incidence"
                        elif "prevalence" in row_text:
                            label = "prevalence"
                        elif "cases" in row_text or "patients" in row_text:
                            label = "cases"
                        elif "rate" in row_text or "per 100" in row_text:
                            label = "rate"
                        elif "%" in row_text or "percent" in row_text:
                            label = "percent"
                        results.append((label, val))
    return results


def _extract_from_body_aggressive(soup: "BeautifulSoup", body_text: str) -> List[Tuple[str, str]]:
    found = []
    found.extend(_extract_percentages_from_text(body_text))
    found.extend(_extract_numbers_from_text(body_text[:300000], require_kpi_context=True))  # Increased from 120000 - scan more text
    if HAS_BS4 and soup:
        for tag in soup.find_all(["li", "dd", "p", "div", "span", "section", "article", "main", "content"])[:500]:  # Increased from 250 - scan more tags
            t = tag.get_text(separator=" ", strip=True)
            if 10 <= len(t) <= 2000:  # Longer text allowed (increased from 1500)
                found.extend(_extract_percentages_from_text(t))
                found.extend(_extract_numbers_from_text(t, require_kpi_context=False))
    return found


def _extract_from_script_tags(soup: "BeautifulSoup", url: str) -> List[Tuple[str, str]]:
    """Extract datapoints from embedded JSON/JavaScript in script tags - for interactive portals."""
    found = []
    if not HAS_BS4 or not soup:
        return found
    
    # Look for JSON data in script tags
    for script in soup.find_all("script"):
        script_text = script.get_text() or ""
        script_string = str(script)  # Get raw HTML including script tag attributes
        if not script_text and not script_string:
            continue
        
        # Combine text content and raw HTML for better extraction
        combined_text = script_text + " " + script_string
        
        # Try to find JSON objects with epidemiology data
        # Pattern: {"incidence": 21000, "prevalence": 200000, ...}
        json_patterns = [
            r'"incidence"\s*:\s*(\d+(?:\.\d+)?)',
            r'"prevalence"\s*:\s*(\d+(?:\.\d+)?)',
            r'"cases"\s*:\s*(\d+(?:\.\d+)?)',
            r'"value"\s*:\s*(\d+(?:\.\d+)?)',
            r'"count"\s*:\s*(\d+(?:\.\d+)?)',
            r'"number"\s*:\s*(\d+(?:\.\d+)?)',
            r'"rate"\s*:\s*(\d+(?:\.\d+)?)',
            r'"mortality"\s*:\s*(\d+(?:\.\d+)?)',
            r'"newCases"\s*:\s*(\d+(?:\.\d+)?)',
            r'"newCases"\s*:\s*(\d+(?:\.\d+)?)',
            r'"totalCases"\s*:\s*(\d+(?:\.\d+)?)',
            r'"total"\s*:\s*(\d+(?:\.\d+)?)',
        ]
        
        for pattern in json_patterns:
            for m in re.finditer(pattern, combined_text, re.IGNORECASE):
                val = m.group(1)
                if val and _is_plausible_datapoint(val, allow_small=True):
                    label = "value"
                    if "incidence" in pattern.lower() or "newcases" in pattern.lower():
                        label = "incidence"
                    elif "prevalence" in pattern.lower():
                        label = "prevalence"
                    elif "cases" in pattern.lower() or "count" in pattern.lower() or "total" in pattern.lower():
                        label = "cases"
                    elif "mortality" in pattern.lower():
                        label = "mortality"
                    found.append((label, val))
        
        # Look for arrays of numbers that might be data
        # Pattern: [21000, 200000, 5.2, ...]
        array_pattern = r'\[(\d+(?:\.\d+)?(?:\s*,\s*\d+(?:\.\d+)?)*)\]'
        for m in re.finditer(array_pattern, combined_text):
            nums_str = m.group(1)
            for num in re.findall(r'\d+(?:\.\d+)?', nums_str):
                if _is_plausible_datapoint(num, allow_small=True):
                    found.append(("value", num))
        
        # Look for data attributes or meta content
        # Pattern: data-incidence="21000" or content="21000 cases"
        attr_patterns = [
            r'data-incidence=["\'](\d+(?:\.\d+)?)',
            r'data-prevalence=["\'](\d+(?:\.\d+)?)',
            r'data-cases=["\'](\d+(?:\.\d+)?)',
            r'data-value=["\'](\d+(?:\.\d+)?)',
            r'content=["\']([^"\']*\d{3,}[^"\']*)',
        ]
        for pattern in attr_patterns:
            for m in re.finditer(pattern, combined_text, re.IGNORECASE):
                val = m.group(1)
                if val and _is_plausible_datapoint(val, allow_small=True):
                    found.append(("value", val))
        
        # GLOBOCAN-specific: Look for patterns like "21000" or "21,000" near keywords
        # This handles cases where data is in text format within scripts
        globocan_patterns = [
            r'(?:incidence|new\s+cases|cases)\s*[:\-]?\s*(\d{1,3}(?:[,\.]\d{3})*(?:\.\d+)?)',
            r'(?:prevalence|total\s+cases)\s*[:\-]?\s*(\d{1,3}(?:[,\.]\d{3})*(?:\.\d+)?)',
            r'(\d{1,3}(?:[,\.]\d{3})*(?:\.\d+)?)\s*(?:cases|patients|incidence|prevalence)',
        ]
        for pattern in globocan_patterns:
            for m in re.finditer(pattern, combined_text, re.IGNORECASE):
                val = m.group(1).replace(",", "").replace(".", "")
                if val and _is_plausible_datapoint(val, allow_small=False):
                    label = "value"
                    context = m.group(0).lower()
                    if "incidence" in context or "new" in context:
                        label = "incidence"
                    elif "prevalence" in context or "total" in context:
                        label = "prevalence"
                    found.append((label, val))
    
    return found


def _try_data_portal_api(url: str, indication: str, country: str) -> List[Tuple[str, str]]:
    """Try to construct API calls for known data portals."""
    found = []
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    
    # GLOBOCAN: Try alternative endpoints or API-like URLs
    if "gco.iarc.who.int" in host or "iarc.who.int" in host:
        # Try GLOBOCAN API endpoint pattern (if available)
        # Note: GLOBOCAN may require specific cancer type codes
        # Try to find embedded cancer type mappings or use common patterns
        try:
            # First, try to fetch the main page and extract embedded data MORE AGGRESSIVELY
            main_text = _get_page_text(url)
            if main_text and HAS_BS4:
                main_soup = BeautifulSoup(main_text, "html.parser")
                
                # Extract from script tags (JSON/JavaScript data) - ENHANCED
                script_data = _extract_from_script_tags(main_soup, url)
                found.extend(script_data)
                
                # Also extract from the raw HTML text (before script removal)
                # GLOBOCAN often has data in data-* attributes or hidden divs
                raw_html_text = str(main_soup)
                found.extend(_extract_numbers_from_text(raw_html_text[:200000], require_kpi_context=False))
                
                # Look for all data-* attributes
                for tag in main_soup.find_all(attrs=lambda x: x and any(k.startswith('data-') for k in x.keys())):
                    for attr_name, attr_value in tag.attrs.items():
                        if isinstance(attr_value, str) and any(kw in attr_name.lower() for kw in ["data", "value", "count", "number"]):
                            nums = re.findall(r'\d{3,}', str(attr_value))
                            for num in nums:
                                if _is_plausible_datapoint(num, allow_small=False):
                                    found.append(("value", num))
                
                # Look for links to fact sheets or data pages
                for a in main_soup.find_all("a", href=True)[:50]:  # More links
                    href = a.get("href", "").lower()
                    text_lower = (a.get_text() or "").lower()
                    if any(x in href or x in text_lower for x in ["fact", "sheet", "data", "statistics", "incidence", "prevalence", "cancer", "download", "export"]):
                        full_link = urljoin(url, a.get("href", ""))
                        if full_link.startswith("http") and full_link not in [url]:
                            time.sleep(REQUEST_DELAY * 0.5)
                            link_text = _get_page_text(full_link)
                            if link_text and HAS_BS4:
                                link_soup = BeautifulSoup(link_text, "html.parser")
                                link_body = link_soup.get_text(separator=" ", strip=True)
                                found.extend(_extract_numbers_from_text(link_body[:100000], require_kpi_context=True))
                                found.extend(_extract_from_tables(link_soup))
                                # Also extract from script tags in linked pages
                                found.extend(_extract_from_script_tags(link_soup, full_link))
                
                # Try to find and follow API endpoints mentioned in the page
                # GLOBOCAN might have API URLs in script tags
                for script in main_soup.find_all("script"):
                    script_text = str(script)
                    # Look for API URLs
                    api_urls = re.findall(r'https?://[^\s"\'<>]+(?:api|data|fact)[^\s"\'<>]*', script_text, re.IGNORECASE)
                    for api_url in api_urls[:5]:  # Limit to 5 API attempts
                        if api_url.startswith("http"):
                            time.sleep(REQUEST_DELAY * 0.5)
                            api_text = _get_page_text(api_url)
                            if api_text:
                                # Try parsing as JSON first
                                try:
                                    import json
                                    api_json = json.loads(api_text)
                                    # Recursively extract numbers from JSON
                                    def extract_from_json(obj):
                                        nums = []
                                        if isinstance(obj, dict):
                                            for k, v in obj.items():
                                                if isinstance(v, (int, float)) and v >= 100:
                                                    nums.append(("value", str(v)))
                                                elif isinstance(v, (dict, list)):
                                                    nums.extend(extract_from_json(v))
                                        elif isinstance(obj, list):
                                            for item in obj:
                                                nums.extend(extract_from_json(item))
                                        return nums
                                    found.extend(extract_from_json(api_json))
                                except:
                                    # Not JSON, try as HTML/text
                                    if HAS_BS4:
                                        api_soup = BeautifulSoup(api_text, "html.parser")
                                        api_body = api_soup.get_text(separator=" ", strip=True)
                                        found.extend(_extract_numbers_from_text(api_body[:50000], require_kpi_context=True))
            
            # Common GLOBOCAN patterns - try to access data endpoints
            indication_clean = indication.lower().replace(" ", "-").replace("(", "").replace(")", "").replace(",", "").replace("chronic-lymphocytic-leukemia", "cll")
            country_clean = country.lower().replace(" ", "-") if country else ""
            
            # Try multiple GLOBOCAN URL patterns
            api_patterns = []
            if indication:
                # Try various cancer name formats
                cancer_codes = [
                    indication_clean,
                    indication_clean.replace("-", ""),
                    "cll" if "lymphocytic" in indication.lower() else indication_clean,
                    "chronic-lymphocytic-leukemia",
                ]
                for code in cancer_codes:
                    api_patterns.extend([
                        f"https://gco.iarc.who.int/today/data/fact_sheets/cancers/{code}-fact-sheet.pdf",
                        f"https://gco.iarc.who.int/today/data/fact_sheets/cancers/{code}-fact-sheet.html",
                    ])
            if country:
                country_codes = [country_clean, country_clean.replace("-", "")]
                for code in country_codes:
                    api_patterns.extend([
                        f"https://gco.iarc.who.int/today/data/fact_sheets/populations/{code}-fact-sheet.pdf",
                        f"https://gco.iarc.who.int/today/data/fact_sheets/populations/{code}-fact-sheet.html",
                    ])
            
            for api_url in api_patterns[:10]:  # Limit attempts
                time.sleep(REQUEST_DELAY * 0.5)
                text = _get_page_text(api_url)
                if text:
                    # Try to extract from PDF text or HTML
                    soup = BeautifulSoup(text, "html.parser") if HAS_BS4 else None
                    if soup:
                        body_text = soup.get_text() if soup.find("body") else text[:50000]
                        found.extend(_extract_numbers_from_text(body_text, require_kpi_context=True))
                        found.extend(_extract_from_tables(soup))
                        found.extend(_extract_from_script_tags(soup, api_url))
                    else:
                        # Even if not HTML, try extracting numbers from raw text
                        found.extend(_extract_numbers_from_text(text[:50000], require_kpi_context=True))
        except Exception:
            pass
    
    # SEER: Try SEER Stat API or data endpoints
    if "seer.cancer.gov" in host:
        try:
            # SEER often has data in specific endpoints
            seer_patterns = [
                f"https://seer.cancer.gov/statfacts/html/{indication.lower().replace(' ', '').replace('(', '').replace(')', '')}.html",
                f"https://seer.cancer.gov/statistics-network/explorer/application.html",
            ]
            for api_url in seer_patterns:
                time.sleep(REQUEST_DELAY * 0.5)
                text = _get_page_text(api_url)
                if text and HAS_BS4:
                    soup = BeautifulSoup(text, "html.parser")
                    found.extend(_extract_from_tables(soup))
                    body_text = soup.get_text(separator=" ", strip=True)
                    found.extend(_extract_numbers_from_text(body_text[:100000], require_kpi_context=True))
        except Exception:
            pass
    
    return found


def _is_data_portal(url: str) -> bool:
    """Check if URL is an interactive data portal."""
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower().replace("www.", "")
        path = (parsed.path or "").lower()
        return any(h in host for h in DATA_PORTAL_HOSTS) or any(p in path for p in DATA_PORTAL_PATTERNS)
    except Exception:
        return False


def _extract_datapoints_from_page(soup: "BeautifulSoup", body_text: str, url: str = "") -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    found.extend(_extract_from_tables(soup))
    found.extend(_extract_from_body_aggressive(soup, body_text))
    # Extract from script tags (for interactive portals)
    found.extend(_extract_from_script_tags(soup, url))
    # Enhanced extraction for journal articles
    if url and _is_journal_article_url(url):
        found.extend(_extract_from_journal_article(soup, url))
    # Per-host extraction for org/reference sites (Cancer.net, Medscape, NORD, etc.)
    if url and _is_org_site(url):
        found.extend(_extract_from_org_site(soup, url))
    return found


def _fetch_and_extract(url: str, retry: int = 0) -> List[Tuple[str, str]]:
    """Fetch URL and extract - with retry. Preserves script tags for data portal extraction."""
    text = _get_page_text(url, retry=retry)
    if not text:
        return []
    try:
        soup = BeautifulSoup(text, "html.parser")
        # Extract from script tags BEFORE removing them (for data portals)
        script_data = _extract_from_script_tags(soup, url) if _is_data_portal(url) else []
        # Now remove non-content tags (but keep script tags for now if it's a portal)
        for tag in soup(["style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        body = soup.find("body") or soup
        body_text = body.get_text(separator=" ", strip=True) if body else ""
        found = _extract_datapoints_from_page(soup, body_text, url)
        found.extend(script_data)
        return found
    except Exception:
        if retry < MAX_RETRIES:
            time.sleep(REQUEST_DELAY)
            return _fetch_and_extract(url, retry + 1)
        return []


def _dedupe_and_format(found: List[Tuple[str, str]], max_values: int = 50) -> Optional[str]:
    seen_vals = set()
    ordered = []
    for label in ("incidence", "prevalence", "cases", "rate", "percent", "mortality", "survival", "value"):
        for lbl, val in found:
            if lbl != label:
                continue
            vnorm = val.replace(",", "").replace(" ", "").replace("%", "")
            if vnorm in seen_vals:
                continue
            seen_vals.add(vnorm)
            ordered.append((lbl, val))
    if not ordered:
        return None
    ordered = ordered[:max_values]
    parts = [f"{v} ({lbl})" for lbl, v in ordered]
    return "; ".join(parts) if len(parts) > 1 else ordered[0][1]


def extract_values_from_url(url: str, max_depth: int = 6, visited: Optional[Set[str]] = None, min_datapoints: int = 2, indication: str = "", country: str = "", deadline: Optional[float] = None) -> Optional[str]:
    """
    Bounded multi-level extraction: gets datapoints from page and limited link-following.
    max_depth: when <= 0, only extract from current page (no link following). Recursive calls use max_depth - 1.
    max_visited: stop following new links after MAX_VISITED_PER_RUN URLs per run (hard cap).
    deadline: if set (Unix timestamp), return None once time.time() >= deadline to cap total run time.
    """
    if not HAS_BS4:
        return None
    if deadline is not None and time.time() >= deadline:
        return None
    if visited is None:
        visited = set()
    if url in visited:
        return None
    visited.add(url)
    # Hard cap: do not follow more links once we've hit the limit (still extract from current page)
    at_visit_cap = len(visited) >= MAX_VISITED_PER_RUN
    # When max_depth <= 0, only extract from current page (no recursion into links)
    no_more_depth = max_depth <= 0
    can_follow_links = not (at_visit_cap or no_more_depth)
    next_depth = max_depth - 1

    text = _get_page_text(url)
    if not text:
        # Retry once
        time.sleep(REQUEST_DELAY)
        text = _get_page_text(url, retry=1)
        if not text:
            return None

    try:
        soup = BeautifulSoup(text, "html.parser")
        # Extract from script tags BEFORE removing them (for data portals)
        script_data = _extract_from_script_tags(soup, url) if _is_data_portal(url) else []
        # Now remove non-content tags
        for tag in soup(["style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        body = soup.find("body") or soup
        body_text = body.get_text(separator=" ", strip=True) if body else ""
    except Exception:
        return None

    found: List[Tuple[str, str]] = _extract_datapoints_from_page(soup, body_text, url)
    # Add script-extracted data for portals
    if script_data:
        found.extend(script_data)

    # Strategy 0: If this is a data portal (GLOBOCAN, SEER, etc.), try special extraction
    if _is_data_portal(url) and len(found) < min_datapoints:
        # Extract from script tags (JSON/JavaScript data)
        script_data = _extract_from_script_tags(soup, url)
        found.extend(script_data)
        
        # Try API endpoints for known portals (use passed indication/country)
        api_data = _try_data_portal_api(url, indication or "", country or "")
        found.extend(api_data)
        
        # Look for download/export links that might have data
        download_links = []
        for a in soup.find_all("a", href=True)[:50]:
            href = a.get("href", "").lower()
            text = (a.get_text() or "").lower()
            if any(x in href or x in text for x in ["download", "export", "csv", "excel", "data", "statistics", "fact", "sheet"]):
                full = urljoin(url, a.get("href", ""))
                if full not in visited and full.startswith("http"):
                    download_links.append(full)
        
        # Try downloading data files
        for dl_link in download_links[:3]:
            if dl_link not in visited:
                time.sleep(REQUEST_DELAY)
                dl_text = _get_page_text(dl_link)
                if dl_text and HAS_BS4:
                    try:
                        dl_soup = BeautifulSoup(dl_text, "html.parser")
                        dl_body = dl_soup.get_text(separator=" ", strip=True)
                        found.extend(_extract_numbers_from_text(dl_body[:50000], require_kpi_context=True))
                    except Exception:
                        pass

    # Strategy 1: If this is a search page, follow a few result links
    if can_follow_links and _is_search_url(url):
        result_links = _get_search_result_links(soup, url)
        for link in result_links[:6]:
            if link in visited or len(visited) >= MAX_VISITED_PER_RUN:
                break
            time.sleep(REQUEST_DELAY)
            sub_found = _fetch_and_extract(link)
            found.extend(sub_found)
            if len(found) < min_datapoints:
                sub_result = extract_values_from_url(link, max_depth=next_depth, visited=visited, min_datapoints=min_datapoints, indication=indication, country=country, deadline=deadline)
                if sub_result:
                    found.append(("value", sub_result.split(";")[0].split("(")[0].strip()))
            if len(found) >= min_datapoints:
                break

    # Strategy 2: If journal search page, follow a bounded set of articles and refs
    if can_follow_links and _is_journal_search_url(url):
        article_links = _get_journal_search_result_links(soup, url)
        if not article_links:
            article_links = _get_all_links_from_soup(soup, url, max_links=30, filter_patterns=ARTICLE_PATH_PATTERNS)
        for result_div in soup.find_all(["div", "article", "li"], class_=re.compile(r"result|item|article|paper|entry", re.I))[:40]:
            for a in result_div.find_all("a", href=True)[:5]:
                href = a.get("href", "")
                if href.startswith("http") or href.startswith("/"):
                    full = urljoin(url, href)
                    if any(pat in full.lower() for pat in ARTICLE_PATH_PATTERNS) and full not in article_links:
                        article_links.append(full)
        for link in article_links[:18]:
            if link in visited or len(visited) >= MAX_VISITED_PER_RUN:
                break
            time.sleep(REQUEST_DELAY)
            sub_found = _fetch_and_extract(link)
            found.extend(sub_found)
            if _is_journal_article_url(link):
                link_text = _get_page_text(link)
                if link_text and HAS_BS4:
                    link_soup = BeautifulSoup(link_text, "html.parser")
                    journal_data = _extract_from_journal_article(link_soup, link)
                    found.extend(journal_data)
                    full_text = link_soup.get_text(separator=" ", strip=True)
                    if len(full_text) > 1000:
                        results_conclusions_text = ""
                        for section in link_soup.find_all(["section", "div", "h2", "h3"]):
                            section_text = section.get_text(separator=" ", strip=True).lower()
                            if any(kw in section_text for kw in ["result", "conclusion", "observation", "finding"]):
                                results_conclusions_text += " " + section.get_text(separator=" ", strip=True)
                        if results_conclusions_text:
                            found.extend(_extract_numbers_from_text(results_conclusions_text[:150000], require_kpi_context=True))
                            found.extend(_extract_percentages_from_text(results_conclusions_text))
                    article_ref_links = _get_reference_links(link_soup, link)
                    for ref_link in article_ref_links[:15]:
                        if ref_link in visited or len(visited) >= MAX_VISITED_PER_RUN or len(found) >= min_datapoints:
                            break
                        time.sleep(REQUEST_DELAY * 0.8)
                        ref_text = _get_page_text(ref_link)
                        if ref_text and HAS_BS4:
                            ref_soup = BeautifulSoup(ref_text, "html.parser")
                            ref_found = _fetch_and_extract(ref_link)
                            found.extend(ref_found)
                            if _is_journal_article_url(ref_link):
                                found.extend(_extract_from_journal_article(ref_soup, ref_link))
                        if len(found) >= min_datapoints:
                            break
                    if len(found) < min_datapoints:
                        sub_result = extract_values_from_url(link, max_depth=next_depth, visited=visited, min_datapoints=min_datapoints, indication=indication, country=country, deadline=deadline)
                        if sub_result:
                            found.append(("value", sub_result.split(";")[0].split("(")[0].strip()))
            if len(found) >= min_datapoints:
                break

    # Strategy 3: If article page (especially journal articles), DEEP DIVE and extract comprehensively
    # CRITICAL: Also deep-dive into REFERENCES - they may contain insights/values even if main article doesn't
    if any(pat in url.lower() for pat in ARTICLE_PATH_PATTERNS):
        # CRITICAL: Enhanced extraction for journal articles - DEEP DIVE into RESULTS, CONCLUSIONS, OBSERVATIONS
        if _is_journal_article_url(url):
            # Deep-dive extraction from RESULTS, CONCLUSIONS, OBSERVATIONS
            journal_data = _extract_from_journal_article(soup, url)
            found.extend(journal_data)
            # Also extract from full article text for triangulation
            full_text = soup.get_text(separator=" ", strip=True)
            if len(full_text) > 1000:
                # Focus on sections with results/conclusions/observations keywords
                results_conclusions_text = ""
                for section in soup.find_all(["section", "div", "h2", "h3", "h4"]):
                    section_text = section.get_text(separator=" ", strip=True).lower()
                    if any(kw in section_text for kw in ["result", "conclusion", "observation", "finding", "summary"]):
                        results_conclusions_text += " " + section.get_text(separator=" ", strip=True)
                if results_conclusions_text:
                    found.extend(_extract_numbers_from_text(results_conclusions_text[:300000], require_kpi_context=True))
                    found.extend(_extract_percentages_from_text(results_conclusions_text))
        
        # Follow a bounded set of references
        ref_links = _get_reference_links(soup, url)
        for ref_section in soup.find_all(["section", "div", "ol", "ul"], class_=re.compile(r"reference|citation|bibliography|ref", re.I))[:20]:
            for a in ref_section.find_all("a", href=True)[:25]:
                href = a.get("href", "")
                if href.startswith("http") or href.startswith("/"):
                    full = urljoin(url, href)
                    if full not in ref_links and (any(pat in full.lower() for pat in REFERENCE_PATTERNS) or "doi.org" in full.lower() or "pubmed" in full.lower() or "pmc" in full.lower() or "ncbi" in full.lower()):
                        ref_links.append(full)
        if can_follow_links:
            for link in ref_links[:25]:
                if link in visited or len(visited) >= MAX_VISITED_PER_RUN or len(found) >= min_datapoints:
                    break
                time.sleep(REQUEST_DELAY)
                sub_found = _fetch_and_extract(link)
                found.extend(sub_found)
                if _is_journal_article_url(link):
                    link_text = _get_page_text(link)
                    if link_text and HAS_BS4:
                        link_soup = BeautifulSoup(link_text, "html.parser")
                        found.extend(_extract_from_journal_article(link_soup, link))
                        ref_full_text = link_soup.get_text(separator=" ", strip=True)
                        if len(ref_full_text) > 1000:
                            ref_results_conclusions_text = ""
                            for section in link_soup.find_all(["section", "div", "h2", "h3", "h4"]):
                                section_text = section.get_text(separator=" ", strip=True).lower()
                                if any(kw in section_text for kw in ["result", "conclusion", "observation", "finding", "summary"]):
                                    ref_results_conclusions_text += " " + section.get_text(separator=" ", strip=True)
                            if ref_results_conclusions_text:
                                found.extend(_extract_numbers_from_text(ref_results_conclusions_text[:150000], require_kpi_context=True))
                                found.extend(_extract_percentages_from_text(ref_results_conclusions_text))
                        ref_ref_links = _get_reference_links(link_soup, link)
                        for ref_ref_link in ref_ref_links[:10]:
                            if ref_ref_link in visited or len(visited) >= MAX_VISITED_PER_RUN or len(found) >= min_datapoints:
                                break
                            time.sleep(REQUEST_DELAY * 0.7)
                            ref_ref_text = _get_page_text(ref_ref_link)
                            if ref_ref_text and HAS_BS4:
                                ref_ref_soup = BeautifulSoup(ref_ref_text, "html.parser")
                                found.extend(_fetch_and_extract(ref_ref_link))
                                if _is_journal_article_url(ref_ref_link):
                                    found.extend(_extract_from_journal_article(ref_ref_soup, ref_ref_link))
                                ref_ref_ref_links = _get_reference_links(ref_ref_soup, ref_ref_link)
                                for ref_ref_ref_link in ref_ref_ref_links[:6]:
                                    if ref_ref_ref_link in visited or len(visited) >= MAX_VISITED_PER_RUN or len(found) >= min_datapoints:
                                        break
                                    time.sleep(REQUEST_DELAY * 0.6)
                                    ref_ref_ref_text = _get_page_text(ref_ref_ref_link)
                                    if ref_ref_ref_text and HAS_BS4:
                                        ref_ref_ref_soup = BeautifulSoup(ref_ref_ref_text, "html.parser")
                                        found.extend(_fetch_and_extract(ref_ref_ref_link))
                                        if _is_journal_article_url(ref_ref_ref_link):
                                            found.extend(_extract_from_journal_article(ref_ref_ref_soup, ref_ref_ref_link))
                            if len(found) >= min_datapoints:
                                break
                if len(found) < min_datapoints:
                    sub_result = extract_values_from_url(link, max_depth=next_depth, visited=visited, min_datapoints=1, indication=indication, country=country, deadline=deadline)
                    if sub_result:
                        found.append(("value", sub_result.split(";")[0].split("(")[0].strip()))
                if len(found) >= min_datapoints:
                    break

    # Strategy 4: If company site, scan a few epidemiology pages
    if can_follow_links and _is_company_site(url) and len(found) < min_datapoints:
        company_links = _get_all_links_from_soup(soup, url, max_links=10, filter_patterns=COMPANY_DATA_PATTERNS)
        for link in company_links:
            if link in visited or len(visited) >= MAX_VISITED_PER_RUN:
                break
            time.sleep(REQUEST_DELAY)
            sub_found = _fetch_and_extract(link)
            found.extend(sub_found)
            if len(found) < min_datapoints:
                sub_result = extract_values_from_url(link, max_depth=next_depth, visited=visited, min_datapoints=1, indication=indication, country=country, deadline=deadline)
                if sub_result:
                    found.append(("value", sub_result.split(";")[0].split("(")[0].strip()))
            if len(found) >= min_datapoints:
                break

    # Strategy 5: Try promising links with epidemiology keywords (fallback)
    if can_follow_links and len(found) < min_datapoints:
        all_links = _get_all_links_from_soup(soup, url, max_links=15)
        for link in all_links:
            if link in visited or len(visited) >= MAX_VISITED_PER_RUN:
                break
            link_lower = link.lower()
            link_text = ""
            try:
                for a in soup.find_all("a", href=True):
                    if a.get("href") == link or link in a.get("href", ""):
                        link_text = (a.get_text() or "").lower()
                        break
            except Exception:
                pass
            combined_check = link_lower + " " + link_text
            if any(kw in combined_check for kw in ["epidemiology", "incidence", "prevalence", "statistics", "data", "burden", "patient", "disease", "cancer", "rate", "mortality", "survival", "cases", "study", "research", "publication"]):
                time.sleep(REQUEST_DELAY)
                sub_found = _fetch_and_extract(link)
                found.extend(sub_found)
                if len(found) < min_datapoints:
                    sub_result = extract_values_from_url(link, max_depth=next_depth, visited=visited, min_datapoints=1, indication=indication, country=country, deadline=deadline)
                    if sub_result:
                        found.append(("value", sub_result.split(";")[0].split("(")[0].strip()))
                if len(found) >= min_datapoints:
                    break

    # Strategy 6: If still not enough, try a few more promising links (bounded)
    if can_follow_links and len(found) < min_datapoints:
        promising = _get_all_links_from_soup(soup, url, max_links=15)
        for link in promising[:5]:
            if link in visited or len(visited) >= MAX_VISITED_PER_RUN:
                break
            time.sleep(REQUEST_DELAY * 1.2)
            sub_result = extract_values_from_url(link, max_depth=next_depth, visited=visited, min_datapoints=1, indication=indication, country=country, deadline=deadline)
            if sub_result:
                found.append(("value", sub_result.split(";")[0].split("(")[0].strip()))
            if len(found) >= min_datapoints:
                break

    # Strategy 7: Last-resort follow a few more links (bounded)
    if can_follow_links and len(found) < min_datapoints:
        desperate_links = _get_all_links_from_soup(soup, url, max_links=30)
        for link in desperate_links[:8]:
            if link in visited or len(visited) >= MAX_VISITED_PER_RUN:
                break
            time.sleep(REQUEST_DELAY * 0.8)
            try:
                sub_found = _fetch_and_extract(link)
                found.extend(sub_found)
                if len(found) < min_datapoints:
                    sub_result = extract_values_from_url(link, max_depth=next_depth, visited=visited, min_datapoints=1, indication=indication, country=country, deadline=deadline)
                    if sub_result:
                        found.append(("value", sub_result.split(";")[0].split("(")[0].strip()))
                if len(found) >= min_datapoints:
                    break
            except Exception:
                continue
    
    # Strategy 8: FINAL FALLBACK - Extract from raw HTML even more aggressively
    if len(found) < min_datapoints:
        try:
            raw_html = str(soup)
            # Extract from raw HTML (up to 500KB)
            found.extend(_extract_numbers_from_text(raw_html[:500000], require_kpi_context=False))
            # Also try extracting from all text nodes
            for tag in soup.find_all(["p", "div", "span", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6"])[:500]:
                tag_text = tag.get_text(separator=" ", strip=True)
                if len(tag_text) > 20:  # Only meaningful text
                    found.extend(_extract_numbers_from_text(tag_text, require_kpi_context=False))
        except:
            pass
    
    # Strategy 9: Journal fallback - bounded set of articles and refs
    if can_follow_links and len(found) < min_datapoints and (_is_journal_article_url(url) or _is_journal_search_url(url) or any(h in url.lower() for h in JOURNAL_HOSTS)):
        all_journal_links = []
        for a in soup.find_all("a", href=True)[:150]:
            href = a.get("href", "")
            if href.startswith("http") or href.startswith("/"):
                full = urljoin(url, href)
                if _is_journal_article_url(full) and full not in visited:
                    all_journal_links.append(full)
        for journal_link in all_journal_links[:15]:
            if len(found) >= min_datapoints or journal_link in visited or len(visited) >= MAX_VISITED_PER_RUN:
                break
            time.sleep(REQUEST_DELAY)
            journal_text = _get_page_text(journal_link)
            if journal_text and HAS_BS4:
                journal_soup = BeautifulSoup(journal_text, "html.parser")
                found.extend(_extract_from_journal_article(journal_soup, journal_link))
                journal_full_text = journal_soup.get_text(separator=" ", strip=True)
                if len(journal_full_text) > 1000:
                    journal_results_text = ""
                    for section in journal_soup.find_all(["section", "div", "h2", "h3"]):
                        section_text = section.get_text(separator=" ", strip=True).lower()
                        if any(kw in section_text for kw in ["result", "conclusion", "observation", "finding"]):
                            journal_results_text += " " + section.get_text(separator=" ", strip=True)
                    if journal_results_text:
                        found.extend(_extract_numbers_from_text(journal_results_text[:150000], require_kpi_context=True))
                        found.extend(_extract_percentages_from_text(journal_results_text))
                journal_refs = _get_reference_links(journal_soup, journal_link)
                for ref_link in journal_refs[:20]:
                    if len(found) >= min_datapoints or ref_link in visited or len(visited) >= MAX_VISITED_PER_RUN:
                        break
                    time.sleep(REQUEST_DELAY * 0.8)
                    ref_text = _get_page_text(ref_link)
                    if ref_text and HAS_BS4:
                        ref_soup = BeautifulSoup(ref_text, "html.parser")
                        found.extend(_fetch_and_extract(ref_link))
                        if _is_journal_article_url(ref_link):
                            found.extend(_extract_from_journal_article(ref_soup, ref_link))
                    if len(found) >= min_datapoints:
                        break
            if len(found) >= min_datapoints:
                break

    # Return more values - we want comprehensive extraction
    max_vals = 50 if len(found) > 30 else 40  # Increased from 30/25
    return _dedupe_and_format(found, max_values=max_vals)


def deep_dive_link_record(url: str, delay: bool = True, indication: str = "", country: str = "", deadline: Optional[float] = None) -> Optional[str]:
    """
    Bounded extraction: get datapoints from page and limited link-following (max_depth=6, ~55 URLs max per attempt).
    Two attempts: first prefer 2+ datapoints, then accept 1. deadline: if set, stop once time passes (run-time cap).
    """
    if deadline is not None and time.time() >= deadline:
        return None
    if delay:
        time.sleep(REQUEST_DELAY)
    if deadline is not None and time.time() >= deadline:
        return None

    if _is_data_portal(url):
        api_data = _try_data_portal_api(url, indication or "", country or "")
        if api_data:
            formatted = _dedupe_and_format(api_data, max_values=20)
            if formatted:
                return formatted

    if deadline is not None and time.time() >= deadline:
        return None
    # Attempt 1: prefer multiple datapoints
    result = extract_values_from_url(url, max_depth=6, min_datapoints=2, indication=indication or "", country=country or "", deadline=deadline)
    if result:
        return result

    if deadline is not None and time.time() >= deadline:
        return None
    # Attempt 2: accept single datapoint
    result = extract_values_from_url(url, max_depth=6, min_datapoints=1, indication=indication or "", country=country or "", deadline=deadline)
    return result
