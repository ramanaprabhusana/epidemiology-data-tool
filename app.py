"""
Epidemiology Data Tool - Get data for an indication and country, then use the outputs for your next steps.
Designed so someone receiving the tool can run it without editing code.
"""

import io
import sys
import zipfile
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import yaml
import pandas as pd

from src.pipeline.runner import run_pipeline

# Match app_web.py: only these extensions go into the downloadable ZIP
_ZIP_ALLOWED_EXT = (".csv", ".xlsx", ".db", ".md")


def _build_outputs_zip_bytes(output_dir: Path, suffix: str = "") -> bytes:
    """Zip output files for the given suffix (indication + country) plus dashboard/* files."""
    output_dir = Path(output_dir)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if output_dir.is_dir():
            for path in sorted(output_dir.iterdir()):
                if path.is_file() and any(path.name.lower().endswith(ext) for ext in _ZIP_ALLOWED_EXT):
                    if not suffix or suffix in path.name:
                        zf.write(path, path.name)
            dashboard_dir = output_dir / "dashboard"
            if dashboard_dir.is_dir():
                for path in sorted(dashboard_dir.iterdir()):
                    if path.is_file() and any(path.name.lower().endswith(ext) for ext in _ZIP_ALLOWED_EXT):
                        if not suffix or suffix in path.name:
                            zf.write(path, f"dashboard/{path.name}")
    buf.seek(0)
    return buf.read()


_UI_OPTIONS_FALLBACK = {
    "indications": [
        # "Other" is first so that when it's selected, CLL (index 1) is still
        # visible at the top of the dropdown list. Streamlit scrolls the list
        # to show the selected item; with Other at 0 and CLL at 1, every
        # possible selection keeps CLL within the visible range.
        {"id": "OTHER",   "label": "Other (specify below)",              "config_suffix": ""},
        {"id": "cll",     "label": "CLL (Chronic Lymphocytic Leukemia)", "config_suffix": "cll"},
        {"id": "hodgkin", "label": "Hodgkin Lymphoma",                   "config_suffix": "hodgkin"},
        {"id": "nhl",     "label": "Non-Hodgkin Lymphoma (NHL)",          "config_suffix": "nhl"},
        {"id": "gastric", "label": "Gastric Cancer (GC)",                "config_suffix": "gc"},
        {"id": "ovarian", "label": "Ovarian Cancer",                     "config_suffix": "ovarian"},
        {"id": "prostate","label": "Prostate Cancer",                    "config_suffix": "prostate"},
    ],
    "countries": [
        {"id": "US",    "label": "United States"},
        {"id": "DE",    "label": "Germany"},
        {"id": "FR",    "label": "France"},
        {"id": "UK",    "label": "United Kingdom"},
        {"id": "CA",    "label": "Canada"},
        {"id": "JP",    "label": "Japan"},
        {"id": "CN",    "label": "China"},
        {"id": "OTHER", "label": "Other (specify below)"},
    ],
}


def load_ui_options():
    config_path = ROOT / "config" / "ui_options.yaml"
    if not config_path.exists():
        return _UI_OPTIONS_FALLBACK
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
        # Validate: ensure both keys are present and non-empty
        if data.get("indications") and data.get("countries"):
            return data
    except Exception:
        pass
    return _UI_OPTIONS_FALLBACK


