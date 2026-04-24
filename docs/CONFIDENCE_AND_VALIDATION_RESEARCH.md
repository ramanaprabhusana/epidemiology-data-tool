# Confidence Level and Validation: Deep-Dive Research and Recommendations

**Purpose:** Align the tool’s confidence scoring and validation with industry frameworks and best practices, identify gaps, and propose enhancements so the client sees a defensible, audit-ready approach.

---

## Part A: What the Tool Does Today

### 1. Confidence (current)

| Aspect | Implementation |
|--------|----------------|
| **Scope** | Per **evidence row** (one score per source × metric × value). |
| **Score** | 0–100, additive: **Source tier** (35 max: gold 35, silver 22, bronze 15) + **Extraction success** (30 if numeric extracted, 0 if "See link") + **Completeness** (25 max: definition, year_or_range, geography, population, 6 pts each) + **Recency** (10 max: year within 1 yr = 5, within 5 yr = 3). |
| **Label** | High (70–100), Medium (40–69), Low (0–39). |
| **Output** | `computed_confidence_score`, `computed_confidence` on evidence CSV; `confidence_rubric.md`; scorecard uses these for **validation_status** (Ready = agreement + high confidence or gold). |
| **Manual vs computed** | Evidence schema has optional manual `confidence` (low/medium/high); pipeline adds **computed** columns and does not overwrite manual-both can coexist. |

**Strengths:** Transparent, rule-based, no black box. Tier + extraction + completeness + recency match common “evidence quality” dimensions. Rubric is documented.

### 2. Validation (current)

| Aspect | Implementation |
|--------|----------------|
| **When** | Runs on evidence **before** pipeline continues (after evidence finder, before data builder). Optional **strict_validation**: if True and any **error** exists, pipeline stops. |
| **Schema** | **Required columns:** indication, metric, value, source_citation, source_tier. **Valid tiers:** gold, silver, bronze. **Optional columns:** definition, population, year_or_range, geography, split_logic, source_url, notes, confidence. |
| **Checks** | (1) Missing required columns → **error**. (2) Invalid `source_tier` values → **error**. (3) Empty metric/value/source_citation → **warning** (sample of row indices). (4) Duplicate (metric, year_or_range, geography) → **warning**. |
| **Output** | `validation_report` (list of {level, code, message, row}); `validation_passed` (True iff no errors). Returned in pipeline result and (in web app) in API response. Not written to a file. |

**Strengths:** Clear separation of errors vs warnings; strict mode supports “fail fast.”  
**Gaps:** No row-level “valid/invalid” flag on evidence; no numeric plausibility; no export of validation report to CSV/md; no link from validation to confidence (e.g. “validation passed + high confidence”).

---

## Part B: Alignment with External Frameworks

### 1. GRADE (evidence certainty)

- **GRADE** uses: risk of bias, inconsistency, indirectness, imprecision, publication bias; levels High / Moderate / Low / Very low.
- **Our model** does not map 1:1: we have **source tier** (proxy for “risk of bias” / authority), **extraction** (direct vs stub), **completeness** (indirectness/proxy for applicability), **recency** (timeliness). We do not explicitly model **inconsistency** (agreement across sources) or **imprecision** (e.g. CIs) at the **evidence row** level-those appear in the **scorecard** (agreement_flag) and **reconciliation**.
- **Takeaway:** We can strengthen the narrative by (a) documenting that our confidence rubric is “GRADE-inspired” for epidemiology **sources** (tier, completeness, recency) and (b) adding an explicit **inconsistency** dimension when multiple sources disagree for the same metric/year (e.g. downgrade or flag).

### 2. CDC standard framework for evaluating health care data (MMWR 2024)

