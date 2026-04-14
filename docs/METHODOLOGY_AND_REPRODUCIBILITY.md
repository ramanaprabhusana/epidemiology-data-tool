# Epidemiology Evidence Pack — Methodology and Reproducibility

**Purpose:** Describe how sources are selected, how extraction works, how confidence is calculated, and how the KPI scorecard and white-space are produced. Use this for handoff and to run the pipeline for a new indication.

---

## 1. Source selection (tiers and config)

- **Tiers:** Evidence Finder uses three tiers: **Gold** (authoritative, e.g. SEER, CDC/NCHS, Census, NIH), **Silver** (peer-reviewed, widely cited, e.g. PubMed, registry reports), **Bronze** (grey literature, discovery links, trials, journals).
- **Config:** Sources are defined in:
  - `config/source_tiers.yaml` — tier names and high-level source list.
  - `config/sources_to_explore.yaml` — full list of link and API sources explored per run (URL templates with placeholders `{indication}`, `{country}`).
- **Order:** Discovery runs **Gold → Silver → Bronze** so high-value sources are prioritized. Within a run, the “Explore all” connector visits each entry in `sources_to_explore.yaml` (link sources get a stub and optional deep-dive; API sources are queried).
- **Adding a source:** Add an entry under `sources` in `sources_to_explore.yaml` with `name`, `tier`, `url` (with placeholders), and optional `metric`, `definition`, `notes`, `confidence`.

---

## 2. Extraction (deep-dive and APIs)

- **Link sources:** For each URL (with indication and country substituted), the pipeline fetches the page and:
  - Extracts numbers and percentages from tables, paragraphs, and sections (Results, Conclusions, Abstract, etc.) using epidemiology keywords (incidence, prevalence, rate, mortality, etc.).
  - For journal and org sites, uses **journal-specific** and **per-host** logic (see `link_value_extractor.py`: `_extract_from_journal_article`, `_extract_from_org_site`).
  - If no datapoint is found, the row keeps value **“See link for incidence, prevalence, and KPIs”** and the URL in `source_url` for manual lookup.
- **API sources:** ClinicalTrials.gov and PubMed return study/article counts and links; WHO GHO returns indicator values when available. These are appended as evidence rows.
- **Caps:** A run has a configurable time cap (e.g. 45 minutes) and a maximum number of URLs visited per run so the pipeline finishes in a bounded time.

---

## 3. Confidence scoring (rubric)

- **Rule-based score (0–100):** Each evidence row receives:
  - **Source tier:** Gold = 35 pts, Silver = 22 pts, Bronze = 15 pts.
  - **Extraction success:** 30 pts if the value is an extracted number/range; 0 if the value is “See link for...” (stub).
  - **Completeness:** Up to 25 pts for presence of definition, year_or_range, geography, population (6 pts each, cap 25).
  - **Recency:** Up to 10 pts (e.g. year within 1 year of current = 5 pts; within 5 years = 3 pts).
- **Label:** 70–100 = **High**, 40–69 = **Medium**, 0–39 = **Low**.
- **Output:** Evidence table gets columns `computed_confidence_score` and `computed_confidence`. The full rubric is in `output/confidence_rubric.md` (or embedded in this doc).

---

## 4. KPI scorecard (coverage, agreement, validation)

- **Inputs:** Evidence table + `required_metrics_*.yaml` for the indication.
- **Per required metric we compute:**
  - **Coverage:** Number of distinct sources; number of rows with an extracted numeric value.
  - **Best value:** First numeric value from the best tier (gold preferred); source name.
  - **Range:** Min and max of parsed numerics across sources.
  - **Agreement:** Whether values agree within a set percentage (e.g. 20%); text like “3 of 3 agree” or “2 of 3 agree; 1 outlier.”
  - **Validation status:** **Ready** (at least one high-confidence or gold source and agreement), **Needs review** (conflict or only low confidence), **No source** (no evidence row for that metric).
