# Deploy the Streamlit app to Streamlit Community Cloud (shareable URL)

This is the **full checklist** to get a **`https://….streamlit.app`** link so someone can test the tool in a browser without installing Python.

**What only you can do:** Sign in at [share.streamlit.io](https://share.streamlit.io) with GitHub and click **Deploy**. This repo cannot complete that login for you.

**NDA / course rules:** Read [docs/CONFIDENTIALITY.md](docs/CONFIDENTIALITY.md) and the checklist in [DEPLOY.md](DEPLOY.md) before publishing a URL.

---

## 1. Repo layout (required)

Streamlit Cloud expects this project **at the root of a GitHub repository** (not buried inside a monorepo without extra settings):

- `app.py` at the top level (Streamlit entrypoint)
- `requirements.txt` at the top level
- `src/`, `config/`, `templates/`, etc. as in this folder

If your GitHub repo currently has a **parent** folder above `Data Pipeline tool`, either:

- Create a **new repo** and copy **only** the contents of `Data Pipeline tool/` into the root, or  
- Use Streamlit’s advanced options if they expose a **subdirectory** (Community Cloud is simplest with **repo root = this project**).

---

## 2. Local sanity check (once)

From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Confirm the app loads. Press Ctrl+C when done.

---

## 3. Push to a GitHub repo

Use a **Private** repository unless PharmaACE and your instructor allow public.

```bash
cd "/path/to/Data Pipeline tool"
git init
git add .
git commit -m "Initial commit for Streamlit Cloud"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

Resolve any **merge conflicts** in your real tree before pushing. Cloud builds use whatever is on GitHub.

---

## 4. Create the app on Streamlit Community Cloud

1. Open **[https://share.streamlit.io](https://share.streamlit.io)**.
2. **Sign in with GitHub** and authorize Streamlit to see the repo (including **private** repos).
3. Click **Create app** (or **New app**).
4. Set:
   - **Repository:** `YOUR_USER/YOUR_REPO`
   - **Branch:** `main` (or your default branch)
   - **Main file path:** `app.py`
5. Click **Deploy**.

Wait for the build. When it succeeds, copy the app URL (example shape: `https://YOUR-APP-NAME.streamlit.app`).

**Share that URL** with your teammate for testing.

---

## 5. Files Streamlit Cloud uses (already in this project)

| File / folder | Role |
|---------------|------|
| [app.py](app.py) | Main Streamlit script (required) |
| [requirements.txt](requirements.txt) | `pip install` during build |
| [.streamlit/config.toml](.streamlit/config.toml) | Server options (headless, etc.) |
| [runtime.txt](runtime.txt) | Optional Python pin (Render-oriented; Cloud may ignore or respect similar conventions; if build fails, set Python version in the Cloud **Settings** UI) |

---

## 6. Optional: secrets

If you add API keys later, use **Streamlit Cloud → App → Settings → Secrets**. Do **not** commit real secrets.

Example template (for local copy only): [.streamlit/secrets.toml.example](.streamlit/secrets.toml.example).

---

## 7. What often breaks on free Cloud

- **Cold start:** First open after idle can take a minute.
- **Selenium / heavy scraping:** May not match your laptop. For demos, use **built-in templates** or **upload a CSV** in the app.
- **Disk:** Treat the app as **stateless**; downloads in the UI are the durable handoff.

---

## 8. Redeploy after changes

Push commits to GitHub. Streamlit Cloud usually **rebuilds automatically**; you can also use **Reboot app** in the dashboard.

---

## 9. Other hosting

For Flask (`app_web.py`) on Render instead, see [render.yaml](render.yaml) and [DEPLOY.md](DEPLOY.md).
