# Deploy the Epidemiology Data Tool for Client Access

This guide sets up a **private GitHub repo** and deploys the web app so you and your client can access it via a URL (no code sharing).

---

## Before you deploy (policy and approval)

**You must confirm externally before any world-reachable URL goes live.** This project is covered by the PharmaACE NDA and internal-use expectations.

Use this checklist (see [docs/CONFIDENTIALITY.md](docs/CONFIDENTIALITY.md) for full wording):

| Step | Action |
|------|--------|
| 1 | **Sponsor / PharmaACE:** Obtain explicit approval that a hosted URL (even “link only”) is allowed under the NDA and current practicum agreement. |
| 2 | **Course / instructor:** Confirm deployment meets course rules for confidential client work. |
| 3 | **Data:** Do not put confidential indication data or client-only artifacts in a **public** repository. Keep the GitHub repo **Private** unless PharmaACE approves otherwise. |
| 4 | **Access model:** If a fully public URL is not allowed, use link discipline (private repo + trusted recipients), or add authentication in front of the app (not included in this repo; use your platform’s features or a reverse proxy). |

Until steps 1–3 are satisfied, deploy only to **local** or **approved private** environments.

**Streamlit Cloud (full checklist):** [STREAMLIT_CLOUD_DEPLOY.md](STREAMLIT_CLOUD_DEPLOY.md).

**Streamlit or Render (short comparison):** [docs/CLOUD_URL_QUICKSTART.md](docs/CLOUD_URL_QUICKSTART.md).

---

## Choose a platform: Streamlit Cloud vs Render

| Factor | [Streamlit Cloud](https://share.streamlit.io) (`app.py`) | [Render](https://render.com) ([render.yaml](render.yaml), Flask `app_web.py`) |
|--------|-----------------------------------------------------------|--------------------------------------------------------------------------------|
| **Best for** | Quick UI share; team already uses Streamlit locally | Same web flow as `python app_web.py`; single-page API + downloads |
| **Entry file** | `app.py` | `app_web:app` via Gunicorn |
| **Selenium / headless Chrome** | Often **limited or unavailable** on free tier; scraping may fail partially | More control on paid tiers; still **no Chrome in default** [requirements.txt](requirements.txt) build; heavy scraping may need a custom Docker image |
| **Long pipeline runs** | App may hit **timeout** limits; prefer shorter runs or upgrade tier | Gunicorn uses **`--timeout 300`** in [render.yaml](render.yaml); very long runs may still need background jobs or local runs |
| **Disk** | **Ephemeral**; `output/` may not persist across restarts | Same on default web service; treat downloads as the durable handoff |
| **Public URL** | Yes, once deployed | Yes, once deployed |

**Rule of thumb:** Prefer **Streamlit Cloud** if your workflow is already Streamlit-first and you accept cloud limits on scraping. Prefer **Render** if you want the **Flask** experience to match local `app_web.py` and you want the blueprint in-repo.

---

## Step 1: Create a Private GitHub Repository

1. Go to [https://github.com/new](https://github.com/new)
2. **Repository name:** e.g. `epidemiology-data-tool`
3. **Description:** (optional)
4. **Private** (select Private)
5. Do **not** initialize with README, .gitignore, or license if you already have them in the folder you will push
6. Click **Create repository**

**Repository root:** Push the contents of the **`Data Pipeline tool`** folder as the **root** of the repo (so `app.py`, `app_web.py`, and `requirements.txt` sit at the top level). If your Git repo is a parent folder (e.g. whole practicum), set **Root Directory** in Render to `Data Pipeline tool`, or use a submodule / separate repo for deployment.

---

## Step 2: Push Your Code to GitHub

In your project folder, run:

```bash
cd "path/to/Data Pipeline tool"

# Add the remote (replace YOUR_USERNAME and YOUR_REPO with your GitHub username and repo name)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# Push
git branch -M main
git push -u origin main
```

---

## Step 3a: Deploy on Streamlit Cloud (Streamlit UI)

1. Go to [https://share.streamlit.io](https://share.streamlit.io)
2. **Sign in with GitHub**
3. Click **New app**
4. When prompted, **authorize Streamlit to access your repositories** (including private repos)
5. Fill in:
   - **Repository:** `YOUR_USERNAME/YOUR_REPO`
   - **Branch:** `main`
   - **Main file path:** `app.py`
6. Click **Deploy**

After a few minutes, you get a URL like `https://your-app-name.streamlit.app`.  
**Share this URL only with people allowed under your NDA and approvals above.**

---

## Step 3b: Deploy on Render (Flask / `app_web.py`)

1. Sign up at [https://render.com](https://render.com) and connect **GitHub**.
2. **New** → **Blueprint** (or **Web Service** if you prefer manual config).
3. Select the repo that has [render.yaml](render.yaml) at the blueprint path (repo root if you pushed `Data Pipeline tool` as root).
4. If the repo root is the **parent** of `Data Pipeline tool`, create the service manually instead: **Web Service** → set **Root Directory** to `Data Pipeline tool`, **Runtime** Python, **Build** `pip install -r requirements.txt`, **Start** `gunicorn -b 0.0.0.0:$PORT -w 1 --timeout 300 app_web:app`.
5. Deploy; open the URL Render assigns.

---

## Local smoke test (before or after cloud deploy)

Verify production-style serving on your machine (no code edits required):

```bash
cd "path/to/Data Pipeline tool"
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
gunicorn -b 127.0.0.1:8765 -w 1 --timeout 300 app_web:app
```

In another terminal:

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/
```

Expect **`200`**. Stop Gunicorn with Ctrl+C.

**After a cloud deploy:** Open the live URL, run **one** indication/country you are allowed to use, confirm the UI completes and **downloads** or **output** behave as expected. If scraping is disabled or fails in cloud, fall back to **manual evidence CSV** per [HOW_TO_USE_THIS_TOOL.md](HOW_TO_USE_THIS_TOOL.md).

---

## Important Notes

- **Private repo + public app:** The repo can stay private while the **app URL** is reachable by anyone who has the link. Treat the URL as confidential unless policy says otherwise.
- **Pipeline behavior in cloud:** Web scraping (PubMed, Selenium, etc.) may hit **limits** or missing browsers. Full extraction may remain **local-only** unless you add a suitable container image and approvals.
- **Ephemeral disk:** Do not rely on server-side `output/` lasting across restarts; use **downloads** or connect persistent storage if you need retention on the host.
- **Secrets:** Use the platform’s **secrets / environment variables** for any API keys (Streamlit **Secrets**, Render **Environment**).
- **Production:** Cloud hosts should use **Gunicorn** (as in [render.yaml](render.yaml)), not `app.run(debug=True)` from [app_web.py](app_web.py).
