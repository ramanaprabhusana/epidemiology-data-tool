# Deep-Dive Extraction - Exact Match to Web Platform

This notebook uses the **EXACT SAME** deep-dive extraction logic as the web platform (`src/evidence_finder/connectors/link_value_extractor.py`).

## Matching Features

### ✅ Extraction Parameters
- **Tables**: 35 tables scanned (web platform: 35)
- **Text**: 120,000 characters (web platform: 120,000)
- **Tags**: 250 elements (web platform: 250)
- **Context window**: 100 characters for KPI matching (web platform: 100)

### ✅ 6-Strategy Deep-Dive (Exact Match)

1. **Current Page Extraction**
   - Extract from tables and body text
   - Same extraction functions as web platform

2. **Search Page Strategy** (Google Scholar, etc.)
   - Follows **8 result links** (web platform: 8)
   - Does **BOTH**:
     - Immediate extraction (`fetch_and_extract`)
     - Recursive deep-dive (`scrape_url`) if still need more datapoints
   - Exact match to web platform's Strategy 1

3. **Journal Search Strategy** (Lancet, Nature, etc.)
   - Follows **8 article links** (web platform: 8)
   - Does **BOTH**:
     - Immediate extraction (`fetch_and_extract`)
     - Recursive deep-dive (`scrape_url`) if still need more datapoints
   - Exact match to web platform's Strategy 2

4. **Article Page Strategy**
   - Follows **5 reference links** (web platform: 5)
   - Extracts from reference pages
   - Exact match to web platform's Strategy 3

5. **Company Site Strategy**
   - Scans **8 epidemiology pages** (web platform: 8)
   - Filters by company data patterns
   - Exact match to web platform's Strategy 4

6. **Fallback Strategy**
   - Tries **10 promising links** with epidemiology keywords (web platform: 10)
   - Exact match to web platform's Strategy 5

7. **Final Recursive Fallback**
   - Tries **3 promising links** with recursive extraction (web platform: 3)
   - Uses longer delay (1.5x) for recursive calls
   - Exact match to web platform's Strategy 6

### ✅ Persistent Extraction Logic

- **Max depth**: 5 levels (web platform: 5)
- **Initial min_datapoints**: 2 (web platform: 2)
- **Retry logic**: If no result, retries with max_depth=4, min_datapoints=1 (web platform: same)
- **Retry on fetch failure**: Up to 2 retries (web platform: 2)

### ✅ Deduplication & Formatting

- **Priority order**: incidence → prevalence → cases → rate → percent → mortality → survival → value
- **Max values**: 30 if >15 found, else 25 (web platform: same)
- **Format**: "value1 (label1); value2 (label2); ..." (web platform: same)

### ✅ Link Detection

- **Google Scholar**: Checks 20 h3 tags + 80 links (web platform: same)
- **References**: Scans 120 links for DOI/pubmed patterns (web platform: same)
- **All links**: Checks up to 200 links per page (web platform: 200)

## Differences (Notebook vs Web Platform)

**None** - The notebook uses the same logic, just structured as a notebook instead of a module.

The only minor difference is:
- Web platform: Returns formatted string, parses back for recursive calls
- Notebook: Works with lists directly (simpler, functionally equivalent)

## Verification

To verify the notebook matches the web platform:
1. Run the same URL through both
2. Compare extracted datapoints
3. Compare depth of link following
4. Compare number of links followed

Both should produce identical or very similar results.
