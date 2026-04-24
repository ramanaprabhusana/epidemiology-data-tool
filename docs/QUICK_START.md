# Quick Start - Evidence Finder + Data Builder

Get the pipeline running in a few minutes.

---

## 1. Setup (once)

```bash
cd "Data Pipeline tool"
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 2. Run the pipeline

**Option A - Streamlined web page**

```bash
python app_web.py
```

Then open **http://127.0.0.1:5000** in your browser. Choose indication and country, optionally upload evidence CSV, then click **Get data**. Download links appear after the run.

**Option B - Interactive app**

```bash
streamlit run app.py
```

Choose **Indication** and **Country**, optionally upload an evidence CSV, then click **Get data**. PubMed is always queried for literature counts (silver tier). Download from the page or use files in `output/`.

**Option C - Command line**

```bash
# CLL + US (outputs in output/)
python run_tool.py --indication CLL --country US

# Without dashboard export
python run_tool.py --indication CLL --country US --no-dashboard

# PubMed is on by default. To skip (faster/offline):
python run_tool.py --indication CLL --country US --no-pubmed
```

---

## 3. Where outputs go

| Output | Location |
|--------|----------|
| Evidence table | `output/evidence_<Indication>_<Country>.csv` |
| Tool-ready table | `output/tool_ready_<Indication>_<Country>.csv` |
| KPI table | `output/kpi_table_<Indication>_<Country>.csv` |
| Conflicts (if any) | `output/kpi_conflicts_<Indication>_<Country>.csv` |
| InsightACE export | `output/insightace_epi_<Indication>_<Country>.csv` |
| Dashboard (CSV + SQLite) | `output/dashboard/` (when dashboard export is on) |

---

## 4. Add a new indication

1. **Metrics config** - Copy `config/required_metrics.yaml` to `config/required_metrics_<slug>.yaml` (e.g. `required_metrics_my_indication.yaml`). Set `indication` and the list of `metrics` (id, label, required, splits).
2. **Evidence** - Add `templates/evidence_<slug>.csv` with columns: indication, metric, value, source_citation, source_tier (gold/silver/bronze), and optional definition, population, year_or_range, geography, split_logic, source_url, notes, confidence.
3. **UI** - Add an entry to `config/ui_options.yaml` under `indications` (id, label, config_suffix).
4. Run from UI or: `python run_tool.py --indication "My Indication" --country US`

---

## 5. Connect Tableau or Power BI

After running with **Export dashboard** enabled, open `output/dashboard/`. Connect your BI tool to the CSV files or to `epidemiology_dashboard.db`. See [DASHBOARD_AND_ANALYTICS.md](DASHBOARD_AND_ANALYTICS.md) for step-by-step Tableau and Power BI instructions.

---

## 6. Run tests

```bash
python -m pytest tests/ -v
```

---

For full handoff and configuration details, see [HANDOFF.md](HANDOFF.md) and [EVIDENCE_FINDER_DATA_BUILDER_SCOPE.md](EVIDENCE_FINDER_DATA_BUILDER_SCOPE.md).
