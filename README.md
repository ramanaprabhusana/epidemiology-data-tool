# Epidemiology Data Tool (Evidence Finder + Data Builder)

## For the person using this tool to get data

**You use this tool to get epidemiology data for an indication and country.** No code editing needed.

1. **Open the tool** (first time: see [HOW_TO_USE_THIS_TOOL.md](HOW_TO_USE_THIS_TOOL.md) for setup). Use **one** of:
   - **Double-click (no terminal):** **Windows:** `Start_Web_App.bat` · **Mac:** `Start_Web_App.command` — browser opens automatically.
   - **Streamlined web page:** `python app_web.py` → then open **http://127.0.0.1:5000** in your browser
   - **Interactive app:** `streamlit run app.py` → browser opens automatically
2. **Choose** indication and country, then click **Get data**.
3. **Use** the files in the **`output`** folder (or download from the page) for your next steps (Excel, Power BI, Tableau, or another system).

Full instructions: **[HOW_TO_USE_THIS_TOOL.md](HOW_TO_USE_THIS_TOOL.md)**.

---

Pilot tool for **PharmaACE** Industry Practicum: consolidate epidemiology evidence for an indication in one place and build tool-ready datasets with **multiple defensible scenario options** (e.g., alternate growth rates, stage splits) so forecasters can choose inputs with clear rationale. Outputs are designed for **efficient ingestion into InsightACE** (Epidemiology Beta) and align with the project mission: *making epidemiology trustworthy enough to act on* — source-backed, validated, no AI-generated numbers.

**Confidential / Internal use only.** This project is subject to the PharmaACE NDA. See [docs/CONFIDENTIALITY.md](docs/CONFIDENTIALITY.md).

**Build order:** The tool (finder, builder, KPI, export) is built first; Tableau and Power BI are connected to the tool’s output after the pipeline is ready. See [docs/BUILD_ORDER.md](docs/BUILD_ORDER.md).

## Goals

- **Multi-level source finder**: Find data from **multiple sources at different levels** (Gold → Silver → Bronze); aggregate into one evidence table + source log. Extensible with API connectors per tier.
- **Evidence Finder / Data Builder**: Tiered discovery, tool-ready schema, multiple scenario options with rationale; **InsightACE-aligned export** (EPI Parameter × Year).
- **KPI table + central repo**: Track required metrics, gaps/conflicts, validated evidence; repeatable across indications.
- **Dashboard & analytics**: Export a **dashboard-ready layer** (CSV + optional SQLite) for **Tableau or Power BI**; **forecasting** (trend-based) and **insights generation** (summary + gaps) for advanced analytics and a **sophisticated reference** for the client.

**Docs:** [Quick start](docs/QUICK_START.md) · [Scope & spec](docs/EVIDENCE_FINDER_DATA_BUILDER_SCOPE.md) · [Build order](docs/BUILD_ORDER.md) · [Company & platform context](docs/COMPANY_AND_PLATFORM_CONTEXT.md) · [Handoff](docs/HANDOFF.md) · [Dashboard & analytics](docs/DASHBOARD_AND_ANALYTICS.md).

## Project layout

```
Data Pipeline tool/
├── README.md
├── requirements.txt
├── config/
│   ├── source_tiers.yaml      # Source tiers (Gold/Silver/Bronze) and preferences
│   └── required_metrics.yaml # Required metrics per indication (template)
├── docs/
│   ├── EVIDENCE_FINDER_DATA_BUILDER_SCOPE.md
│   ├── DASHBOARD_AND_ANALYTICS.md   # Tableau/Power BI, forecast, insights
│   ├── COMPANY_AND_PLATFORM_CONTEXT.md
│   ├── HANDOFF.md
│   └── CONFIDENTIALITY.md
├── src/
│   ├── evidence_finder/      # Multi-level source finder + evidence collection
│   ├── data_builder/         # Schema, scenarios, tool-ready + InsightACE export
│   ├── repository/           # KPI table and central repo
│   ├── dashboard/            # Dashboard-ready export (CSV/SQLite for Tableau/Power BI)
│   └── analytics/           # Forecasting and insights generation
├── output/                   # Evidence, tool-ready, KPI, forecast, insights
│   └── dashboard/            # BI-ready tables (CSV + optional .db)
├── HOW_TO_USE_THIS_TOOL.md   # Start here if you're the person getting the data
├── Start_Web_App.bat         # Double-click to start (Windows, no terminal)
├── Start_Web_App.command     # Double-click to start (Mac, no terminal)
├── app.py                    # Interactive app: streamlit run app.py
├── app_web.py                # Streamlined web page: python app_web.py → http://127.0.0.1:5000
├── templates_web/            # HTML for web page UI
├── static_web/               # CSS for web page UI
├── run_tool.py               # CLI: run for indication + country (--indication, --country, --dashboard)
├── run_pilot_example.py      # Legacy quick run
├── run_full_pipeline_with_dashboard.py  # Legacy full run
└── templates/                # Evidence upload template (CSV)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Usage

**Streamlined web page or interactive app:**

- **Streamlined web page:** `python app_web.py` → open http://127.0.0.1:5000 → choose indication and country → **Get data** → use download links or the `output` folder.
- **Interactive app:** `streamlit run app.py` → same flow with live previews and download buttons.

**CLI:**

```bash
# CLL + US (default: dashboard export on)
python run_tool.py --indication CLL --country US

# Other indication/country
python run_tool.py --indication "Lung Cancer" --country US --dashboard

# Skip dashboard export
python run_tool.py --indication CLL --country US --no-dashboard
```

- **Multi-level finder:** Evidence is collected from Gold → Silver → Bronze (manual CSV and/or future API connectors). KPI includes **conflict detection** (same metric/year/population, different values).
- **Dashboard:** With `--dashboard`, outputs go to `output/dashboard/` (CSV + SQLite + manifest and data dictionary for BI). Connect Tableau or Power BI; see [docs/DASHBOARD_AND_ANALYTICS.md](docs/DASHBOARD_AND_ANALYTICS.md).
- **Validation:** Evidence is validated (required columns, tier values); report is in the pipeline result and optional in the UI.
- **PubMed:** Optional `use_pubmed=True` (e.g. from UI) runs a PubMed search (silver tier) and can add stub evidence rows with PMIDs.
- **Scenarios:** Scenario options (growth rate, stage split) are read from `config/scenario_options.yaml`; edit there to add alternatives.
- **Tests:** `python -m pytest tests/ -v`

For a short path to running everything, see [docs/QUICK_START.md](docs/QUICK_START.md). For setup and handoff, see [docs/HANDOFF.md](docs/HANDOFF.md).

## Tech

- Python 3.x, pandas, openpyxl, requests; optional SQLite for central repo.
- Config: YAML (source tiers, required metrics). Schema: see `src/data_builder/schema.py`.