- **Nine constructs:** general attributes; coverage/representativeness/inclusion; standardization and **quality**; period/periodicity/recency; versatility; utility; usability; adaptability; stability.
- **Quality** is often broken into: **completeness**, **validity**, **accuracy**, **consistency**, **precision** (and plausibility in EHR frameworks).
- **Our model:** Completeness ≈ our completeness factor (definition, year, geography, population). Validity/accuracy ≈ we don’t check numeric bounds or cross-source consistency at row level. Consistency ≈ we check duplicate keys and, in scorecard, agreement. Recency ≈ our recency score.
- **Takeaway:** Adding **plausibility checks** (e.g. incidence/prevalence in reasonable ranges) and **consistency checks** (e.g. flag when value disagrees with reconciled value) would align with “standardization and quality” and “consistency.”

### 3. Data quality dimensions (secondary use / EHR reuse)

- Common dimensions: **integrity** (schema, types), **completeness**, **consistency** (internal/external), **accuracy** (plausibility, cross-check).
- **Our validation:** Strong on **integrity** (required columns, valid tiers). **Completeness** is in confidence (field presence), not in validation. **Consistency:** duplicate key warning; agreement in scorecard. **Accuracy/plausibility:** not implemented.
- **Takeaway:** Validation could be extended with: (1) **Completeness checks** (e.g. % of rows with non-null year_or_range, geography). (2) **Plausibility checks** (metric-specific bounds or “sanity” ranges). (3) **Exported validation report** (CSV/md) for audit.

### 4. Provenance and audit (FHIR Provenance, ONC)

- **Provenance** = who/what/when produced or modified data; supports authenticity and trust.
- **Our model:** We have **source_citation**, **source_url**, **source_tier**-good for lineage. We do not have a formal “provenance” object per value (e.g. extraction method, timestamp of run).
- **Takeaway:** A **lineage** or **provenance** table (metric, value, source, tier, year, extraction_type, pipeline_run_id) would strengthen “every number traces to a source” and audit readiness.

---

## Part C: Gaps and Risks

| Gap | Risk | Priority |
|-----|------|----------|
| **No plausibility validation** | Impossible or extreme values (e.g. incidence &gt; population) could slip through. | High |
| **Validation report not persisted** | No audit trail of what was checked and what failed. | High |
| **No “Very low” confidence** | GRADE has 4 levels; we have 3; very weak evidence is lumped with “Low.” | Medium |
| **Inconsistency not in row-level confidence** | When two sources disagree, we don’t downgrade confidence on individual rows. | Medium |
| **No row-level validation flag** | Users can’t filter “validation-passed” rows per row (only at run level). | Medium |
| **Manual confidence not merged with computed** | If client supplies “high,” we don’t combine it with computed (e.g. take max or show both). | Low |
| **No explicit “validation status” per metric in UI** | Scorecard has it; evidence table doesn’t surface “this row supports a Ready metric.” | Low |

---

## Part D: Recommended Enhancements

### 1. Plausibility validation (numeric bounds)

- **Idea:** For known metric types (e.g. incidence, prevalence, mortality rate), apply optional **range checks** (e.g. rate 0–1 or 0–100; count ≥ 0 and &lt; population cap).
- **Implementation:** Config-driven (e.g. `config/validation_plausibility.yaml`: metric_id → min, max, unit). In `validation.py`, after schema checks, add `_check_plausibility(df, config)` → list of {level, code, message, row, value}. Append to validation_report. Optionally add column `validation_plausibility` (pass/warning/fail) to evidence.
- **Output:** Validation report includes plausibility; optionally evidence CSV gets a `validation_plausibility` or `out_of_range` flag.
- **Effort:** Medium.

### 2. Persist validation report

- **Idea:** Write `validation_report_{suffix}.csv` (and optionally `.md`) in `output/` after validation runs, so every run has an audit trail.
- **Implementation:** In runner, after `validate_evidence_df`, call `validation_report_to_df(report)` and save to `output_dir / f"validation_report_{file_suffix}.csv"`. Optionally add a short markdown summary (errors vs warnings, counts).
- **Output:** `validation_report_{indication}_{country}.csv` with columns level, code, message, row.
- **Effort:** Low.

### 3. Confidence: add “Very low” and optional inconsistency downgrade

