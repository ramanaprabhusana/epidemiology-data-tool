# Quick Start Guide

## Option 1: Jupyter Notebook (Recommended)

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Launch Jupyter:**
   ```bash
   jupyter notebook epidemiology_web_scraper.ipynb
   ```

3. **Edit configuration** in the notebook:
   - Change `INDICATION` (line ~20)
   - Change `COUNTRY` (line ~21)
   - Add URLs to `SOURCE_URLS` list (line ~24)

4. **Run all cells:** Cell → Run All

5. **Results saved** to CSV automatically

## Option 2: Python Script

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Edit configuration** in `scraper.py`:
   - Change `INDICATION` (line ~18)
   - Change `COUNTRY` (line ~19)
   - Add URLs to `SOURCE_URLS` list (line ~22)

3. **Run script:**
   ```bash
   python scraper.py
   ```

4. **Results saved** to CSV automatically

## Example Configuration

```python
INDICATION = "CLL (Chronic Lymphocytic Leukemia)"
COUNTRY = "US"

SOURCE_URLS = [
    "https://scholar.google.com/scholar?q=CLL+epidemiology+US",
    "https://www.thelancet.com/action/doSearch?AllField=CLL+epidemiology",
    "https://www.cancer.gov/about-cancer/understanding/statistics",
    # Add more URLs...
]
```

## What It Does

1. **Fetches each URL** with retry logic
2. **Extracts datapoints** from tables and text:
   - Numbers (incidence, prevalence, case counts)
   - Percentages (survival rates, response rates)
   - Rates (per 100,000, etc.)
3. **Follows links** if it's a search/journal page:
   - Google Scholar → follows result links
   - Journal sites → follows article links
   - Up to 4 levels deep
4. **Saves results** to CSV with timestamp

## Output Format

CSV file with columns:
- `indication`: Your indication
- `country`: Your country
- `source_url`: The URL scraped
- `value`: Extracted datapoints (e.g., "21000 (incidence); 200000 (prevalence); 5.2% (percent)")
- `datapoint_count`: Number of unique datapoints found
- `scraped_at`: Timestamp

## Tips

- **Add more sources**: More URLs = more data
- **Be patient**: Multi-level following takes time (1-2 minutes per source)
- **Check results**: Some sources may have more extractable data than others
- **Respectful scraping**: Built-in delays prevent overwhelming servers

## Troubleshooting

- **No datapoints**: Try adding more URLs or increasing `max_depth` (default: 4)
- **Connection errors**: Some sites may block scraping - it will skip and continue
- **Slow**: Normal - multi-level following takes time
