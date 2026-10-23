# FAA NAS Status Monitor — GitHub Actions + iPhone push

Checks the [FAA NAS Status XML feed](https://nasstatus.faa.gov/api/airport-status-information) for nationwide ground stops, ground delay programs, airport closures, and airport delays. Pushes new/updated/ended event alerts to iPhone via ntfy. Uses GitHub Actions every ~5 minutes (GitHub may delay or skip scheduled runs). The first run establishes a baseline, so it sends no alerts for existing events.

## 1. Set up iPhone notifications

1. Install **ntfy** on your iPhone: https://apps.apple.com/us/app/ntfy/id1625396347
2. Allow notifications and tap **+** to subscribe to a topic on `ntfy.sh`.
3. Use a **long random private topic**, e.g. `faa-8b3f4c...` (make your own, don't use the example). Anyone knowing the topic can publish to it; it is not a password-protected channel.
4. For reliable iOS push, use the ntfy app and the default ntfy.sh server.

## 2. Create a GitHub repository

1. Sign in at https://github.com and choose **New repository**.
2. Name it `faa-nas-monitor`, choose **Public** (GitHub-hosted Actions usage is free for standard public repositories), and create it. **Don't put the ntfy topic in any file.**
3. Upload `monitor.py`, `.gitignore`, and the `.github/workflows/monitor.yml` file, **preserving the exact `.github/workflows/` folder structure**. The GitHub web upload interface can upload a folder if your browser supports it; otherwise use GitHub Desktop or `git` (instructions below).
4. Under **Settings → Secrets and variables → Actions → New repository secret**, create `NTFY_TOPIC` with the exact topic subscribed to in the iPhone app.
5. Under **Settings → Actions → General → Workflow permissions**, choose **Read and write permissions** (so the workflow can commit `faa_state.json`). Save.
6. Go to **Actions → FAA NAS Status Monitor → Run workflow** to test. Open the run's logs. The first run saves `faa_state.json` as a baseline.
7. Subsequent scheduled runs compare against that state and send notifications when events change.

**Important:** Workflow schedules run on the default branch only. GitHub scheduled runs are *best effort*, not guaranteed to execute at exact five-minute intervals, and can be disabled after extended inactivity in public repositories. Check Actions occasionally.

## Optional: upload using git (more reliable for hidden `.github` folder)

From inside this project directory:

```bash
git init
git branch -M main
git add monitor.py .gitignore .github/workflows/monitor.yml README.md
git commit -m "Initial FAA NAS monitor"
git remote add origin https://github.com/YOUR_USERNAME/faa-nas-monitor.git
git push -u origin main
```

If GitHub created a README during repository creation, clone the repository instead of `git init`, then copy the files in and commit/push.

## Test push from a computer

```bash
export NTFY_TOPIC='YOUR_RANDOM_TOPIC'
python3 monitor.py --test-push
```

## Notes and limitations

- Source: FAA airport-status-information XML. This is **not** every FAA advisory, NOTAM, reroute, or forecast item.
- Event updates are based on changes in XML fields; some FAA feed timestamp or schema changes could cause noisy updates.
- ntfy.sh topics are unprotected by default. Use an unguessable topic and don't share it. Don't put it in repository files.
- A failed feed fetch or failed push causes the job to fail without committing new state, so it retries next run. Partial push success followed by failure can result in duplicate notifications.
- If you delete `faa_state.json`, the next run resets the baseline.
- A public repository exposes `faa_state.json` (public FAA data), not the ntfy topic secret.
- GitHub Actions schedule may not be reliable enough for time-critical operational decisions. Always verify with official FAA/ATC sources.
