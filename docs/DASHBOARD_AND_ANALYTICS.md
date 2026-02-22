# Dashboard & Advanced Analytics Guide

**Phase 2 (after the tool is built).** This document explains how to use the tool’s **multi-level source finder**, **dashboard-ready data layer**, and **forecasting/insights** so the client can connect **Tableau** or **Power BI** once the pipeline is ready. See [BUILD_ORDER.md](BUILD_ORDER.md) for tool-first, dashboards-after sequence.

---

## 1. Multi-Level Data Finding

The tool finds data from **multiple sources at different levels** (tiers):

| Level | Tier | Description | Examples |
|-------|------|-------------|----------|
| 1 | **Gold** | Highest confidence, authoritative | SEER, CDC/NCHS, Census, NIH |
| 2 | **Silver** | Peer-reviewed, widely cited | PubMed/PMC, registry reports |
| 3 | **Bronze** | Grey literature, trials, reports | ClinicalTrials.gov, commercial (future) |

- **Order:** Evidence is collected **Gold → Silver → Bronze** so high-confidence sources are prioritized.
- **Aggregation:** All levels are combined into one **evidence table** and a **source log** (which tier/source contributed what).
- **Extensibility:** You can add API connectors (e.g. PubMed, SEER) per tier/source; the same tier logic applies. Manual CSV upload can tag rows by `source_tier` (gold/silver/bronze) so one file can feed multiple levels.

**Code entry:** `src/evidence_finder/sources.py` — `TieredSourceFinder`, `collect_from_multiple_levels()`.

---

## 2. Dashboard-Ready Data Layer (Tableau & Power BI)

The pipeline can export a **single folder** (and optionally one **SQLite** database) with fixed table names so the client can point Tableau or Power BI at one location and refresh.

### Tables Exported

| Table | Description | Typical use in dashboards |
|-------|-------------|----------------------------|
| **evidence** | All evidence rows (metric, value, source, tier, year, geography, etc.) | Evidence explorer, source mix, trend by tier |
| **tool_ready** | Consolidated tool-ready rows (indication, metric, year, split, value, scenario) | Main epi view, scenario comparison |
| **kpi** | Required metrics, coverage, gap flags | Coverage gauge, gap list |
| **scenario_registry** | Scenario options (growth rate, stage split) with rationale | Scenario selector, audit |
| **insightace_epi** | EPI Parameter × Year (InsightACE format) | Ingestion or mirror of platform view |
| **source_log** | Which tier/source was queried, row counts, status | Data lineage, refresh status |
| **forecast** | Forecasted values by metric/year/scenario | Forecast charts, scenario comparison |
| **insights_summary** | Per-metric summary + gap flag + short insight text | KPI cards, narrative insights |

### Connection Options

**Option A — CSV folder (simplest)**  
- Pipeline writes all tables as CSV to one folder (e.g. `output/dashboard/`).  
- **Tableau:** Data → Connect to Text file → select each CSV; or use a folder data source.  
- **Power BI:** Get Data → Text/CSV → select each CSV; or connect to folder.  
- **Refresh:** Re-run the pipeline; overwrite CSVs; refresh the workbook/report.

**Option B — SQLite (single connection)**  
- Pipeline writes one SQLite file (e.g. `output/dashboard/epidemiology_dashboard.db`) with one table per name above.  
- **Tableau:** Connect to SQLite (may require driver or Tableau’s built-in support).  
- **Power BI:** Get Data → Database → SQLite (or use a connector).  
- **Refresh:** Re-run the pipeline to rebuild the DB; then refresh the dashboard.

**Option C — Excel**  
- Pipeline can write each table as a sheet or separate Excel file.  
- Power BI and Tableau can connect to Excel; refresh after re-export.

### Recommended Refresh Process

1. Run the full pipeline (evidence finder → data builder → KPI → forecast → insights → dashboard export).  
2. Export to `output/dashboard/` (CSV + optional SQLite).  
3. In Tableau/Power BI, refresh the data connection(s) to that folder or DB.  
4. Schedule the pipeline (e.g. weekly) and refresh the dashboard after each run.

---

## 3. Forecasting & Insights (Advanced Analytics)

### Forecasting

- **Purpose:** Generate forward-looking values for key metrics (e.g. incidence, prevalence) from curated historical evidence — **no AI-generated numbers**; only source-backed inputs.
- **Method:** Simple trend: use last observed year and optional growth rate; if not provided, growth is estimated from the last two years of evidence.
- **Output:** A **forecast** table: indication, metric, year, value, scenario (e.g. base). Can be extended to low/base/high scenarios by passing different growth rates per metric.
- **Dashboard use:** Line charts (historical evidence + forecast), scenario comparison, planning views.