- **Idea:** (a) Split Low into **Low** (40–39) and **Very low** (0–19) for clarity. (b) Optionally: if the evidence row’s (metric, year, geography) appears in the **reconciliation** table (multiple conflicting sources), apply a **downgrade** (e.g. cap score at 65 or add a “inconsistent_sources” flag).
- **Implementation:** (a) In `confidence.py`, change `get_confidence_label`: 70+ High, 40–69 Medium, 20–39 Low, 0–19 Very low. Update rubric. (b) Optional: in runner, after reconciliation is built, add column `confidence_downgrade_reason` (e.g. "multiple_sources_disagree") or reduce score for rows that are in reconciliation set.
- **Output:** Rubric and evidence CSV reflect four levels; optional downgrade reason column.
- **Effort:** Low for (a); medium for (b) (need to join evidence to reconciliation).

### 4. Row-level validation flag on evidence

- **Idea:** Add `validation_passed_row` (or `schema_valid`) to each evidence row: True if that row has no required-field errors and (optionally) passes plausibility.
- **Implementation:** In validation, return per-row results (e.g. list of row indices with errors). In runner, after validation, set `evidence_df["validation_passed_row"] = True` then set False for rows in error list. If plausibility is added, combine.
- **Output:** Evidence CSV has a column users can filter on.
- **Effort:** Low (once validation returns row-level detail).

### 5. Completeness and consistency in validation (optional)

- **Idea:** (a) **Completeness:** Add warning if &gt; X% of rows missing year_or_range or geography. (b) **Consistency:** Add warning if any (metric, year, geography) has multiple distinct numeric values (same as “conflict” in KPI); optionally link to reconciliation.
- **Implementation:** In `validate_evidence_df`, add optional steps: (a) compute % complete for key fields; if below threshold, add warning. (b) Compute duplicate (metric, year, geography) with different values; add warning “Possible conflict: N metrics with multiple values.”
- **Output:** Validation report and optional summary stats.
- **Effort:** Medium.

### 6. Document alignment with GRADE and CDC in methodology

- **Idea:** In `METHODOLOGY_AND_REPRODUCIBILITY.md` and in `confidence_rubric.md`, add short sections: “Relationship to GRADE” (tier/completeness/recency as proxies; inconsistency handled in scorecard/reconciliation) and “Relationship to data quality frameworks” (completeness, consistency, plausibility as in CDC/MMWR and EHR reuse).
- **Output:** Clear narrative for client and auditors.
- **Effort:** Low.

---

## Part E: Summary Table (Confidence vs Validation)

| Dimension | Confidence (today) | Validation (today) | After enhancements (suggested) |
|-----------|---------------------|--------------------|----------------------------------|
| **Source quality** | Tier weight (35 pts) | Tier must be gold/silver/bronze | Same |
| **Extraction** | 30 or 0 | - | Same |
| **Completeness** | 25 pts from 4 fields | - | Validation: optional completeness % warning |
| **Recency** | 10 pts | - | Same |
| **Schema** | - | Required cols, valid tiers | Same + optional row-level flag |
| **Plausibility** | - | - | Validation: metric-level bounds → report + optional flag |
| **Consistency** | - | Duplicate key warning | Validation: conflict warning; Confidence: optional inconsistency downgrade |
| **Audit** | Rubric + columns | In-memory report only | Validation report CSV/md; optional provenance/lineage |
| **Labels** | High/Medium/Low | - | High/Medium/Low/**Very low** |

---

## Part F: Suggested Implementation Order

1. **Quick wins:** Persist validation report (2), add “Very low” confidence (3a), document GRADE/CDC alignment (6).
2. **High value:** Plausibility validation (1), row-level validation flag (4).
3. **If time:** Inconsistency downgrade in confidence (3b), completeness/consistency in validation (5), lineage/provenance table (from breakthrough doc).

---

*This document is part of the Epidemiology Evidence Pack. It is intended for internal use and client alignment on confidence and validation strategy.*