def main():
    st.set_page_config(
        page_title="Epidemiology Data Tool",
        page_icon="📊",
        layout="wide",
    )

    if "last_run" not in st.session_state:
        st.session_state.last_run = None
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "last_export_dashboard" not in st.session_state:
        st.session_state.last_export_dashboard = True

    # --- Dropdown UX fix ---
    # Streamlit's baseweb Select calls scrollTop on the listbox after rendering to
    # position the currently-selected item. When "Other" (last item) is selected,
    # CLL (first item) scrolls out of view.
    #
    # Fix: CSS `overflow: clip` (unlike `overflow: hidden`) also forbids programmatic
    # scrollTop changes per the CSS spec, so the baseweb JS cannot scroll the list.
    # Combined with a generous max-height (all 7-8 items fit in ~320px), every option
    # is always visible without needing to scroll.
    st.markdown("""
<style>
[data-baseweb="popover"] ul[role="listbox"] {
    overflow: clip !important;
    max-height: 600px !important;
}
</style>
""", unsafe_allow_html=True)

    # --- Header: purpose of the tool ---
    st.title("Epidemiology Data Tool")
    st.markdown("**Get data** for an indication and country. Use the output files for analysis, dashboards, or reporting.")
    st.caption(
        "Choose your options below, then click **Get data**. "
        "After a run, download the **ZIP** (or individual CSVs). "
        "On your own computer, files also appear under the `output` folder next to this app."
    )

    # --- Sidebar ---
    with st.sidebar:
        st.subheader("Last run")
        if st.session_state.last_run:
            lr = st.session_state.last_run
            st.write(f"**Indication:** {lr.get('indication', '-')}")
            st.write(f"**Country:** {lr.get('country', '-')}")
            st.write(f"**Records:** {lr.get('record_count', 0)}")
            st.write(f"**Time:** {lr.get('timestamp', '-')}")
        else:
            st.write("No run yet.")
        st.divider()
        st.markdown("**Need help?** Open **HOW_TO_USE_THIS_TOOL.md** in this folder.")

    options = load_ui_options()
    indications = options.get("indications", [])
    countries = options.get("countries", [])

    indication_labels = [x.get("label", x.get("id", "")) for x in indications]
    indication_ids = [x.get("id", x.get("label", "")) for x in indications]
    country_labels = [x.get("label", x.get("id", "")) for x in countries]
    country_ids = [x.get("id", x.get("label", "")) for x in countries]

    # --- 1. Choose what you need ---
    st.subheader("1. Choose what you need")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        # Use label strings as options so Streamlit renders a type-to-search box.
        # This lets users type "CLL", "Lung", etc. to find the indication instantly.
        ind_label_selected = st.selectbox(
            "Indication",
            options=indication_labels,
            index=1,   # Default to CLL (index 1; "Other" is index 0)
            help="Disease or indication. Click the dropdown and type to search (e.g. 'CLL', 'Lung', 'Breast').",
        )
        ind_index = indication_labels.index(ind_label_selected)
        st.caption("💡 Click and type to search — e.g. type **CLL** to jump straight to it")
    with col2:
        country_label_selected = st.selectbox(
            "Country / Geography",
            options=country_labels,
            index=0,
            help="Geography for the data. Click the dropdown and type to search (e.g. 'US', 'Japan', 'Canada').",
        )
        country_index = country_labels.index(country_label_selected)
        st.caption("💡 Type to search — e.g. **US**, **Japan**, **Canada**")
    indication_label = indication_labels[ind_index]
    indication_id = indication_ids[ind_index]
    country_label = country_labels[country_index]
    country_id = country_ids[country_index]

    # "Other" indication - show a free-text input
    if indication_id == "OTHER":
        custom_indication = st.text_input(
            "Enter indication / disease",
            placeholder="e.g. Lung Cancer, Breast Cancer, Melanoma, AML, NSCLC ...",
            help=(
                "Type any cancer or disease. Common abbreviations are understood "
                "(e.g. 'NSCLC', 'AML', 'HNSCC'). PubMed and ClinicalTrials searches "
                "will be expanded automatically using known synonyms."
            ),
        )
        indication_for_pipeline = custom_indication.strip() if custom_indication and custom_indication.strip() else None
        indication_display = custom_indication.strip() if custom_indication and custom_indication.strip() else "Other"
    else:
        indication_for_pipeline = indication_label
        indication_display = indication_label

    # "Other" country - show a free-text input below the selectors
    if country_id == "OTHER":
        custom_country = st.text_input(
            "Enter country / geography",
            placeholder="e.g. Australia, South Korea, Netherlands, AU, KR ...",
            help=(
                "Type any country name or ISO code. "
                "Common abbreviations and local names are understood "
                "(e.g. 'nippon' -> Japan, 'prc' -> China, 'oz' -> Australia)."
            ),
        )
        country_for_pipeline = custom_country.strip() if custom_country and custom_country.strip() else None
        country_display = custom_country.strip() if custom_country and custom_country.strip() else "Other"
    else:
        country_for_pipeline = country_id      # e.g. "US", "JP", "CN"
        country_display = country_label

    # Output options
    with st.expander("⚙️ Output options", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Checked by default**")
            include_evidence          = st.checkbox("Evidence by Metric (CSV + Excel sheet)", value=True,
                                                     help="Full evidence table - every data point with source, value, year, tier, confidence score and URL.")
            include_kpi_scorecard     = st.checkbox("KPI Scorecard (CSV + Excel sheet)", value=True,
                                                     help="Best value + source range per required metric.")
            include_consolidated_xlsx = st.checkbox("Consolidated Excel workbook", value=True,
                                                     help="extract_consolidated XLSX containing all enabled sheets in one file.")
            include_tool_ready        = st.checkbox("Tool-ready table (CSV)", value=True,
                                                     help="Scenario-ready evidence table that feeds the Excel forecast model.")
            include_evidence_summary  = st.checkbox("Evidence summary (.md)", value=True,
                                                     help="Human-readable summary of key numbers, top sources and gaps.")
            include_seer_sheet      = st.checkbox("SEER Trends sheet (Excel)", value=True,
                                                   help="Adds a 'SEER Trends' tab to the consolidated Excel with 1975–2024 incidence / mortality / survival data")
            include_forecast        = st.checkbox("Forecast projections", value=True,
                                                   help="Generates forecast CSV with 2018–2029 scenario projections")
            export_dashboard        = st.checkbox("Dashboard export (BI / Tableau)", value=True,
                                                   help="Creates output/dashboard/ folder with aggregated CSVs and SQLite DB for Power BI or Tableau")
        with col_b:
            st.markdown("**Unchecked by default**")
            export_insightace            = st.checkbox("InsightACE format", value=False,
                                                        help="insightace_epi CSV - wide year-column pivot for the InsightACE tool")
            export_insights_summary      = st.checkbox("Insights summary", value=False,
                                                        help="insights_summary CSV - broad coverage view across 90+ metrics")
            export_source_log            = st.checkbox("Source log", value=False,
                                                        help="source_log CSV - records which data sources were loaded and row counts")
            export_reference_links       = st.checkbox("Reference links", value=False,
                                                        help="reference_links CSV - curated source URLs for this indication")
            export_reconciliation        = st.checkbox("Reconciliation table", value=False,
                                                        help="reconciliation CSV - recommended best value per metric with source comparison")
            export_kpi_conflicts         = st.checkbox("KPI conflicts", value=False,
                                                        help="kpi_conflicts CSV - flags where two sources give different values for the same metric/year")
            export_white_space           = st.checkbox("White-space summary", value=False,
                                                        help="white_space_summary.md - gap analysis showing which required metrics have no source")
            export_validation_report_file = st.checkbox("Validation report", value=False,
                                                         help="validation_report CSV - pipeline QA checks (duplicate keys, missing fields)")

    # Optional: evidence upload
    uploaded_file = st.file_uploader(
        "Use your own evidence CSV (optional)",
        type=["csv"],
        help="If you have your own evidence file, upload it. Otherwise the tool uses built-in data.",
    )
    evidence_path_for_run = None
    if uploaded_file is not None:
        temp_dir = ROOT / "output" / "temp_upload"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"upload_{indication_id}_{country_id}.csv"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        evidence_path_for_run = temp_path
        st.caption(f"Using: {uploaded_file.name}")

    # PubMed (expanded queries + stub rows) is always included for every run.
    use_pubmed = True
    add_pubmed_stubs = True

    # --- 2. Get the data ---
    st.subheader("2. Get the data")
    run_clicked = st.button("Get data", type="primary", use_container_width=True)

    if run_clicked:
        if indication_id == "OTHER" and not indication_for_pipeline:
            st.warning("Please enter an indication / disease name before running.")
        elif country_id == "OTHER" and not country_for_pipeline:
            st.warning("Please enter a country / geography name before running.")
        else:
            with st.spinner("Collecting and building data…"):
                result = run_pipeline(
                    indication=indication_for_pipeline,
                    country=country_for_pipeline,
                    evidence_path=evidence_path_for_run,
                    config_dir=ROOT / "config",
                    output_dir=ROOT / "output",
                    metrics_config_path=None,
                    include_evidence=include_evidence,
                    include_kpi_scorecard=include_kpi_scorecard,
                    include_consolidated_xlsx=include_consolidated_xlsx,
                    include_tool_ready=include_tool_ready,
                    include_evidence_summary=include_evidence_summary,
                    export_dashboard=export_dashboard,
                    include_forecast=include_forecast,
                    use_pubmed=use_pubmed,
                    add_pubmed_stubs=add_pubmed_stubs,
                    export_insightace=export_insightace,
                    export_insights_summary=export_insights_summary,
                    export_source_log=export_source_log,
                    export_reference_links=export_reference_links,
                    include_seer_sheet=include_seer_sheet,
                    export_reconciliation=export_reconciliation,
                    export_kpi_conflicts=export_kpi_conflicts,
                    export_white_space=export_white_space,
                    export_validation_report_file=export_validation_report_file,
                )
                st.session_state.last_run = {
                    "indication": indication_for_pipeline,
                    "country": country_for_pipeline,
                    "record_count": result.get("record_count", 0),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "success": result.get("success", False),
                }
                st.session_state.last_result = result
                st.session_state.last_export_dashboard = export_dashboard

    # Render from session_state so download-button reruns do not hide this block
    result = st.session_state.get("last_result")
    if result and result.get("success"):
        lr = st.session_state.last_run or {}
        ind_label = lr.get("indication") or ""
        country_code = lr.get("country") or ""
        ind_safe = str(ind_label).replace(" ", "_")
        c_safe = str(country_code).replace(" ", "_")
        suffix = f"{ind_safe}_{c_safe}"
        had_dashboard = st.session_state.get("last_export_dashboard", True)

        st.success("Your data is ready.")
        n = result.get("record_count", 0)
        st.info(
            f"**{n}** evidence row(s) processed. "
            "Use **Download all outputs (ZIP)** below to save everything. "
            "When you run this app on your own machine, files are also written under the **`output`** folder."
        )

        # --- 3. Your outputs ---
        st.subheader("3. Your outputs")
        zip_bytes = _build_outputs_zip_bytes(ROOT / "output", suffix=suffix)
        zip_name = f"epidemiology_outputs_{suffix}.zip"
        st.download_button(
            label="Download all outputs (ZIP)",
            data=zip_bytes,
            file_name=zip_name,
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="dl_zip_all",
            help="Contains CSVs (and dashboard folder files) from this run.",
        )
        st.caption(
            "In **Chrome**, if **Ask where to save each file before downloading** is on "
            "(Settings → Downloads), you can pick the folder when the ZIP saves."
        )
        st.markdown("Included file names (also inside the ZIP):")
        st.markdown(f"- **Evidence** (sources & values) → `evidence_{suffix}.csv`")
        st.markdown(f"- **Tool-ready table** → `tool_ready_{suffix}.csv`")
        st.markdown(f"- **KPI** (coverage & gaps) → `kpi_table_{suffix}.csv`")
        st.markdown(f"- **InsightACE export** → `insightace_epi_{suffix}.csv`")
        if had_dashboard:
            st.markdown("- **Dashboard pack** (Tableau / Power BI) → folder `dashboard/`")

        # Validation report (if any)
        if result.get("validation_report"):
            with st.expander("Validation notes"):
                for e in result["validation_report"]:
                    level = e.get("level", "info")
                    msg = e.get("message", "")
                    if level == "error":
                        st.error(msg)
                    else:
                        st.warning(msg)

        # Preview and download (DataFrames restored from session_state on each rerun)
        if result.get("evidence_df") is not None and not result["evidence_df"].empty:
            with st.expander("Preview: Evidence"):
                st.dataframe(result["evidence_df"], use_container_width=True, hide_index=True)
            csv_ev = result["evidence_df"].to_csv(index=False).encode("utf-8")
            st.download_button("Download evidence (CSV)", data=csv_ev, file_name=f"evidence_{suffix}.csv", mime="text/csv", key="dl_evidence")
        if result.get("kpi_df") is not None and not result["kpi_df"].empty:
            with st.expander("Preview: KPI (coverage & gaps)"):
                st.dataframe(result["kpi_df"], use_container_width=True, hide_index=True)
            csv_kpi = result["kpi_df"].to_csv(index=False).encode("utf-8")
            st.download_button("Download KPI (CSV)", data=csv_kpi, file_name=f"kpi_table_{suffix}.csv", mime="text/csv", key="dl_kpi")
        if result.get("tool_ready_df") is not None and not result["tool_ready_df"].empty:
            csv_tr = result["tool_ready_df"].to_csv(index=False).encode("utf-8")
            st.download_button("Download tool-ready table (CSV)", data=csv_tr, file_name=f"tool_ready_{suffix}.csv", mime="text/csv", key="dl_tool_ready")

        # --- 4. What to do next ---
        st.subheader("4. What to do next")
        st.markdown("""
        Use the output files for your work:
        - **Unzip** - Extract the ZIP, then open CSVs from the folder you chose (or from Downloads).
        - **Open in Excel** - Open any CSV to review or share.
        - **Use in Power BI or Tableau** - Connect to the `dashboard` subfolder inside the ZIP (see **docs/DASHBOARD_AND_ANALYTICS.md**).
        - **Feed another system** - Use the tool-ready or InsightACE CSV as input for your models or platform.
        - **Share** - Send the ZIP or individual CSVs to a colleague.
        - **Check quality** - Use the KPI table to see coverage and gaps; add evidence and run again if needed.
        """)
    elif result and not result.get("success"):
        st.error("Something went wrong.")
        st.write(result.get("message", ""))
        if result.get("validation_report"):
            with st.expander("Details"):
                for e in result["validation_report"]:
                    st.warning(e.get("message", ""))

    st.divider()
    st.caption("This tool collects evidence from configured sources, builds tool-ready tables and KPI, and optionally exports a dashboard pack. For full instructions, see **HOW_TO_USE_THIS_TOOL.md**.")


if __name__ == "__main__":
    main()
