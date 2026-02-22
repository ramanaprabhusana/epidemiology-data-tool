"""
Epidemiology Data Tool — Get data for an indication and country, then use the outputs for your next steps.
Designed so someone receiving the tool can run it without editing code.
"""

import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import yaml
import pandas as pd

from src.pipeline.runner import run_pipeline


def load_ui_options():
    config_path = ROOT / "config" / "ui_options.yaml"
    if not config_path.exists():
        return {"indications": [{"id": "cll", "label": "CLL", "config_suffix": "cll"}], "countries": [{"id": "US", "label": "United States"}]}
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    st.set_page_config(
        page_title="Epidemiology Data Tool",
        page_icon="📊",
        layout="wide",
    )

    if "last_run" not in st.session_state:
        st.session_state.last_run = None

    # --- Header: purpose of the tool ---
    st.title("Epidemiology Data Tool")
    st.markdown("**Get data** for an indication and country. Use the output files for analysis, dashboards, or reporting.")
    st.caption("Choose your options below, then click **Get data**. Your files will be in the `output` folder.")

    # --- Sidebar ---
    with st.sidebar:
        st.subheader("Last run")
        if st.session_state.last_run:
            lr = st.session_state.last_run
            st.write(f"**Indication:** {lr.get('indication', '—')}")
            st.write(f"**Country:** {lr.get('country', '—')}")
            st.write(f"**Records:** {lr.get('record_count', 0)}")
            st.write(f"**Time:** {lr.get('timestamp', '—')}")
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
        ind_index = st.selectbox(
            "Indication",
            range(len(indication_labels)),
            format_func=lambda i: indication_labels[i],
            index=0,
            help="Disease or indication (e.g. CLL, Lung Cancer).",
        )
    with col2:
        country_index = st.selectbox(
            "Country / Geography",
            range(len(country_labels)),
            format_func=lambda i: country_labels[i],
            index=0,
            help="Geography for the data (e.g. US, UK).",
        )
    with col3:
        export_dashboard = st.checkbox("Include dashboard export", value=True, help="Also create files in output/dashboard for Tableau or Power BI.")

    indication_label = indication_labels[ind_index]
    indication_id = indication_ids[ind_index]
    country_label = country_labels[country_index]
    country_id = country_ids[country_index]
    indication_for_pipeline = indication_label

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

    use_pubmed = st.checkbox("Also search PubMed for literature", value=False, help="Adds search results (PMIDs) as silver-tier evidence.")

    # --- 2. Get the data ---
    st.subheader("2. Get the data")
    run_clicked = st.button("Get data", type="primary", use_container_width=True)

    if run_clicked:
        with st.spinner("Collecting and building data…"):
            result = run_pipeline(
                indication=indication_for_pipeline,
                country=country_id,
                evidence_path=evidence_path_for_run,
                config_dir=ROOT / "config",
                output_dir=ROOT / "output",
                metrics_config_path=None,
                export_dashboard=export_dashboard,
                include_forecast=True,
                use_pubmed=use_pubmed,
                add_pubmed_stubs=use_pubmed,
            )
            st.session_state.last_run = {
                "indication": indication_for_pipeline,
                "country": country_id,
                "record_count": result.get("record_count", 0),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "success": result.get("success", False),
            }
            st.session_state.last_result = result

        if result["success"]:
            st.success("Your data is ready.")
            n = result.get("record_count", 0)
            st.info(f"**{n}** evidence row(s) processed. Outputs are in the **`output`** folder in this project.")

            # --- 3. Your outputs ---
            st.subheader("3. Your outputs")
            ind_safe = indication_for_pipeline.replace(" ", "_")
            c_safe = country_id.replace(" ", "_")
            suffix = f"{ind_safe}_{c_safe}"
            st.markdown("All files are in the **`output`** folder. Names include your indication and country:")
            st.markdown(f"- **Evidence** (sources & values) → `evidence_{suffix}.csv`")
            st.markdown(f"- **Tool-ready table** → `tool_ready_{suffix}.csv`")
            st.markdown(f"- **KPI** (coverage & gaps) → `kpi_table_{suffix}.csv`")
            st.markdown(f"- **InsightACE export** → `insightace_epi_{suffix}.csv`")
            if export_dashboard:
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

            # Preview and download
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
            - **Open in Excel** — Open any CSV from the `output` folder to review or share.
            - **Use in Power BI or Tableau** — Connect to `output/dashboard` (see **docs/DASHBOARD_AND_ANALYTICS.md**).
            - **Feed another system** — Use the tool-ready or InsightACE CSV as input for your models or platform.
            - **Share** — Send the `output` folder or the CSVs to a colleague.
            - **Check quality** — Use the KPI table to see coverage and gaps; add evidence and run again if needed.
            """)
        else:
            st.error("Something went wrong.")
            st.write(result["message"])
            if result.get("validation_report"):
                with st.expander("Details"):
                    for e in result["validation_report"]:
                        st.warning(e.get("message", ""))

    st.divider()
    st.caption("This tool collects evidence from configured sources, builds tool-ready tables and KPI, and optionally exports a dashboard pack. For full instructions, see **HOW_TO_USE_THIS_TOOL.md**.")


if __name__ == "__main__":
    main()
