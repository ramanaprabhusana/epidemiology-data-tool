# Company & Platform Context — PharmaACE & InsightACE

**Confidential / Internal use only.** Subject to the PharmaACE NDA. See [CONFIDENTIALITY.md](CONFIDENTIALITY.md).

This document summarizes the company and platform context so the **Evidence Finder + Data Builder** tool can be shared and handed off to PharmaACE with clear alignment to their mission and systems.

---

## 1. PharmaACE

- **Role:** Consulting and analytics partner with 550+ consultants; Analytics Centre of Excellence covering Forecasting & Modeling, Insights Generation & Visualization, Business & Commercial Analytics, Market Research & Competitive Intelligence.
- **Therapy areas:** Primary Care, Specialty Care, Hospital, Oncology, Rare Diseases.
- **Tech stack (relevant):** Python, R, SAS, Alteryx, Excel, Tableau, Power BI, Qlik Sense, Spotfire; AWS, Azure, GCP; SQL Server, Snowflake, Oracle, MySQL.
- **Locations:** USA (Bridgewater, NJ), Canada (Montreal), Germany (Marburg), India (Pune, Hyderabad).

---

## 2. InsightACE

- **What it is:** PharmaACE’s in-house, AI-powered **Competitive Intelligence (CI) platform** for multiple use cases.
- **Purpose:** Streamline information gathering, synthesis, and dissemination; reduce effort-intensive data mining and manual structuring; aggregate data from multiple sources; support point-in-time refresh and custom views.
- **Key modules (from the platform):**
  - **Trial Scanner** — Global trial data (phases, indications, companies, regions, targets), trial design, MoA, approval timelines.
  - **Opportunity Scanner** — Strategic insights from trials, launch timelines, planning analytics.
  - **Market Scanner** — Market baskets by indication/MoA/targets, sales and ACOT data, 20K+ assets.
  - **Product Profile** — Brand insights, FDA labels, approvals, revenue, competitor impact.
  - **Company Profile** — Products, technology, financials, partnerships, competitors.
  - **Insights Hub** — News, sentiment, KYC alerts, watchlists, PDUFA calendar.
  - **Disease Overview** — Including **Epidemiology (Beta)** (see below).

- **Epidemiology (Beta)** lives under Disease Overview and shows:
  - **Geography:** e.g. United States.
  - **Time range:** Start Year / End Year (e.g. 2024–2029).
  - **Scenario toggle:** **Low / High** (different assumptions or bounds).
  - **Table:** “United States Distribution By Stage” (or similar) with:
    - **EPI Parameter** (rows): e.g. Incidence, Prevalence, Stage I, Stage II, Stage III.
    - **Year columns:** One column per year with numeric values.
  - Current data may be AI-generated and carry a disclaimer; the goal is to replace or supplement with **source-backed, validated** epidemiology from this tool.

---

## 3. Project Mission (Epidemiology Intelligence for InsightACE)

- **Goal:** Make epidemiology **trustworthy enough to act on**.
- **Mission:**
  - Source **high-confidence** epidemiology data for selected tumors/disease areas.
  - **Validate, reconcile, and standardize** data across public and high-quality sources.
  - Build **reusable, transparent pipelines** for extraction and validation.
  - Prepare datasets for **efficient ingestion into InsightACE**.
  - **No AI-generated data** — this tool’s outputs become the **trusted foundation** the platform relies on.

- **Success looks like:**
  - InsightACE populated with **verified, well-documented** epidemiology.
  - Each dataset: **confidence scored**, **source-mapped**, **assumption-clear**, **reusable** for future diseases and analytics.
  - **Clear identification of white-space gaps** (high burden, low data/focus).
  - Output **ready for analytics, insights, and strategic decision-making** (forecasting, market access, competitive intelligence).
  - **Pipeline repeatable and expandable** for new tumor areas.

- **Epidemiology (from project slides):**
  - **How many patients exist** — size of population today and in future (opportunity/burden).
  - **Who they are** — age, sex, disease stage, risk group (unmet demand).
  - **Where they are** — geography (market/region prioritization).
  - **How disease patterns change over time** — forecasting and planning.

- **Common metrics:** Incidence, Prevalence, Mortality and Survival, Population Splits (e.g. by stage, age, sex), Geographic Splits.

---

## 4. How This Tool Fits

| Project need | Evidence Finder + Data Builder |
|--------------|--------------------------------|
| High-confidence, source-backed data | Evidence Finder uses tiered sources (Gold → Silver → Bronze) and captures full context (source, definition, year, geography, split). |
| No AI-generated numbers | All values come from configured sources and manual/API evidence; no synthetic fill. |
| Tool-ready ingestion | Data Builder produces tables aligned to InsightACE Epidemiology (Beta): EPI Parameter, years, stage splits, optional Low/High scenario. |
| Multiple defensible options | Scenario options (e.g. growth rate, stage split) with rationale; forecaster chooses. |
| Transparent, reusable pipeline | Config-driven (YAML), same process for every indication; KPI table and central repo for gaps/conflicts and replication. |
| White-space identification | KPI table and coverage logic flag missing metrics and conflicts. |

---

## 5. Sharing With the Company

- **Deliverables to share:** Codebase (or packaged repo), `README.md`, `docs/EVIDENCE_FINDER_DATA_BUILDER_SCOPE.md`, this context doc, `docs/HANDOFF.md`, and sample `output/` (evidence table, tool-ready table, KPI table).
- **Dependencies:** Python 3.x, pandas, openpyxl, PyYAML, requests (see `requirements.txt`).
- **Integration note:** Output is designed for **ingestion into InsightACE** (e.g. Epidemiology Beta). Exact ingestion mechanism (API, file upload, ETL) depends on PharmaACE’s InsightACE backend; this tool produces the **correct schema and file formats** for that step.
