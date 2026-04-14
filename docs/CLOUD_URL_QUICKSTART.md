# Quickstart: Get a shareable URL (Streamlit Cloud or Render)

Use this when a teammate (or reviewer) needs a **link** to open the tool in a browser **without** installing Python locally.

**Important:** Creating the actual URL requires **your** GitHub account and signing in to **Streamlit** or **Render**. No automated step in this repo can finish that for you. After deploy, the platform shows something like `https://….streamlit.app` or `https://….onrender.com`.

**NDA:** Follow [CONFIDENTIALITY.md](CONFIDENTIALITY.md) and [DEPLOY.md](../DEPLOY.md) (approval checklist) before making any app world-reachable.

---

## 0. Prereqs

1. **GitHub:** A **private** repository whose **root** is the contents of the `Data Pipeline tool` folder (so `app.py`, `app_web.py`, and `requirements.txt` are at the repo root).
2. **Push:** Commit and push a state that **builds cleanly** (fix merge conflicts and run `pip install -r requirements.txt` locally first if unsure).
3. **Entry files:**
   - **Streamlit Cloud:** [app.py](../app.py) (Streamlit UI).
   - **Render:** [app_web.py](../app_web.py) via [render.yaml](../render.yaml) (Flask + Gunicorn).

Pick **one** platform unless you want two URLs.

---

## Option A: Streamlit Community Cloud (Streamlit webpage)

Use the **complete** step list (GitHub layout, local check, deploy clicks): **[STREAMLIT_CLOUD_DEPLOY.md](../STREAMLIT_CLOUD_DEPLOY.md)**.

Summary:

1. Repo root must contain `app.py` and `requirements.txt`.
2. [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub → **New app** → **Main file path:** `app.py` → **Deploy**.
3. Copy `https://<name>.streamlit.app` and share for testing.

**Notes:** Free tier **spin down**; **Selenium** may differ from local; use **upload CSV** for stable demos. Secrets: Streamlit **Settings → Secrets**.

---

## Option B: Render (Flask webpage, matches `app_web.py`)

1. Open [https://render.com](https://render.com) and sign in with GitHub.
2. **New → Blueprint** (if [render.yaml](../render.yaml) is at the repo root) **or** **New → Web Service** and connect the same repo.
3. If the repo root is **not** this folder (monorepo), set **Root Directory** to `Data Pipeline tool` and use:
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `gunicorn -b 0.0.0.0:$PORT -w 1 --timeout 300 app_web:app`
4. Deploy and open the **`.onrender.com`** URL Render assigns.

**Share:** That HTTPS URL is what your teammate opens.

**Notes:**

- Free web services also **sleep** when idle; cold starts apply.
- Same caveats as Streamlit for **scraping** and **ephemeral disk** (see [DEPLOY.md](../DEPLOY.md)).

---

## After deploy

- Test **Get data** once yourself before sharing the link.
- Treat the URL like **confidential** unless policy says otherwise (anyone with the link may be able to use the app on free tiers).

---

## If the build fails

- Check the platform **Logs** for missing dependencies or import errors.
- Confirm **Python** version: Render reads [runtime.txt](../runtime.txt) when present.
- Ensure `app.py` exists at repo root for Streamlit Cloud.
