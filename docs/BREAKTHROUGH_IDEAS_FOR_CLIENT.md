# Breakthrough Ideas for Client Presentation

**Purpose:** Suggestions that go beyond “we built the pipeline” and position the deliverable as a **clear differentiator** for PharmaACE / InsightACE. Pick 1–3 to align on, then we implement.

---

## 1. **Evidence Quality Index (EQI) — One number per indication**

**One-line value:** *“At a glance: how ready is this indication for InsightACE?”*

- **What:** A single **0–100 score** (and label: Ready / Needs review / Not ready) per indication + country run, derived from: % of required metrics with ≥1 gold/silver source, agreement rate, coverage of key years, and white-space severity.
- **Why breakthrough:** Executives and product owners get one headline number instead of digging through scorecards. Easy to compare CLL vs Lung Cancer vs next indication. Fits “trustworthy enough to act on.”
- **Deliverable:** EQI on the one-pager and in a small `evidence_quality_index_{suffix}.csv` (indication, country, eqi_score, eqi_label, factors_breakdown). Optional: show EQI in the web UI after a run.
- **Effort:** Medium (formula + one new output + optional UI).

---

## 2. **Source lineage / audit trail — “Every number traces to a source”**

**One-line value:** *“Proof pack: for any EPI value, see exactly where it came from and how it was derived.”*

- **What:** For each **tool-ready / InsightACE** value (metric × year), attach a **lineage record**: source_citation, source_url, source_tier, year_or_range, extraction_notes, confidence_score. Export as a **lineage table** (e.g. `lineage_{suffix}.csv` or an extra column set in tool_ready) and optionally a one-pager “How to read lineage.”
- **Why breakthrough:** Directly addresses “no AI-generated numbers” and regulatory/audit mindset. Client can show stakeholders: “This incidence number is from SEER, this URL, this year.”
- **Deliverable:** Lineage table linked to tool_ready/InsightACE export; short doc “Source lineage and audit trail.”
- **Effort:** Medium (already have evidence → tool_ready mapping; formalize and export).

---

## 3. **“What changed” vs last run (delta report)**

**One-line value:** *“See exactly what’s new or different since the last pipeline run — no re-reading everything.”*

- **What:** When the pipeline runs, compare current evidence and KPI outputs to the **previous run** (same indication+country) if it exists. Produce a **delta report**: new sources, changed values (metric/year), new conflicts, coverage changes. Output: `delta_report_{suffix}.md` and optionally a small CSV of changed rows.
- **Why breakthrough:** Saves time on refresh cycles; supports “point-in-time” and “what’s new” storytelling. Fits InsightACE’s refresh and CI use cases.
- **Deliverable:** Delta report (markdown + optional CSV); optional “Last run: date” and “Changes since last run” on web UI.
- **Effort:** Medium–high (need to store/load previous run outputs and diff).

---

## 4. **InsightACE-ready package (one-click export)**

**One-line value:** *“One folder = everything needed to load this indication into Epidemiology (Beta).”*

- **What:** A single **export package**: InsightACE-formatted CSV(s), schema description, lineage snippet, EQI (if built), one-pager summary, and a short **ingestion checklist** (e.g. “1. Upload insightace_epi_*.csv to Disease Overview; 2. Map EPI Parameter to…”). Optionally a **manifest.json** listing files and their purpose.
- **Why breakthrough:** Reduces friction from “we have outputs” to “we have the exact drop-in package for your platform.” Positions you as platform-aware.
- **Deliverable:** “InsightACE-ready” zip or folder + one-page ingestion checklist.
- **Effort:** Low–medium (packaging + one doc; EQI/manifest optional).

---

## 5. **Multi-indication comparison (portfolio view)**

**One-line value:** *“Compare evidence quality and gaps across all indications you run — one view.”*

- **What:** After multiple runs (e.g. CLL US, Lung Cancer UK, …), produce a **portfolio summary**: one row per (indication, country) with EQI (if built), metric coverage %, number of sources, key gaps, last run date. Output: `portfolio_summary.csv` and optionally a simple **portfolio summary markdown**.
- **Why breakthrough:** Strategic view: “Where are we strongest? Where do we need more sources?” Fits “reusable across tumor areas.”
- **Deliverable:** Portfolio summary table + optional one-pager “Portfolio evidence overview.”
- **Effort:** Medium (aggregate across runs; depends on how runs are stored/named).

---

## 6. **Recency and “use with caution” flags**

**One-line value:** *“No surprises: we flag old data and recommend when to re-run or seek newer sources.”*

- **What:** For each evidence row (or each metric in the scorecard), add **recency**: “Data year vs current year” and a flag when the **latest year of evidence** is older than a threshold (e.g. 5 years). In scorecard or one-pager: “Use with caution: incidence based on pre-2020 data.” Optionally: “Recommended refresh” (e.g. “Re-run when GLOBOCAN updates”).
- **Why breakthrough:** Shows rigor and sets expectations; reduces risk of using stale numbers in forecasts.
- **Deliverable:** Recency column/flag in evidence and scorecard; “Use with caution” callouts in one-pager and methodology.
- **Effort:** Low–medium (you have year; add thresholds and labels).

---

## 7. **Executive one-pager (slide-ready)**

**One-line value:** *“One page the client can drop into a deck: key numbers, quality, gaps, and next steps.”*

- **What:** A single **executive one-pager** (PDF or HTML): indication + geography, EQI (if built), top 3–5 metrics with “best value (source, year),” confidence snapshot, top gaps, and “Recommended next steps” (e.g. “Add SEER deep-dive for prevalence,” “Reconcile incidence across 3 sources”). Designed to be slide-ready or appendix-ready.
- **Why breakthrough:** Makes the deliverable immediately presentable; clients can share with leadership without reworking content.
- **Deliverable:** `executive_onepager_{suffix}.pdf` (or .html) from existing evidence + scorecard + white-space + methodology.
- **Effort:** Medium (template + auto-fill from existing outputs; PDF export may need a small lib).

---

## 8. **Reconciliation rules (documented and traceable)**

**One-line value:** *“When sources disagree, here’s exactly how we chose the recommended value — and you can change the rule.”*

- **What:** Document **reconciliation rules** in a short, client-facing doc (e.g. “We prefer gold tier; if tie, median; if only one source, that value with a note”). Optionally: add a **rule_id** or **rule_name** column to the reconciliation table so each recommended value points to the rule used. Config-driven so the client could later suggest a different rule (e.g. “prefer SEER for US incidence”).
- **Why breakthrough:** “Assumption-clear” and “validated” in one place; supports handoff and future tuning.
- **Deliverable:** “Reconciliation rules” one-pager + optional rule_id in reconciliation CSV.
- **Effort:** Low (doc + optional column from existing logic).

---

## Suggested alignment (pick 1–3)

| If the client cares most about…        | Prioritize |
|----------------------------------------|------------|
| **Trust, audit, compliance**           | 2 (Lineage), 6 (Recency), 8 (Rules) |
| **Ease of adoption / platform fit**   | 4 (InsightACE package), 7 (Executive one-pager) |
| **Strategic / portfolio view**        | 1 (EQI), 5 (Portfolio comparison) |
| **Operational “what changed”**        | 3 (Delta report) |

**Quick wins (high impact, lower effort):** 4 (InsightACE package), 6 (Recency flags), 8 (Reconciliation rules).  
**High-impact differentiators:** 1 (EQI), 2 (Lineage), 7 (Executive one-pager).

---

## Next step

Reply with which ideas you want to pursue (e.g. “1, 4, and 7” or “2 and 6”). We can then implement in that order and keep the rest in this doc for a later phase.
