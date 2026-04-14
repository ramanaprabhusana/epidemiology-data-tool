# Web Scraping Notebook for Epidemiology Data

A simple, standalone Jupyter notebook for web scraping epidemiology datapoints from public sources.

## Features

- **Multi-level link following**: Follows search results → articles → references
- **Persistent extraction**: Keeps trying until datapoints are found
- **Extracts**: Numbers, percentages, rates from tables and text
- **Supports**: Google Scholar, journal sites, company websites
- **Output**: CSV file with extracted values

## Setup

1. **Install dependencies:**
   ```bash
   pip install requests beautifulsoup4 pandas lxml jupyter
   ```

2. **Launch Jupyter:**
   ```bash
   jupyter notebook epidemiology_web_scraper.ipynb
   ```

3. **Configure:**
   - Set `INDICATION` (e.g., "CLL (Chronic Lymphocytic Leukemia)")
   - Set `COUNTRY` (e.g., "US")
   - Add source URLs to `SOURCE_URLS` list

4. **Run all cells** (Cell → Run All)

## How It Works

1. **Fetches each source URL** with retry logic
2. **Extracts datapoints** from:
   - HTML tables (scans for incidence, prevalence, cases, rates)
   - Body text (finds numbers near KPI keywords)
   - Percentages (X% or X percent)
3. **Follows links** if it's a search/journal page:
   - Google Scholar → follows top 5 result links
   - Journal sites → follows article links
   - Recursively extracts from followed pages (up to 4 levels deep)
4. **Deduplicates** and formats results
5. **Saves to CSV** with timestamp

## Example Output

```
indication,country,source_url,value,datapoint_count,scraped_at
CLL (Chronic Lymphocytic Leukemia),US,https://scholar.google.com/...,21000 (incidence); 200000 (prevalence); 5.2% (percent),3,2024-02-11 10:30:00
```

## Customization

- **Add more sources**: Edit `SOURCE_URLS` list
- **Change depth**: Modify `max_depth` parameter (default: 4)
- **Adjust delay**: Change `REQUEST_DELAY` (default: 1.0 seconds)
- **Filter patterns**: Add to `ARTICLE_PATTERNS` or `KPI_KEYWORDS`

## Notes

- **Be respectful**: Uses delays between requests
- **May take time**: Multi-level following can take several minutes per source
- **Some sites may block**: If a site blocks scraping, it will skip and continue
- **Results vary**: Some pages have more extractable data than others

## Troubleshooting

- **No datapoints found**: Try adding more source URLs or increasing `max_depth`
- **Connection errors**: Check internet connection, some sites may be temporarily unavailable
- **Parsing errors**: Some pages may have malformed HTML - the notebook will skip them
