#!/usr/bin/env python3
"""
Standalone web scraper for epidemiology data.
Simple Python script version (alternative to notebook).
"""

import re
import time
import pandas as pd
from typing import List, Optional, Tuple, Set
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ===== CONFIGURATION =====
INDICATION = "CLL (Chronic Lymphocytic Leukemia)"
COUNTRY = "US"

SOURCE_URLS = [
    "https://scholar.google.com/scholar?q=CLL+Chronic+Lymphocytic+Leukemia+epidemiology+US",
    "https://www.thelancet.com/action/doSearch?AllField=CLL+epidemiology",
    "https://www.nature.com/search?q=CLL+epidemiology",
    "https://www.cancer.gov/about-cancer/understanding/statistics",
    "https://seer.cancer.gov/statistics-network/explorer",
    # Add more URLs here
]

REQUEST_DELAY = 1.0
REQUEST_TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (compatible; EpidemiologyScraper/1.0)"

# ===== PATTERNS =====
SEARCH_HOSTS = ("scholar.google.com", "google.com", "bing.com")
JOURNAL_HOSTS = ("thelancet.com", "nejm.org", "nature.com", "bmj.com", "sciencedirect.com")
COMPANY_HOSTS = ("pfizer.com", "merck.com", "novartis.com", "roche.com")

ARTICLE_PATTERNS = ("/article/", "/articles/", "/fulltext", "/doi/", "/journals/")
KPI_KEYWORDS = ("incidence", "prevalence", "cases", "patients", "rate", "percent", "%", "epidemiology")

NUMBER_PATTERN = re.compile(r"\b(\d{1,3}(?:[, \u00a0]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\b")
PERCENT_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*%|\b(\d+(?:\.\d+)?)\s+percent\b")


def fetch_page(url: str, retry: int = 0) -> Optional[str]:
    """Fetch page with retry logic."""
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}, allow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as e:
        if retry < 2:
            time.sleep(REQUEST_DELAY * (retry + 1))
            return fetch_page(url, retry + 1)
        print(f"  ✗ Failed to fetch {url}: {e}")
        return None


def is_plausible_datapoint(s: str) -> bool:
    """Check if number looks like epidemiology data."""
    s_clean = s.replace(",", "").replace(" ", "").strip()
    try:
        n = float(s_clean)
        if 1900 <= n <= 2030 and "." not in s_clean:
            return False  # Year
        return n >= 100 or (0.01 <= n <= 100)  # Counts or rates/percentages
    except ValueError:
        return False


def extract_from_tables(soup: BeautifulSoup) -> List[Tuple[str, str]]:
    """Extract datapoints from HTML tables."""
    results = []
    for table in soup.find_all("table")[:30]:
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            row_text = " ".join(c.get_text(strip=True) for c in cells).lower()
            if any(kw in row_text for kw in KPI_KEYWORDS):
                for cell in cells:
                    text = cell.get_text(strip=True)
                    # Percentages
                    for m in PERCENT_PATTERN.finditer(text):
                        val = (m.group(1) or m.group(2) or "").strip()
                        if val:
                            try:
                                if 0 <= float(val) <= 100:
                                    results.append(("percent", f"{val}%"))
                            except ValueError:
                                pass
                    # Numbers
                    for m in NUMBER_PATTERN.finditer(text):
                        val = m.group(1)
                        if val and is_plausible_datapoint(val):
                            label = "value"
                            if "incidence" in row_text:
                                label = "incidence"
                            elif "prevalence" in row_text:
                                label = "prevalence"
                            elif "cases" in row_text or "patients" in row_text:
                                label = "cases"
                            results.append((label, val))
    return results


def extract_from_text(text: str) -> List[Tuple[str, str]]:
    """Extract datapoints from body text."""
    results = []
    text_lower = text.lower()
    
    # Percentages
    for m in PERCENT_PATTERN.finditer(text):
        val = (m.group(1) or m.group(2) or "").strip()
        if val:
            try:
                if 0 <= float(val) <= 100:
                    results.append(("percent", f"{val}%"))
            except ValueError:
                pass
    
    # Numbers near KPI keywords
    for m in NUMBER_PATTERN.finditer(text):
        val = m.group(1)
        if not val or not is_plausible_datapoint(val):
            continue
        start = max(0, m.start() - 80)
        end = min(len(text), m.end() + 80)
        window = text_lower[start:end]
        if any(kw in window for kw in KPI_KEYWORDS):
            label = "value"
            if "incidence" in window:
                label = "incidence"
            elif "prevalence" in window:
                label = "prevalence"
            elif "cases" in window or "patients" in window:
                label = "cases"
            results.append((label, val))
    
    return results


