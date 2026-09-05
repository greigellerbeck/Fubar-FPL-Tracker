# FPL Mini-League Tracker (auto-updating, no install needed to view)

This turns your tracker into a live webpage that anyone can open on any
device, no app or install required. A robot (GitHub Actions) fetches the
FPL data on a schedule and republishes the page automatically.

## One-time setup (about 10-15 minutes, all in a browser)

1. **Create a GitHub account** (free): https://github.com/signup

2. **Create a new repository**
   - Click the "+" top-right -> "New repository"
   - Name it something like `fpl-tracker`
   - Set it to **Public** (required for free GitHub Pages)
   - Click "Create repository"

3. **Upload these files**, keeping their folders:
   - `generate_site.py` (repo root)
   - `.github/workflows/update-tracker.yml`
   - `docs/logo.jpg` (your league crest -- already sized and wired into the page header)
   - `README.md` (optional, just for your own reference)

   To replace the logo later, just upload a new image to `docs/logo.jpg`
   with the same filename (or change the filename in the `<img src=...>`
   line inside `generate_site.py` if you'd rather rename it).

   Easiest way: on the repo page, click "Add file" -> "Upload files", then
   drag in `generate_site.py`. For the workflow file, click "Add file" ->
   "Create new file", type the path
   `.github/workflows/update-tracker.yml` into the filename box (GitHub
   creates the folders automatically), and paste in the workflow file's
   contents.

4. **Turn on Actions permissions to let it commit the page back**
   - Repo -> Settings -> Actions -> General
   - Scroll to "Workflow permissions"
   - Select **"Read and write permissions"** -> Save

5. **Run it for the first time**
   - Go to the "Actions" tab -> "Update FPL Tracker" (left sidebar)
   - Click "Run workflow" -> "Run workflow" (green button)
   - Wait ~30-60 seconds, refresh -- you should see a green checkmark
   - This creates `docs/index.html` in your repo automatically

6. **Turn on GitHub Pages**
   - Repo -> Settings -> Pages
   - Under "Build and deployment" -> Source: "Deploy from a branch"
   - Branch: `main`, folder: `/docs` -> Save
   - GitHub shows you the live URL (looks like
     `https://<your-username>.github.io/fpl-tracker/`) -- give it a minute
     the first time

That URL is what you share with your friends. It updates itself every
Tuesday automatically (edit the `cron:` line in the workflow file to
change the schedule), and anyone with repo access can also trigger an
instant refresh from the Actions tab -> "Run workflow".

## Changing the league ID

Open `generate_site.py` and edit the `LEAGUE_ID = 970639` line near the
top, then commit the change.