- **Output:** `kpi_scorecard_{indication}_{country}.csv` with one row per metric and columns as above. Use this to see “validated vs AI-ready” at a glance.

---

## 5. White-space (gaps)

- **Coverage matrix:** For each required metric we classify:
  - **Has value** — at least one row with an extracted numeric (not stub).
  - **Stub only** — only “See link” rows.
  - **Missing** — no evidence row.
- **Outputs:** `white_space_{suffix}.csv` (one row per metric, columns: coverage_status, n_sources, n_with_value, n_stub_only, source_list) and `white_space_{suffix}_summary.md` (narrative: what’s covered, what’s stub-only, what’s missing). This addresses “clear identification of white-space gaps.”

---

## 6. Reconciliation view

- **When:** For metrics that have **multiple** evidence rows with **different** numeric values (same or similar year/geography).
- **Output:** Reconciliation table: metric, geography, year_or_range, value_by_source (e.g. “Source A: X; Source B: Y”), range_min, range_max, recommended_value, recommended_source, note. Recommendation prefers gold tier when available. Exported as `reconciliation_{suffix}.csv`.

---

## 7. One-pager evidence summary

- **Content:** For each indication (and geography), one markdown page: key numbers (from scorecard or evidence), confidence distribution, top 3–5 sources, gaps (from white-space summary), and caveats (metrics in “Needs review” or “No source”).
- **Output:** `evidence_summary_{indication}_{country}.md`. Open in a browser or editor and print to PDF for a one-pager.

---

## 8. Reproducibility — how to run for a new indication

1. **Config**
   - Ensure `config/sources_to_explore.yaml` and `config/source_tiers.yaml` are in place (no change needed for a new indication if you use the same source list).
   - Add or select `config/required_metrics_{indication}.yaml` (copy from `required_metrics_cll.yaml` and adjust metric ids/labels). Add the indication to `config/ui_options.yaml` if using the web app.

2. **Run**
   - **Web:** Start the app (`python app_web.py` or double-click `Start_Web_App.command`), choose indication and country, click “Get data.”
   - **CLI:** From project root:
     ```bash
     python -c "
     from pathlib import Path
     from src.pipeline.runner import run_pipeline
     run_pipeline(
         indication='Your Indication Name',
         country='US',
         config_dir=Path('config'),
         output_dir=Path('output'),
         export_dashboard=True,
     )
     "
     ```

3. **Outputs (in `output/`)**
   - `evidence_by_metric_{indication}_{country}.csv` — evidence table (sorted by metric; with computed_confidence).
   - `kpi_scorecard_*.csv` — per-metric coverage, validation status; `kpi_conflicts_*.csv` when conflicts exist.
   - `white_space_*_summary.md` — white-space narrative.
   - `validation_report_*.csv` — validation audit trail.
   - `reconciliation_*.csv` (if there are conflicting values).
   - `evidence_summary_*.md` — one-pager.
   - `confidence_rubric.md` — scoring rubric.
   - `tool_ready_*.csv`, `insightace_epi_*.csv`, `forecast_*.csv`, `insights_summary_*.csv`, and optionally `output/dashboard/` (CSV + SQLite).

4. **Dependencies:** Python 3.x, pandas, openpyxl, PyYAML, requests, beautifulsoup4, flask (see `requirements.txt`). Optional: python-docx for Word export.

---

## 9. How to read the KPI scorecard

- **best_value** — Single value we recommend for this metric (from best available source).
- **best_source** — Source that supplied best_value.
- **range_min / range_max** — Spread of parsed numeric values across sources; large range suggests need for reconciliation.
- **n_sources** — Number of distinct sources; **n_with_value** — Rows with an extracted number (not stub).
- **agreement_flag** — “X of Y agree” or “no numeric values”; use to see if sources align.
- **validation_status** — **Ready** = use with confidence; **Needs review** = check sources or reconciliation table; **No source** = gap, add source or manual entry.

---

*This document is part of the Epidemiology Evidence Pack. Source-backed data; no AI-generated numbers.*
