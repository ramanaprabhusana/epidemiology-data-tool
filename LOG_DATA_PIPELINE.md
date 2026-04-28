# Data Pipeline tool: change log

Use this file when continuing in a chat focused on **`Data Pipeline tool/`** (Evidence Finder, `run_tool.py`, curated YAML, SQLite dashboard export).

---

## 2026-04-28 — Evidence template fallback fix + indication-specific templates

### Problem
All 6 indication source logs (`source_log_*.csv`) showed `evidence_cll.csv` as the
gold/silver manual-upload path — even for Gastric, Hodgkin, NHL, Ovarian, Prostate.

### Root cause
`src/pipeline/runner.py:285` had a hardcoded fallback slug list:
`[slug, "cll", "lung_cancer", "example"]`. For non-CLL indications the slug
didn't match, so the code fell through to "cll" which always resolved.

### Fix
1. **`src/pipeline/runner.py:285`** — Changed fallback list from
   `[slug, "cll", "lung_cancer", "example"]` to `[slug]` so non-CLL indications
   fall through to `evidence_upload_template.csv` instead of using CLL evidence.
2. **New evidence templates** created in `templates/`:
   - `evidence_hodgkin_lymphoma.csv` (indication = Hodgkin Lymphoma)
   - `evidence_non-hodgkin_lymphoma.csv` (indication = Non-Hodgkin Lymphoma)
   - `evidence_gastric.csv` (indication = Gastric)
   - `evidence_ovarian.csv` (indication = Ovarian)
   - `evidence_prostate.csv` (indication = Prostate Cancer)
3. **`run_all_indications.py`** — `DEFAULT_WORKBOOK_REL` updated to point to
   `Epidemiology_Forecast_Model_Client_Hub_v5.xlsx` (new v5 workbook).
4. **`refresh_workbook.py`** — Docstring updated from v5.2 → v5.

### Tests
24/24 tests passed. Committed as `3d95e11`, pushed to `main`.
Streamlit auto-deployed. App UI verified: 15 output options, 6 indications, 8 countries all correct.

### Also done this session
- `Epidemiology_Forecast_Model_Client_Hub_v5.xlsx` created as a copy of v4 in
  `Integrated_Client_Delivery_Sandbox/` — new target for `refresh_workbook.py`.

---

## HANDOFF SUMMARY (as of 2026-04-28)

### What this tool is
A Streamlit app that collects epidemiology evidence (incidence, mortality, survival, prevalence etc.) for a given cancer indication and country. It pulls from curated YAML files + PubMed + ClinicalTrials, builds evidence tables, KPI scorecards, and a consolidated Excel workbook.

### Live deployment
- **URL:** https://epi-data-tool.streamlit.app/
- **GitHub repo:** https://github.com/ramanaprabhusana/epidemiology-data-tool (branch: `main`)
- **Auto-deploy:** Every push to `main` → Streamlit Community Cloud redeploys automatically (~1 min)
- **Local:** Run `streamlit run app.py` from `"Data Pipeline tool/"` folder; uses `.venv`

### Key folders / files
| Path | Purpose |
|---|---|
| `app.py` | Streamlit UI — all checkboxes, run_pipeline() call, download buttons |
| `src/pipeline/runner.py` | Core pipeline — all output generation logic |
| `config/curated_data/*.yaml` | Gold-tier curated data per indication (CLL, NHL, prostate etc.) |
| `config/ui_options.yaml` | Dropdown lists for indications and countries |
| `config/required_metrics*.yaml` | Required metrics per indication |
| `requirements.txt` | Python dependencies for Community Cloud |
| `tests/` | 24 pytest tests — run `.venv/bin/pytest tests/ -q` |
| `LOG_DATA_PIPELINE.md` | This file — always update after changes |

