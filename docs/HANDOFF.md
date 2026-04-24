# Handoff Guide - Evidence Finder + Data Builder

This guide is for **PharmaACE** teams who will use or extend this tool. It explains how to run it, what to share, and how outputs align with **InsightACE** (Epidemiology Beta).

**When giving the tool to someone who will *get the data* and work on next steps:** Point them to **[HOW_TO_USE_THIS_TOOL.md](../HOW_TO_USE_THIS_TOOL.md)** in the project root. That page is written for the end user (no code); this handoff doc is for maintainers and config.

**Confidential / Internal use only.** This project is subject to the PharmaACE NDA. See [CONFIDENTIALITY.md](CONFIDENTIALITY.md).

---

## 1. What This Tool Does

- **Evidence Finder:** Collects epidemiology evidence from tiered sources (Gold → Silver → Bronze), captures full context (source, definition, year, geography, split), and produces a structured evidence table + source log.
- **Data Builder:** Turns evidence into tool-ready datasets; supports multiple scenario options (e.g. growth rate, stage split) with rationale so forecasters can choose defensible inputs.
- **KPI table:** Tracks required metrics, coverage, gaps, and conflicts for each indication.
- **InsightACE export:** Exports epidemiology in the format used by **InsightACE → Disease Overview → Epidemiology (Beta)** (EPI Parameter × Year table, optional Low/High scenario).

All outputs are **source-backed** (no AI-generated numbers); they are intended as the trusted foundation for InsightACE.

---

## 2. What to Share With the Company

| Item | Location | Purpose |
|------|----------|---------|
| **Codebase** | Full project folder (or a zip/archive) | Run and extend the pipeline |
| **README.md** | Project root | Quick start, setup, usage |
| **Scope & spec** | `docs/EVIDENCE_FINDER_DATA_BUILDER_SCOPE.md` | Full product and technical scope |
| **Company & platform context** | `docs/COMPANY_AND_PLATFORM_CONTEXT.md` | PharmaACE / InsightACE alignment |
| **This handoff guide** | `docs/HANDOFF.md` | How to run and what to deliver |
| **Confidentiality notice** | `docs/CONFIDENTIALITY.md` | NDA and confidentiality expectations |
| **Config templates** | `config/source_tiers.yaml`, `config/required_metrics.yaml` | Customize sources and required metrics per indication |
| **Evidence upload template** | `templates/evidence_upload_template.csv` | Manual evidence entry format |
| **Sample output** | `output/` (evidence table, tool-ready table, KPI table, InsightACE-format export) | Example deliverables |

---

## 3. Setup (One-Time)

**Requirements:** Python 3.8+ (Python 3.9+ recommended).

```bash
# From the project root (Data Pipeline tool/)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

No API keys are required for the pilot (manual evidence CSV or future API integrations can be added).

---

## 4. How to Run

**Web UIs (recommended for interactive use):**

- **Streamlined web page:** `python app_web.py` → open http://127.0.0.1:5000
- **Interactive app:** `streamlit run app.py`

Choose **Indication** (e.g. CLL, Lung Cancer, Example) and **Country** (e.g. US, UK), then **Run pipeline**. Outputs go to `output/`; with “Export dashboard” checked, Tableau/Power BI–ready files go to `output/dashboard/`.

**CLI:**

```bash
# CLL + US (pipeline tags evidence by country and names outputs accordingly)
python run_tool.py --indication CLL --country US

# Other indication/country; skip dashboard
python run_tool.py --indication "Lung Cancer" --country US --no-dashboard

# Custom evidence or paths
python run_tool.py --indication CLL --country US --evidence path/to/evidence.csv --output-dir output
```

This will:

1. Load evidence from the given CSV (or default template).
2. Run multi-level finder (Gold → Silver → Bronze), write evidence table + source log.
3. Build scenario registry, tool-ready table, InsightACE epidemiology export.
4. Build KPI table and **conflicts** table (same metric/year/population, different values).
5. If `--dashboard`: add forecast, insights summary, and export all tables to `output/dashboard/` (CSV + SQLite).

**Legacy:** `python run_pilot_example.py` and `python run_full_pipeline_with_dashboard.py` still work; `run_tool.py` is the single CLI entry.

---

## 5. Adding a New Indication

1. **Add required metrics config:**  
   Copy `config/required_metrics.yaml` to `config/required_metrics_<indication>.yaml` (e.g. `required_metrics_lung_cancer.yaml`). Set `indication` and the `metrics` list (e.g. incidence, prevalence, stage_i, stage_ii, stage_iii). Use lowercase and underscores for the filename (e.g. `required_metrics_cll.yaml` for CLL).

2. **Prepare evidence:**  
   Fill `templates/evidence_upload_template.csv` or create `templates/evidence_<indication>.csv` with columns: indication, metric, value, source_citation, source_tier (gold/silver/bronze), definition, population, year_or_range, geography, split_logic, source_url, notes, confidence.

3. **Run the tool:**  
   `python run_tool.py --indication "Your Indication" [--evidence path/to/evidence.csv] --dashboard`

4. **Review outputs:**  
   `output/evidence_*.csv`, `output/tool_ready_*.csv`, `output/kpi_table_*.csv`, `output/kpi_conflicts_*.csv` (if any conflicts), `output/insightace_epi_*.csv`. Use the KPI table for coverage and gaps.

**Optional:** Evidence is validated (required columns, valid source_tier). To fail the pipeline when validation has errors, use `run_pipeline(..., strict_validation=True)`. Scenario options (growth rate, stage split) are configurable in `config/scenario_options.yaml`. **PubMed** is on by default for every UI and pipeline run; pass `use_pubmed=False` (and `add_pubmed_stubs=False`) to `run_pipeline` only for tests or special offline jobs. CLI: `run_tool.py` / `run_all_indications.py` support `--no-pubmed`.

---

## 6. Integration With InsightACE

- **Epidemiology (Beta)** in InsightACE shows a table by **EPI Parameter** (e.g. Incidence, Prevalence, Stage I, Stage II, Stage III) and **year columns**, with a **Low/High** scenario toggle.
- This tool can export exactly that layout via `export_insightace_epidemiology()`. The actual **ingestion path** (API, file upload, or ETL into the InsightACE backend) is determined by PharmaACE; the tool supplies the **correct schema and file content** for that step.

---

## 7. Support and Extensions

- **Source tiers:** Edit `config/source_tiers.yaml` to add/remove sources or change tiers.
- **Required metrics:** Edit per-indication YAML in `config/` to match indication-specific and InsightACE expectations.
- **New scenario types:** Extend `ScenarioOption` and the Data Builder logic in `src/data_builder/`.
- **APIs (e.g. PubMed, SEER):** Add connectors in `src/evidence_finder/` that append to the same evidence schema and source log.

For full product and technical scope, see **docs/EVIDENCE_FINDER_DATA_BUILDER_SCOPE.md** and **docs/COMPANY_AND_PLATFORM_CONTEXT.md**.
