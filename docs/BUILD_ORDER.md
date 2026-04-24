# Build Order: Tool First, Dashboards After

The client prefers **both Tableau and Power BI**. The right sequence is:

1. **Build the tool first** - Evidence Finder, Data Builder, multi-level sources, KPI, export (and optionally forecast/insights).
2. **Then** connect Tableau and Power BI to the tool’s output.

The tool produces the data; the dashboards consume it. So the pipeline and output schema need to be solid before spending time on BI connection details.

---

## Phase 1: Build the Tool (Done)

| Step | What | Status |
|------|------|--------|
| 1 | Multi-level source finder (Gold → Silver → Bronze), evidence table + source log | Done; add API connectors as needed later |
| 2 | Data Builder: tool-ready schema, scenario options, InsightACE-aligned export | Done |
| 3 | KPI table: required metrics, coverage, gaps, **conflict detection** | Done |
| 4 | Config and templates: source tiers, required metrics per indication, evidence upload | Done; `required_metrics_lung_cancer.yaml` added |
| 5 | Optional: forecasting and insights (from evidence) | Done |
| 6 | Single export folder (and optional SQLite) with fixed table names | Done (`output/dashboard/`) |
| 7 | **Single run script:** `run_tool.py --indication X [--evidence path] [--dashboard]** | Done |
| 8 | Validate with at least one real indication | Done (EXAMPLE, Lung Cancer) |
| 9 | Document run steps and handoff | HANDOFF.md, README updated |

**Deliverable for Phase 1:** A working pipeline. Run: `python run_tool.py --indication "Lung Cancer" --dashboard` to produce evidence, tool-ready, KPI (+ conflicts), forecast, insights, and dashboard layer. Phase 2: connect Tableau and Power BI to `output/dashboard/`.

---

## Phase 2: Connect Tableau and Power BI (After the Tool Is Ready)

| Step | What |
|------|------|
| 1 | Confirm output location and table names with the client (`output/dashboard/` and/or SQLite). |
| 2 | **Tableau:** Document or provide steps to connect to the folder (CSV) or to the SQLite database; set refresh process. |
| 3 | **Power BI:** Same: connect to CSV folder or SQLite; set refresh process. |
| 4 | Optionally provide a sample workbook/report that uses the exported tables. |

The data model and table list are already described in [DASHBOARD_AND_ANALYTICS.md](DASHBOARD_AND_ANALYTICS.md). Phase 2 is about connecting existing Tableau/Power BI installations to the tool’s output and, if needed, scheduling the pipeline and dashboard refresh.

---

## Summary

- **First:** Finish and validate the tool (evidence → data builder → KPI → export; optional forecast/insights).
- **Then:** Use the same output to connect **both** Tableau and Power BI; no need to choose one over the other.