### How output selection works (critical to understand)
1. User checks boxes in ⚙️ Output options
2. Each checkbox maps to a flag passed to `run_pipeline()`
3. Runner only adds a file to `result["paths"]` when its flag is `True`
4. After run: `st.session_state.last_paths` = set of resolved paths from `result["paths"]`
5. `_build_outputs_zip_bytes()` receives `allowed_paths` — only zips files in that set
6. `_OUTPUT_LABELS` dict drives the dynamic file listing — shows only keys present in `result["paths"]`
7. **`scenario_registry` and `confidence_rubric` are written to disk for internal use but deliberately NOT added to `result["paths"]`** — they must never appear in the ZIP

### Current output options (15 total)
**Checked by default (left column):**
- Evidence by Metric (CSV + Excel sheet)
- KPI Scorecard (CSV + Excel sheet)
- Consolidated Excel workbook
- Tool-ready table (CSV)
- Evidence summary (.md)
- SEER Trends sheet (Excel)
- Forecast projections ← restored 2026-04-27 (was wrongly removed)

**Unchecked by default (right column):**
- InsightACE format
- Insights summary ← fixed 2026-04-27 (was trapped inside dashboard block)
- Source log
- Reference links
- Reconciliation table
- KPI conflicts
- White-space summary
- Validation report

**Permanently removed from UI (hardcoded False):**
- Dashboard BI/Tableau export — unreliable on Community Cloud ephemeral filesystem