def get_links_from_page(soup: BeautifulSoup, base_url: str, max_links: int = 10, filter_patterns: Optional[List[str]] = None) -> List[str]:
    """Extract relevant links from page."""
    links = []
    base_netloc = urlparse(base_url).netloc.lower().replace("www.", "")
    
    for a in soup.find_all("a", href=True)[:150]:
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full = urljoin(base_url, href)
        try:
            p = urlparse(full)
            netloc = p.netloc.lower().replace("www.", "")
            path = p.path.lower()
            if base_netloc not in netloc:
                continue
            if filter_patterns:
                if not any(pat in path or pat in href.lower() for pat in filter_patterns):
                    continue
            if full not in links:
                links.append(full)
                if len(links) >= max_links:
                    break
        except Exception:
            continue
    return links


def scrape_url(url: str, max_depth: int = 3, visited: Optional[Set[str]] = None, min_datapoints: int = 2) -> List[Tuple[str, str]]:
    """Persistent scraping: follows links until datapoints found."""
    if visited is None:
        visited = set()
    if url in visited or max_depth <= 0:
        return []
    visited.add(url)
    
    print(f"  → Scraping: {url[:70]}...")
    text = fetch_page(url)
    if not text:
        return []
    
    try:
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        body = soup.find("body") or soup
        body_text = body.get_text(separator=" ", strip=True) if body else ""
    except Exception as e:
        print(f"  ✗ Error parsing: {e}")
        return []
    
    # Extract from current page
    found = []
    found.extend(extract_from_tables(soup))
    found.extend(extract_from_text(body_text[:100000]))
    
    if found:
        print(f"    ✓ Found {len(found)} datapoints on page")
    
    # If search/journal page, follow links
    host = urlparse(url).netloc.lower()
    
    if len(found) < min_datapoints and max_depth > 1:
        # Google Scholar / search results
        if any(h in host for h in SEARCH_HOSTS):
            print("    → Following search result links...")
            result_links = get_links_from_page(soup, url, max_links=5)
            for link in result_links:
                if link not in visited:
                    time.sleep(REQUEST_DELAY)
                    found.extend(scrape_url(link, max_depth - 1, visited, min_datapoints))
                    if len(found) >= min_datapoints:
                        break
        
        # Journal sites
        if any(h in host for h in JOURNAL_HOSTS):
            print("    → Following article links...")
            article_links = get_links_from_page(soup, url, max_links=5, filter_patterns=list(ARTICLE_PATTERNS))
            for link in article_links:
                if link not in visited:
                    time.sleep(REQUEST_DELAY)
                    found.extend(scrape_url(link, max_depth - 1, visited, min_datapoints))
                    if len(found) >= min_datapoints:
                        break
    
    return found


def main():
    """Main scraping loop."""
    print("=" * 80)
    print("EPIDEMIOLOGY WEB SCRAPER")
    print("=" * 80)
    print(f"Indication: {INDICATION}")
    print(f"Country: {COUNTRY}")
    print(f"Sources: {len(SOURCE_URLS)}")
    print("=" * 80)
    
    all_results = []
    
    for idx, source_url in enumerate(SOURCE_URLS, 1):
        print(f"\n[{idx}/{len(SOURCE_URLS)}] Processing: {source_url[:70]}...")
        
        datapoints = scrape_url(source_url, max_depth=4, min_datapoints=2)
        
        # Deduplicate
        seen = set()
        unique_datapoints = []
        for label, value in datapoints:
            key = (label, value.replace(",", "").replace(" ", "").replace("%", ""))
            if key not in seen:
                seen.add(key)
                unique_datapoints.append((label, value))
        
        # Format result
        if unique_datapoints:
            value_str = "; ".join([f"{v} ({l})" for l, v in unique_datapoints[:15]])
        else:
            value_str = "No datapoints found"
        
        all_results.append({
            "indication": INDICATION,
            "country": COUNTRY,
            "source_url": source_url,
            "value": value_str,
            "datapoint_count": len(unique_datapoints),
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        print(f"  ✓ Extracted {len(unique_datapoints)} unique datapoints")
        if unique_datapoints:
            preview = value_str[:100] + "..." if len(value_str) > 100 else value_str
            print(f"  Preview: {preview}")
        
        time.sleep(REQUEST_DELAY)
    
    # Create DataFrame and save
    df = pd.DataFrame(all_results)
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total sources processed: {len(df)}")
    print(f"Total datapoints extracted: {df['datapoint_count'].sum()}")
    print(f"Sources with datapoints: {(df['datapoint_count'] > 0).sum()}")
    
    # Save to CSV
    output_file = f"epidemiology_scraped_{INDICATION.replace(' ', '_')}_{COUNTRY}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(output_file, index=False)
    print(f"\n✓ Results saved to: {output_file}")
    
    # Display results
    print("\nResults:")
    print(df.to_string(index=False))
    
    return df


if __name__ == "__main__":
    df = main()
