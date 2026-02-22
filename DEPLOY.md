# Deploy the Epidemiology Data Tool for Client Access

This guide sets up a **private GitHub repo** and deploys the web app so you and your client can access it via a URL (no code sharing).

---

## Step 1: Create a Private GitHub Repository

GitHub CLI is not installed, so create the repo manually:

1. Go to [https://github.com/new](https://github.com/new)
2. **Repository name:** e.g. `epidemiology-data-tool`
3. **Description:** (optional)
4. **Private** (select Private)
5. Do **not** initialize with README, .gitignore, or license (we have them)
6. Click **Create repository**

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

## Step 3: Deploy on Streamlit Cloud (Client Gets Webpage Access)

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
**Share this URL with your client.** They can use the web interface without seeing your code. Your repo stays private.

---

## Important Notes

- **Private repo + public app:** The repo remains private. The deployed app URL is public; anyone with the link can use it.
- **Pipeline behavior in cloud:** The app uses templates and manual evidence by default. Web scraping (PubMed, etc.) may have limits on Streamlit Cloud. For full extraction features, consider running locally or using a different host (e.g. Render) with more resources.
- **Secrets:** If you add API keys later, use Streamlit Cloud's "Secrets" in the app settings.