### What was fixed across 2026-04-26 and 2026-04-27
1. **Output filter bug** — ZIP always included all files regardless of checkbox selection. Fixed by threading `allowed_paths` (set of resolved paths from `result["paths"]`) into `_build_outputs_zip_bytes()`
2. **Dynamic file listing** — hardcoded 5-item markdown replaced with loop over `_OUTPUT_LABELS`
3. **`scenario_registry` + `confidence_rubric` always in ZIP** — removed from `result["paths"]`; now internal-only
4. **`insights_summary` broken** — was nested inside `if export_dashboard:` block. Moved to its own independent block in runner.py
5. **`col3` empty column** — leftover after dashboard checkbox removal; fixed to 2-column layout
6. **Prostate citation stale** — `prostate.yaml` already had correct 2016-2022 SEER data; stale "2013-2016" came from web scraper + old zip-all bug (fixed by #1)
7. **`requirements.txt`** — removed unused `selenium`, `flask`, `gunicorn`, `python-docx`; added `numpy`, `lxml`
8. **Deployed to Streamlit Community Cloud** — repo was already connected; pushed and deployed
9. **Render** — user received Render deploy email because repo was previously connected there too; user to manually delete via https://dashboard.render.com (needs login — cannot be done by Claude)

### Pending / things to watch
- [ ] **Render cleanup** — user needs to log into https://dashboard.render.com and delete the `epidemiology-data-tool` service to stop redundant deploys and possible billing
- [ ] **Forecast on Community Cloud** — forecast works locally; not yet verified end-to-end on the cloud (Community Cloud filesystem is ephemeral per session, so the CSV will generate fine but disappears after the session)
- [ ] **New indications** — no new YAML curated data files were added in these sessions beyond prostate. If a new indication is needed, create `config/curated_data/<slug>.yaml` modelled on `cll.yaml` or `prostate.yaml`
- [ ] **`DataPipelineTool_Copy/`** — a backup copy in the same OneDrive folder; it has a slightly different version of app.py (dashboard/forecast fully removed, not just hardcoded False). It is NOT deployed anywhere — it's just a local backup. Can be ignored or deleted.

### How to continue in a new session
Tell Claude:
> "Continue working on the Data Pipeline tool. Read `LOG_DATA_PIPELINE.md` in `'Data Pipeline tool/'` for full context. GitHub repo is `ramanaprabhusana/epidemiology-data-tool`. Live app at https://epi-data-tool.streamlit.app/. Tests: `.venv/bin/pytest tests/ -q`."

---

## 2026-04-26

### Output filter, dynamic listing, forecast/dashboard download buttons

**Problems reported:**
1. Checking/unchecking Output options had no effect — ZIP always contained all files regardless
2. Forecast projections and Dashboard export files were not downloadable even when those options were checked
3. Output file listing was hardcoded 5 items with wrong filenames (showed `kpi_table_*.csv` but file is `kpi_scorecard_*.csv`)

**Root cause:** `runner.py` correctly gates files behind flags in `result["paths"]`, but:
- Files are always written to disk (required for downstream pipeline steps); only their presence in `result["paths"]` is gated
- `_build_outputs_zip_bytes` zipped everything in the output folder matching the suffix — ignoring the selection flags entirely
- The "Included file names" markdown was hardcoded 5 lines, never reading `result["paths"]`

**Changes to `app.py`:**

1. **`_build_outputs_zip_bytes`** — Added `allowed_paths: set` parameter. When provided, only files whose resolved path is in `allowed_paths` are included in the ZIP. Dashboard folder is included only when `dashboard_dir` is in `allowed_paths`.

2. **Session state** — After each run, `st.session_state.last_paths` is set to the set of resolved file paths from `result["paths"]`. This is passed to `_build_outputs_zip_bytes` so the ZIP exactly matches what was selected.

3. **Dynamic file listing** — Hardcoded markdown block replaced with a loop over `_OUTPUT_LABELS` dict keyed on `result["paths"]`. Only files that were actually generated and selected appear in the list.

4. **Individual download buttons** — Added dedicated download buttons for:
   - Forecast projections CSV (when `include_forecast=True`)
   - Consolidated Excel workbook (when `include_consolidated_xlsx=True`)
   - Existing buttons for evidence, KPI scorecard, tool-ready now gated on their keys being in `paths`

5. **Filename fix** — KPI download button filename corrected from `kpi_table_*.csv` → `kpi_scorecard_*.csv` to match actual file produced by runner

6. **`country_display` in session state** — Added so ZIP filename uses the human-readable country name

**Note on prostate "2013-2016" citation:** `prostate.yaml` already contains correct 2016-2022 SEER data. The stale value came from a web scraper capturing an old SEER page; it was in a previous run's output file which was included in the ZIP due to the zip-all bug above — now fixed.

**Tests:** 24/24 passed.

---

## 2026-04-27

### Streamlit Community Cloud deployment + output options cleanup

**Deployed to:** https://epi-data-tool.streamlit.app/
- Pushed all local `"Data Pipeline tool"` changes to `ramanaprabhusana/epidemiology-data-tool` (main branch)
- Streamlit Community Cloud auto-deployed from GitHub on each push

**Changes to `app.py`:**

1. **Removed `export_dashboard` checkbox** — Dashboard BI/Tableau export (SQLite + folder) is unreliable on Community Cloud's ephemeral filesystem; hardcoded `export_dashboard=False`
2. **Removed `include_forecast` initially, then restored** — Forecast was incorrectly removed based on the pre-fix plan; it was always working independently. Restored as opt-in checkbox (unchecked by default) in left column of Output options
3. **Removed `last_export_dashboard` from session state** — no longer needed

**Changes to `src/pipeline/runner.py`:**

1. **Decoupled `export_insights_summary` from `export_dashboard` block** — "Insights summary" was nested inside `if export_dashboard:`, so it never ran after dashboard was hardcoded to False. Moved to its own independent block so the checkbox works correctly

**Output options audit — all 14 options verified working:**

| Option | Default | Status |
|---|---|---|
| Evidence by Metric | ✅ on | ✅ Works |
| KPI Scorecard | ✅ on | ✅ Works |
| Consolidated Excel workbook | ✅ on | ✅ Works |
| Tool-ready table | ✅ on | ✅ Works |
| Evidence summary (.md) | ✅ on | ✅ Works |
| SEER Trends sheet | ✅ on | ✅ Works |
| Forecast projections | off | ✅ Works |
| InsightACE format | off | ✅ Works |
| Insights summary | off | ✅ Works (fixed) |
| Source log | off | ✅ Works |
| Reference links | off | ✅ Works |
| Reconciliation table | off | ✅ Works |
| KPI conflicts | off | ✅ Works |
| White-space summary | off | ✅ Works |
| Validation report | off | ✅ Works |

**Tests:** 24/24 passed.

---

## 2026-04-18 (and follow-up)

### Non-Hodgkin lymphoma: sparse evidence rows (curated not applied)

**Problem:** Runs for NHL-style indications sometimes produced only a handful of evidence rows (scraped-style metrics such as generic `incidence` / `prevalence`) instead of the full **SEER-style curated block** in `config/curated_data/nhl.yaml` (dozens of metrics).

**Changes:**

1. **`src/evidence_finder/indication_context.py`**
   - **`_match_normalize`:** Maps Unicode dashes (en, em, minus) to ASCII `-` so labels like `Non–Hodgkin` still match.
   - **NHL detection** expanded: compact `nonhodgkin`, `NHL (excl. DLBCL)` without the word lymphoma, common **`Hogdkin`** typo, `excl` + `dlbcl` + `lymphoma`, etc.
   - **`curated_slug_candidates`:** When NHL is detected, **`nhl` is tried first** in the slug list so `nhl.yaml` wins over a nonexistent filesystem slug.

2. **`src/evidence_finder/connectors/explore_all.py`**
   - **`_bundled_pipeline_config_dir()`:** Resolves pipeline `config/` next to `src/`.
   - **`load_curated_records`:** If the caller’s `config_dir` has no matching curated file, **retries** using the bundled pipeline `config/` (covers wrong `--config-dir` or deployments missing `curated_data/` next to the wrong root).
   - **Bugfix:** Default `config_dir` when `None` was **`parents[2]/config`** (`src/config`, wrong). Now uses **`parents[3]/config`** (pipeline root).

3. **`src/pipeline/runner.py`**
   - **`_metrics_suffix_candidates`:** Resolves **`required_metrics_{suffix}.yaml`** using **`curated_slug_candidates(indication)`** after the raw slug, so long labels (e.g. `Non-Hodgkin Lymphoma (excl. DLBCL)`) pick up **`required_metrics_nhl.yaml`** instead of only the generic `required_metrics.yaml`.

4. **`config/ui_options.yaml`**
   - Added indication **`Non-Hodgkin Lymphoma (excl. DLBCL)`** with **`config_suffix: nhl`** for Streamlit parity with the workbook label.

5. **`tests/test_indication_context.py`** (new)
   - Slug order and NHL variants, bundled curated fallback, trial search with Unicode dash, PubMed branch for workbook label.

### How to sanity-check NHL curation locally

```bash
cd "Data Pipeline tool"
python3 -c "
from pathlib import Path
from src.evidence_finder.connectors.explore_all import load_curated_records
r = load_curated_records(Path('config'), 'Non-Hodgkin Lymphoma (excl. DLBCL)', 'US')
print(len(r))
"
```

Expect a **large** row count from `nhl.yaml` (on the order of tens of metrics), not 4–5.

### Full pipeline CLI

```bash
cd "Data Pipeline tool"
python run_tool.py --indication "Non-Hodgkin Lymphoma (excl. DLBCL)" --country US
```

### Tests

- **`tests/test_indication_context.py`:** Added as above.
- **`tests/test_runner.py`:** One legacy assertion expects **`"kpi"`** in `result["paths"]` while the runner exposes **`kpi_scorecard`**; that failure is unrelated to the NHL changes. Update the test if you want CI green.

### Not in scope for this log

- **`Client presentation/`** Excel v5.3 workbook work is recorded in **`Client presentation/LOG_EXCEL_v53.md`**.

---

*Append new dated sections below when you make further pipeline-only changes.*
