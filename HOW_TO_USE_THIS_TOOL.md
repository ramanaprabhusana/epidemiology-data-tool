# How to Use This Tool

**This tool helps you get epidemiology data for an indication and country.** You choose what you need, run it once, and then use the output files for your next steps (analysis, dashboards, reporting).

**What this tool does:** Collects and organizes evidence from configured sources, builds a tool-ready table and KPI, and writes everything to the `output` folder. The workflow is **streamlined**: choose indication and country, get data, then use the files for your next steps.  
**What you do next:** Use those files in Excel, Power BI, Tableau, or another system-the tool only *gets the data*; your analysis and reporting are the next steps.

---

## What you need before you start

- This folder (the whole **Data Pipeline tool** project) on your computer.
- **Python 3** installed. If you’re not sure, ask your IT or the person who gave you the tool.

---

## Step 1: Open the tool (first time only)

**Easiest - no terminal needed:**  
After the one-time setup below, you can start the tool by **double-clicking** a launcher in this folder:

- **Windows:** Double-click **`Start_Web_App.bat`**. A window will open; your browser will open to the tool. Keep the window open while using the tool.
- **Mac:** Double-click **`Start_Web_App.command`**. If macOS asks “cannot be opened because it is from an unidentified developer,” right‑click the file → **Open** → **Open** once. Your browser will open to the tool. Keep the window open while using the tool.

**One-time setup** (someone with Terminal/Command Prompt can do this once, or you can follow these steps):

1. Open **Terminal** (Mac/Linux) or **Command Prompt** (Windows).
2. Go to this project folder, for example:
   ```text
   cd "path/to/Data Pipeline tool"
   ```
3. Create and activate the environment (only once):
   ```text
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   On Windows use: `\.venv\Scripts\activate`
4. Install dependencies (only once):
   ```text
   pip install -r requirements.txt
   ```
5. Start the tool using **one** of these options:

   **Option A - Streamlined web page**  
   ```text
   python app_web.py
   ```
   Then open in your browser: **http://127.0.0.1:5000** - simple form, get data, download links.

   **Option B - Interactive app**  
   ```text
   streamlit run app.py
   ```
   Your browser will open automatically (or go to the URL shown). Same flow with live previews and download buttons.

**Next times:** Double-click **`Start_Web_App.bat`** (Windows) or **`Start_Web_App.command`** (Mac), or activate the environment and run `python app_web.py` or `streamlit run app.py`.

---

## Step 2: Get the data

1. **Indication** - Choose the disease/indication (e.g. CLL, Lung Cancer).
2. **Country** - Choose the geography (e.g. United States, UK).
3. *(Optional)* Upload your own evidence CSV if you have one; otherwise the tool uses built-in templates.
4. Click **“Get data”**.
5. Wait until you see **“Your data is ready.”**

That’s it. The tool has collected and built the data for your chosen indication and country.  
On the **streamlined web page** you can use the download links; in the **interactive app** you can use the download buttons or open the `output` folder.

---

## Step 3: Where your data is

After a successful run, all outputs are in the **`output`** folder inside this project:

| What it is | File / folder | Use it for |
|------------|----------------|------------|
| **Evidence** (sources, values) | `output/evidence_<Indication>_<Country>.csv` | See what sources were used and the raw numbers. |
| **Tool-ready table** | `output/tool_ready_<Indication>_<Country>.csv` | Main table for analysis or ingestion into another system. |
| **KPI / coverage** | `output/kpi_table_<Indication>_<Country>.csv` | See which metrics are covered and where there are gaps. |
| **InsightACE export** | `output/insightace_epi_<Indication>_<Country>.csv` | Ready for the InsightACE epidemiology view (EPI Parameter × Year). |
| **Dashboard pack** | `output/dashboard/` | CSVs + one database file for Tableau or Power BI. |

You can **download** some of these directly from the app after the run, or **open the `output` folder** in Explorer/Finder and use the files from there.

---

## Step 4: What to do next (your next steps)

Use the output files in whatever way you need:

- **Open in Excel** - Open any of the CSV files to review, filter, or share.
- **Use in Power BI or Tableau** - Connect to the `output/dashboard` folder (or the `.db` file there) and build or refresh your dashboards. See the doc *Dashboard & Advanced Analytics* in the `docs` folder for connection steps.
- **Feed another system** - Use `tool_ready_*.csv` or `insightace_epi_*.csv` as the input format for your models or platforms.
- **Share with a colleague** - Send the whole `output` folder or the specific CSVs they need.
- **Check quality** - Use `kpi_table_*.csv` to see coverage and gaps; fix or add evidence and run again if needed.

The tool only **gets the data**. All analysis, forecasting, and reporting are your next steps using these files.

---

## If something goes wrong

- **“No evidence records”** - The tool didn’t find any data for your choice. Try another indication/country or upload an evidence CSV that has data for that combination.
- **App won’t start** - Make sure you’re in the project folder, the environment is activated (`.venv`), and you ran `pip install -r requirements.txt`.
- **Need a different indication or country** - Ask the person who gave you the tool to add it (or see the *Quick start* / *Handoff* docs in the `docs` folder for how new options are added).

---

## Summary

1. **Open the tool** once: `streamlit run app.py` from this folder (after setup).
2. **Choose** indication and country, then click **“Get data.”**
3. **Use** the files in the `output` folder for your next steps.

You don’t need to edit any code. You can use:
- **Streamlined web page:** `python app_web.py` then open http://127.0.0.1:5000
- **Interactive app:** `streamlit run app.py`
- **Command line:** `python run_tool.py --indication CLL --country US` (see README or Quick start for more options).
