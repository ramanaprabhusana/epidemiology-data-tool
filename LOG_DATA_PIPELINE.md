# Data Pipeline tool: change log

Use this file when continuing in a chat focused on **`Data Pipeline tool/`** (Evidence Finder, `run_tool.py`, curated YAML, SQLite dashboard export).

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
