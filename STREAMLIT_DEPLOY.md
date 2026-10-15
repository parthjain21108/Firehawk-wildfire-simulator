# Deploy FireHawk to Streamlit Community Cloud

This repository is structured so `app.py` and `requirements.txt` are at the repository root.

## 1. Create a GitHub repository

1. Go to https://github.com/new and sign in.
2. Repository name: `firehawk-wildfire-simulator`.
3. Choose **Public** if you are comfortable sharing the project source code; otherwise choose Private and later authorize Streamlit to access private repositories.
4. For the easiest first upload, leave **Add a README**, `.gitignore`, and license unchecked; this folder already has those files.
5. Click **Create repository**.

## 2. Upload the project files

1. Open the extracted folder containing this `STREAMLIT_DEPLOY.md`.
2. In the new, empty GitHub repository, choose **Add file → Upload files**.
3. Upload the *contents of this folder* (not a parent folder named `FireHawk_Streamlit_Deploy`). At repository root, you must see `app.py`, `requirements.txt`, and the `firehawk/`, `results/`, `docs/`, and `tests/` folders.
4. Enter commit message `Add FireHawk wildfire response simulator` and commit to `main`.

## 3. Deploy on Streamlit Community Cloud

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Authorize Streamlit to access the repository if asked.
3. Click **Create app** (or **New app**), then choose the existing-repository option.
4. Repository: `YOUR_GITHUB_USERNAME/firehawk-wildfire-simulator`.
5. Branch: `main`.
6. Main file path: `app.py`.
7. Open **Advanced settings** and select Python **3.11** if available.
8. Click **Deploy**. Initial setup may take a few minutes while dependencies install.

## 4. If deployment fails

- Confirm `app.py` is at the repository root, not nested inside another folder.
- Confirm `requirements.txt` is at the root and contains `streamlit` and `pandas`.
- Open **Manage app → Logs** in Streamlit Cloud and read the first traceback. Fix the reported error, commit the fix to GitHub, and Streamlit will redeploy.
- No API keys or secrets are required by FireHawk.

## Local run

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```
