# Epidemiology Evidence Pack - Plan to Remember

**Canonical reference for capstone deliverable ideas.** Use this when implementing features or aligning with PharmaACE.

---

## Concrete ideas that satisfy both sides

### 1. Calculated confidence + rubric (high impact, analytical)

**Idea:** Replace or supplement manual "high/medium/low" with a rule-based confidence score (e.g. 0–100 or Low/Medium/High) from: source tier, extraction success, completeness (definition, year, geography), and optionally recency.

**Deliverable:**
- Confidence on each evidence row (and in exports).
- One-page "Confidence scoring rubric" (PDF/Word): what each factor means, how they combine, how to interpret.

**Why it satisfies:**
- **Client:** "High-confidence, source-backed" and "confidence scored" from the project plan.
- **You:** Clear methodology, defensible, no client data needed.

---

### 2. KPI scorecard that's truly a scorecard (high impact)

**Idea:** Turn the KPI table into a validation scorecard: for each required metric (incidence, prevalence, etc.), show:
- **Coverage:** Number of sources; best value (and source); min–max range.
- **Agreement:** Do sources agree within X%? (e.g. "3 sources; 2 agree; 1 outlier.")
- **Validation readiness:** e.g. "Ready" / "Needs review" / "No source" based on rules (e.g. ≥1 gold source and agreement → Ready).

**Deliverable:**
- KPI scorecard CSV/Excel (one row per metric: metric, best_value, source, range_min, range_max, n_sources, agreement_flag, validation_status).
- Short "How to read the scorecard" section in the methodology doc.

**Why it satisfies:**
- **Client:** Directly addresses "KPI scorecard (validated vs AI-generated)," "validated, well-documented."
- **You:** Clearly analytical (coverage, agreement, status), no internal data required.

---

### 3. White-space map (high impact, strategic)

**Idea:** Automatically identify gaps: metrics × geography × year (or × source type) where you have no or weak evidence. Output a coverage matrix (e.g. rows = metrics, columns = sources or dimensions; cell = "Has value" / "Stub only" / "Missing").

**Deliverable:**
- White-space summary (table + one page): "For CLL US: Incidence and prevalence are covered; Stage I–III splits have limited sources; Mortality has 2 sources, need reconciliation."
- Optional: simple visual (heatmap or table) in Excel or in a dashboard.

**Why it satisfies:**
- **Client:** "Clear identification of white-space gaps" (project plan and slides).
- **You:** Shows strategic thinking and clarity of scope without needing their data.

---

### 4. Source agreement & reconciliation view (analytical)

**Idea:** For each metric that has multiple source values, produce a reconciliation view: Source A = X, Source B = Y, Source C = Z; range; suggested "best" (e.g. gold source, or median) with a short rule.

**Deliverable:**
- Reconciliation table (metric, geography, year, value_by_source, range, recommended_value, note).
- Optional: "Reconciliation rules" one-pager (e.g. "We prefer SEER for US incidence when available").

**Why it satisfies:**
- **Client:** "Validate, reconcile, and standardize" and "assumption-clear."
- **You:** Clear analytical step beyond extraction.

---

### 5. One-pager "Evidence summary" per indication (impressive, low effort)

**Idea:** For each of the 5 indications, one single-page summary:
- Key numbers (incidence, prevalence, best source, year).
- Confidence (overall or per metric).
- Top 3–5 sources used.
- Main gaps (white-space).
- One-line caveats (e.g. "Stage split from one source only").

**Deliverable:** One PDF per indication (e.g. "CLL_US_Evidence_Summary.pdf").

**Why it satisfies:**
- **Client:** Something they can share internally; shows clarity and ownership.
- **You:** Demonstrates communication and synthesis, not just data.

---

### 6. Lightweight forecast with guardrails (optional, very analytical)

**Idea:** Use only your extracted incidence/prevalence (and maybe mortality) to run a simple trend forecast (e.g. linear or exponential growth) with low / base / high scenarios (e.g. different growth assumptions). Always ship with an "Assumptions and limitations" note (e.g. "Based on 3 data points; not for regulatory use").

