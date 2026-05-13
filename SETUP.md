# Dashboard setup — step-by-step

This guide walks through deploying the dashboard. Allow ~30 minutes the
first time; subsequent deploys are automatic.

The architecture: your private strategy repo runs daily via GitHub Actions,
generates JSON files, and pushes the sanitised slice to this public repo.
GitHub Pages serves the public repo. Family bookmarks the URL.

## Prerequisites

- A GitHub account
- Your private `claude-speculation-fund` repo already on GitHub
- 15 minutes

## Step 1 — Create the public dashboard repo

1. Go to https://github.com/new
2. Repository name: `csf-dashboard` (or whatever you prefer — remember the name)
3. Visibility: **Public** (required for free GitHub Pages)
4. Initialise with README: leave UNCHECKED (we have our own)
5. Click "Create repository"

## Step 2 — Push these starter files to the new repo

From the unzipped `csf-dashboard` folder on your machine:

```powershell
cd C:\path\to\csf-dashboard
git init
git add .
git commit -m "Initial dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/csf-dashboard.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

After this, your public repo has: `index.html`, `README.md`, `data/`
(with placeholder JSON files), and `SETUP.md` (this file).

## Step 3 — Enable GitHub Pages

1. Go to your public repo's **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: **main**, folder: **/ (root)**
4. Click Save
5. Wait 1–2 minutes, then refresh the page. You should see:
   *"Your site is live at https://YOUR_USERNAME.github.io/csf-dashboard/"*

That's your URL. Open it in a new tab — you'll see the dashboard with the
placeholder "0 signals" data. Working, just empty.

## Step 4 — Create a Personal Access Token (PAT)

The private repo needs permission to push to the public repo. GitHub's
built-in `GITHUB_TOKEN` can't write across repos, so we use a PAT.

1. Go to https://github.com/settings/tokens?type=beta
   (Fine-grained personal access tokens)
2. Click **Generate new token**
3. Token name: `csf-dashboard-push`
4. Expiration: 1 year (set a calendar reminder to renew)
5. Resource owner: your username
6. Repository access: **Only select repositories** → pick **csf-dashboard**
7. Permissions → Repository permissions → **Contents: Read and write**
8. Click **Generate token**
9. Copy the token. You only see it once — paste it somewhere temporary.

## Step 5 — Add secrets to the private repo

1. Go to your **private** repo (`claude-speculation-fund`)
2. **Settings → Secrets and variables → Actions → New repository secret**
3. Add two secrets:

   **Secret 1:**
   - Name: `DASHBOARD_PAT`
   - Value: paste the PAT from Step 4

   **Secret 2:**
   - Name: `DASHBOARD_REPO`
   - Value: `YOUR_USERNAME/csf-dashboard` (e.g. `richardsmith/csf-dashboard`)

## Step 6 — Add the dashboard builder to your private repo

Copy these two files from the `csf-dashboard` package into your
**private** `claude-speculation-fund` repo:

1. `build_dashboard_data.py` → into the root of the private repo
2. `PRIVATE_REPO_workflow_daily.yml` → into `.github/workflows/daily.yml`
   (replace the existing `daily.yml` with this one)

Commit and push:

```powershell
cd C:\Users\richa\Documents\Investments\claude-speculation-fund
git add build_dashboard_data.py .github/workflows/daily.yml
git commit -m "Add dashboard build + sync workflow"
git push
```

## Step 7 — Trigger the first sync manually

1. Go to your private repo on GitHub
2. **Actions** tab
3. Click **Daily run** in the left sidebar
4. Click **Run workflow** → **Run workflow** (green button)
5. Wait 5–10 minutes for it to complete
6. Check the public `csf-dashboard` repo — you should see a new commit
   "Update dashboard data <date>" with real JSON in `data/`
7. Open your dashboard URL. Real data should now appear.

If step 7 fails, check the Actions log. The most common issues:
- PAT expired or scoped wrong → regenerate, re-add secret
- Secret name typo → must match exactly: `DASHBOARD_PAT`, `DASHBOARD_REPO`
- The build_dashboard_data.py crashed → check its log step

## Step 8 — Share with family

Send them the URL. Done.

They don't need a GitHub account, don't need to install anything, and
will see updated data every weekday morning (UK time) without doing
anything.

## Optional — Custom domain

If you want a nicer URL like `csf.yourdomain.com`:
1. Add a `CNAME` file to the public repo root with one line: `csf.yourdomain.com`
2. Add a CNAME DNS record at your domain pointing to `YOUR_USERNAME.github.io`
3. Wait ~10 minutes for DNS to propagate

## Troubleshooting

**Dashboard shows "Failed to load data":**
The page can't find the JSON files. Check `data/summary.json` exists in
the public repo and is valid JSON.

**Dashboard shows old data:**
GitHub Pages caches aggressively. Hard-refresh (Ctrl+Shift+R) or click
the "refresh" link in the footer.

**The daily workflow runs but nothing changes in the public repo:**
Probably means `build_dashboard_data.py` produced identical output to
yesterday, so `git diff` was empty. Check the workflow log for the
"Sync sanitised data" step.

**I want to hide the URL more:**
GitHub Pages URLs aren't truly private but they're unlisted — only people
with the link can find it. Don't link to it from anywhere else and it
won't be indexed (the page has `noindex` set anyway).
