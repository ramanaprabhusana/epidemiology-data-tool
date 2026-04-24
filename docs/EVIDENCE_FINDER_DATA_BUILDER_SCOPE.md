# Evidence Finder + Data Builder - Scope & Specification

## Vision

Build a **structured evidence consolidation and scenario-building tool** that:
- Reduces manual secondary research by pulling epidemiology evidence for an indication into **one place**
- Keeps **forecaster judgment in the loop** (human selects among defensible options)
- Supports **multiple defensible alternatives** (e.g., alternate growth rates, stage splits) with clear rationale, so forecasters review options in one place instead of searching across sites
- Enables **repeatable replication** across the 5 indications (and future ones)
- Leaves room for **future integration with paid data sources**

---

## 1. Evidence Finder

### Purpose
Prioritize and collect epidemiology evidence from trusted sources in a **tiered order**, capturing full context so every value is traceable and comparable.

### Source tiers (suggested)
| Tier | Description | Examples |
|------|-------------|----------|
| **Gold** | Standardized, authoritative, US epidemiology | SEER, CDC/NCHS, Census, NIH surveillance |
| **Silver** | Peer-reviewed, widely cited | PubMed/PMC, key journal papers, registry reports |
| **Bronze** | Grey literature, reports, trials | ClinicalTrials.gov, commercial reports (future), white papers |

*Configurable per indication or globally so PharmaACE can adjust preferences.*

### Context to capture per evidence item
- **Metric** (e.g., incidence, prevalence, diagnosed prevalence)
- **Definition** (how it’s defined in the source)
- **Population** (e.g., US adults 18+)
- **Year / year range** (e.g., 2019, 2015–2019)
- **Geography** (US national, or state/region if applicable)
- **Split logic** (e.g., by stage, line of therapy, biomarker)
- **Value** (point estimate or range)
- **Source** (citation, URL, report name)
- **Notes** (limitations, reconciliation with other sources)
- **Confidence** (optional: low/medium/high, aligned to project rubric)

### Output
- **Structured evidence table** (e.g., CSV/Excel + optional DB) with one row per evidence item and columns for the fields above
- **Source log** (which sources were queried, what was found, what was excluded and why)
- **Gap/conflict flags** (missing metrics, conflicting values across sources) to feed the KPI table

### Future scope
- API or connector layer for **paid data sources** (same schema, additional source tier)
- Optional **automated search** (e.g., PubMed query by indication + metric) with results pushed into Evidence Finder

---

## 2. Data Builder

### Purpose
Turn raw evidence into **tool-ready, consolidated datasets** while **retaining multiple defensible alternatives** (not forcing a single number). Forecaster chooses the scenario that best fits the use case.

### Core behavior
- **Standardize** extracted values into the **InsightACE / Epidemiology (Beta) schema** (metrics, splits, years, geography)
- **Consolidate** by metric/split/year but **keep multiple alternatives** where sources or assumptions differ
- **Attach rationale** to each alternative (e.g., “SEER 5-year trend”, “Literature-based growth 2%”, “Conservative vs optimistic stage distribution”)

### Scenario options (dropdown-style)
- **Growth rate**: e.g., “SEER trend”, “Literature low”, “Literature high”, “Flat”
- **Stage split**: e.g., “Source A distribution”, “Source B distribution”, “Blended”
- **Incidence/prevalence**: e.g., “SEER only”, “SEER + NCHS reconciliation”, “Published model”
- Each option has: **label**, **short rationale**, **source(s)**, **resulting epi values** (or link to computed values)

### Output
- **Tool-ready tables** (e.g., CSV/Excel aligned to ingestion or Epidemiology view) with chosen scenario clearly indicated
- **Scenario registry** (all alternatives + rationale) so the same logic can be reused across indications
- **Audit trail**: which scenario was selected, for which indication, and why (for handoff and replication)

### Forecaster in the loop
- User selects indication → sees required metrics and available evidence
- User picks **scenario options** (dropdowns) → Data Builder fills the tool-ready table
- User can override or add notes; KPI table and central repo reflect “validated” vs “needs review”

---

## 3. KPI Table & Central Repository