**Deliverable:**
- Forecast table (year, low/base/high) per metric.
- One-page "Forecast assumptions and limitations."

**Why it satisfies:**
- **Client:** Connects to "Forecasting" in InsightACE and project ideas.
- **You:** Clearly analytical and reusable; you already have a forecast stub in the codebase.

---

### 7. Methodology + reproducibility pack (recognition and handoff)

**Idea:** One short methodology document (5–7 pages) that describes:
- How sources are selected (tiers, config).
- How extraction works (deep-dive, journal/org logic).
- How confidence is calculated (rubric).
- How the KPI scorecard and white-space are produced.
Plus a reproducibility pack: config files, how to run the pipeline for a new indication, and (if possible) a small example run.

**Deliverable:**
- "Epidemiology Evidence Pack – Methodology and reproducibility" (PDF + repo/config snapshot).

**Why it satisfies:**
- **Client:** "Reusable, transparent pipelines" and easier handoff.
- **You:** Positions the team as rigorous and makes the capstone clearly "deliverable-driven."

---

## How to package it for both sides

**Name the product:** e.g. "Epidemiology Evidence Pack" or "Source-backed epidemiology pack for InsightACE".

**One-sentence for PharmaACE:**  
"We deliver, per indication, a curated evidence table, a confidence-scored and source-mapped dataset, a KPI scorecard (validated vs. AI-ready), a white-space summary, optional reconciliation view and forecast, and a methodology + reproducibility pack-all from public sources, no AI-generated numbers, ready to feed InsightACE or your own analytics."

**One-sentence for your team:**  
"We don't just list sources; we extract, score, reconcile, gap-analyze, and document so the deliverable is analytical and client-ready."

---

## Suggested priority order

**Must-have (core "great product"):**
1. Calculated confidence + rubric.
2. KPI scorecard (coverage, agreement, validation status).
3. White-space summary (gaps per metric/indication).
4. One-pager per indication (evidence summary).
5. Methodology + reproducibility doc.

**Strong add-on:**
- Source agreement / reconciliation table (and short rules).

**If time allows:**
- Lightweight forecast (low/base/high + assumptions note).
- Dashboard (coverage heatmap, scorecard view) using your existing export.

---

## How this addresses "no clear goal" and "not analytical"

- **Goal** becomes: "Deliver the Epidemiology Evidence Pack per indication: evidence + confidence + scorecard + white-space + methodology (and optionally reconciliation + forecast)."
- **Analytical part** is explicit: scoring, agreement, gaps, reconciliation, optional forecasting, and a clear methodology-all on top of extraction.
- **Recognition:** You're not "just" building a scraper; you're defining how epidemiology should be sourced, scored, and validated for InsightACE, which matches the project plan and the slides.

---

## Implementation note

When implementing, start with one area (e.g. "confidence rubric + KPI scorecard") and map it to the codebase: which modules, which configs, which outputs. Use this doc as the single source of truth for the plan.

---

## Implemented (Evidence Pack in pipeline)

The following are implemented and run automatically after the KPI table in each pipeline run:

| Deliverable | Module | Output files |
|-------------|--------|--------------|
| Calculated confidence + rubric | `src/repository/confidence.py` | Evidence CSV gets `computed_confidence_score`, `computed_confidence`; `output/confidence_rubric.md` |
| KPI scorecard | `src/repository/scorecard.py` | `output/kpi_scorecard_{indication}_{country}.csv` |
| White-space | `src/repository/white_space.py` | `output/white_space_{suffix}.csv`, `output/white_space_{suffix}_summary.md` |
| Reconciliation | `src/repository/reconciliation.py` | `output/reconciliation_{suffix}.csv` (when conflicts exist) |
| One-pager summary | `src/repository/evidence_summary.py` | `output/evidence_summary_{suffix}.md` |
| Methodology | `docs/METHODOLOGY_AND_REPRODUCIBILITY.md` | Handoff doc; not auto-generated per run |
