"""
Epidemiology Data Tool — Get data for an indication and country, then use the outputs for your next steps.
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


def _build_outputs_zip_bytes(output_dir: Path) -> bytes:
    """Zip top-level output files plus output/dashboard/* (same layout as Flask /download_zip)."""
    output_dir = Path(output_dir)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if output_dir.is_dir():
            for path in sorted(output_dir.iterdir()):
                if path.is_file() and any(path.name.lower().endswith(ext) for ext in _ZIP_ALLOWED_EXT):
                    zf.write(path, path.name)
            dashboard_dir = output_dir / "dashboard"
            if dashboard_dir.is_dir():
                for path in sorted(dashboard_dir.iterdir()):
                    if path.is_file() and any(path.name.lower().endswith(ext) for ext in _ZIP_ALLOWED_EXT):
                        zf.write(path, f"dashboard/{path.name}")
    buf.seek(0)
    return buf.read()


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
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "last_export_dashboard" not in st.session_state:
        st.session_state.last_export_dashboard = True

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
        zip_bytes = _build_outputs_zip_bytes(ROOT / "output")
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
        - **Unzip** — Extract the ZIP, then open CSVs from the folder you chose (or from Downloads).
        - **Open in Excel** — Open any CSV to review or share.
        - **Use in Power BI or Tableau** — Connect to the `dashboard` subfolder inside the ZIP (see **docs/DASHBOARD_AND_ANALYTICS.md**).
        - **Feed another system** — Use the tool-ready or InsightACE CSV as input for your models or platform.
        - **Share** — Send the ZIP or individual CSVs to a colleague.
        - **Check quality** — Use the KPI table to see coverage and gaps; add evidence and run again if needed.
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