### Purpose
- Track **required CLL (or indication-specific) metrics**
- **Flag gaps** (missing metrics/splits) and **conflicts** (divergent values across sources)
- Store **validated evidence** and **chosen scenarios** for each indication
- Enable **repeatable replication** (same process for Indication 1–5 and beyond)

### Suggested contents
| Element | Description |
|--------|-------------|
| **Required metrics list** | Per indication: incidence, prevalence, stage split, etc., as per InsightACE view |
| **Coverage** | Which metrics have at least one evidence item; which have multiple alternatives |
| **Gaps** | Missing metrics or splits; priority for filling |
| **Conflicts** | Where two sources give materially different values; link to evidence items |
| **Validated vs AI/auto** | Which numbers are source-backed vs not (align with main project KPI scorecard) |
| **Scenario choices** | Per indication: which growth rate, stage split, etc., were selected and rationale |
| **Central repo** | Single place (folder + optional SQLite/Excel) for all evidence tables, scenario registry, and KPI table |

### Repeatability
- Same **source tiers**, **context fields**, and **schema** for every indication
- **Templates**: evidence template, scenario registry template, KPI template
- Documentation: how to add an indication, how to add a new source tier, how to add a new scenario type

---

## 4. Suggested Tech Stack (Pilot)

| Component | Suggestion | Rationale |
|-----------|------------|-----------|
| **Language** | Python 3.x | Fits “Python, Excel” in project plan; good for APIs and file I/O |
| **Evidence storage** | CSV/Excel first; optional SQLite later | Simple for PharmaACE handoff; DB when scaling or dashboard |
| **Source config** | YAML or JSON | Tier list, source URLs, search queries (e.g., PubMed) per indication |
| **Schema** | One schema (e.g., JSON or dataclasses) for evidence + tool-ready output | Consistency across Evidence Finder and Data Builder |
| **Excel I/O** | `openpyxl` or `pandas` | Read/write templates and deliverables |
| **APIs** | Requests + parsing for PubMed, SEER (if public), CDC where available | Automate “find” step where possible |
| **CLI or simple UI** | CLI first (e.g., “run for indication X”, “export scenario Y”) | Fast to build; optional Streamlit/GUI later |

---

## 5. Deliverables (aligned to your pilot)

1. **Evidence Finder**
   - Configurable source tiers and context fields
   - At least one “gold” source path (e.g., manual CSV upload or one API) to prove the flow
   - Output: evidence table (CSV/Excel) + source log

2. **Data Builder**
   - Schema aligned to Epidemiology (Beta) / PharmaACE expected format
   - Scenario registry (e.g., growth rate, stage split) with rationale
   - Tool-ready export with selected scenario and optional dropdown-style summary (e.g., in Excel with data validation or a small companion table)

3. **KPI table + central repository**
   - KPI-style table: required metrics, coverage, gaps, conflicts, validated vs AI
   - Central folder (and optional DB) for evidence + scenarios + KPI table
   - One-page “how to replicate” for the next indication

4. **Documentation**
   - How to add an indication
   - How to add a source or scenario type
   - Definitions (metrics, splits, confidence) and any assumptions log link

---

## 6. Optional Enhancements (your ideas + a few more)

- **Dropdown-style scenario options with rationale** - Implement as a small “scenario selector” (e.g., Excel data validation + hidden sheet, or a simple HTML/Streamlit form) that writes the chosen scenario into the tool-ready file.
- **Future paid sources** - Abstract “source” behind an interface (e.g., `GoldSource`, `SilverSource`, `PaidSource`) so new connectors don’t break Evidence Finder.
- **Conflict detection** - Rule of thumb: same metric + same population + same year but different value → flag and list both evidence items in KPI table.
- **Market basket alignment note** - One short doc per indication: which epi fields support the numbers (link to evidence and scenario choices); can be auto-generated from the scenario registry + evidence table.

---

## 7. Success Criteria (pilot)

- For **at least one indication**: run Evidence Finder → get a populated evidence table with context; run Data Builder → get tool-ready output with at least 2 scenario options (e.g., 2 growth rates) selectable with rationale.
- KPI table and central repo in place and documented.
- Process document so a teammate can repeat the same steps for another indication without your presence.

If you want, next step can be a **concrete project layout** (folders, module names, one minimal script) and a **data schema** (evidence row, scenario row, KPI row) you can implement in code.