**Code:** `src/analytics/forecast.py` — `simple_trend_forecast()`, `build_forecast_table()`.

### Insights Generation

- **Purpose:** Summarize evidence and gaps in a structured way for dashboards and reports.
- **Output:** **insights_summary** table: per-metric evidence count, tier mix, year range, gap flag, and a short **insight_text** (e.g. “Incidence: 3 source(s) from gold, silver (2018–2022). [Gap: add evidence]”).
- **Dashboard use:** KPI cards (evidence count, gap count), tables of insights, “white space” views.

**Code:** `src/analytics/insights.py` — `build_insights_summary()`.

---

## 4. Sophisticated Reference Tool — Summary

| Capability | How it’s implemented |
|------------|----------------------|
| **Multi-level source finding** | TieredSourceFinder: Gold → Silver → Bronze; multiple sources per tier; one evidence table + source log. |
| **Dashboard connectivity** | Single export folder (and optional SQLite) with fixed table names; Tableau/Power BI connect to CSV or DB and refresh. |
| **Forecasting** | Trend-based forecast from evidence; optional low/base/high; output in forecast table for BI. |
| **Insights** | Per-metric summary + gap flag + narrative line; insights_summary table for cards and reports. |
| **Client handoff** | Same pipeline produces evidence, tool-ready, KPI, scenarios, InsightACE epi, forecast, and insights; all can be written to the dashboard layer for a single reference point. |

For setup, run order, and handoff, see [HANDOFF.md](HANDOFF.md). For confidentiality, see [CONFIDENTIALITY.md](CONFIDENTIALITY.md).

---

## 5. Quick Connect: Tableau and Power BI (Phase 2)

After the tool has been run with `--dashboard`, connect BI tools to `output/dashboard/`.

### Tableau

**Option A — Connect to CSV files**

1. Open Tableau Desktop.
2. **Connect → Text file** (or **To a file → Text file**).
3. Navigate to the project’s `output/dashboard/` folder.
4. Select one CSV at a time (e.g. `evidence.csv`, `tool_ready.csv`, `kpi.csv`, `forecast.csv`, `insights_summary.csv`) and add to the data model, or use **Data → New Data Source** for each.
5. Build sheets using the desired tables; join on common keys (e.g. indication, metric) if using multiple tables.
6. **Refresh:** Re-run `python run_tool.py --indication <X> --dashboard`, then in Tableau use **Data → Refresh** (or refresh the data source).

**Option B — Connect to SQLite (single data source)**

1. **Connect → To a server → More…** (or **Database**) and choose **SQLite** if available (some Tableau editions support it; otherwise use a SQLite ODBC driver).
2. Browse to `output/dashboard/epidemiology_dashboard.db`.
3. Drag the needed tables (evidence, tool_ready, kpi, forecast, insights_summary, etc.) into the canvas and relate them as needed.
4. **Refresh:** Re-run the tool to regenerate the `.db` file, then refresh the data source in Tableau.

### Power BI

**Option A — Connect to CSV files**

1. Open Power BI Desktop.
2. **Home → Get data → Text/CSV**.
3. Navigate to `output/dashboard/` and select a CSV (e.g. `evidence.csv`). Click **Load** (or **Transform data** to edit).
4. Repeat **Get data → Text/CSV** for other tables (tool_ready, kpi, forecast, insights_summary, etc.), or use **Get data → Folder** and point to `output/dashboard/` to combine multiple CSVs (then filter/transform as needed).
5. In **Model** view, create relationships between tables (e.g. evidence.metric ↔ kpi.metric_id, or by indication).
6. **Refresh:** Re-run the tool, then **Home → Refresh** (or schedule refresh in the Power BI service if published).

**Option B — Connect to SQLite**

1. **Get data → Database → SQLite database** (or **More…** and search for SQLite if your connector list includes it).
2. Select `output/dashboard/epidemiology_dashboard.db`.
3. Choose the tables to load (evidence, tool_ready, kpi, forecast, insights_summary, etc.) and load or transform.
4. Build reports; **Refresh** after re-running the tool.

### Suggested first steps in the dashboard

- **Evidence:** Table or filterable list (metric, source_tier, value, year); optional chart by tier or year.
- **KPI:** Card or table for coverage (e.g. % metrics covered), list of gaps (metric_id where gap = True).
- **Forecast:** Line chart (year on axis, value, metric or scenario in legend).
- **Insights summary:** Table or cards with insight_text; filter by has_gap for “white space” view.
