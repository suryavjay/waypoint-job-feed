# Summer 2027 public internship feed

A jobs-only updater for Waypoint. No resume, candidate profile, notes, saved roles, or application history belongs in this repository.

GitHub Actions schedules `.github/workflows/refresh.yml` every 30 minutes, at minutes 7 and 37 UTC, independently of any personal computer. GitHub may delay or skip scheduled runs, so this is a requested cadence rather than a guaranteed freshness interval. The workflow can also be started from Actions → Refresh internship listings → Run workflow. See [GitHub's schedule limitations](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

Sources: four community GitHub feeds and up to 80 discovered/configured Greenhouse, Lever, and Ashby public boards. No LinkedIn, Indeed, or Handshake scraping. Failed or incomplete boards do not close listings. Deduplication uses canonical application URL, ATS identity, then company + role + location. Distinct official posting IDs remain distinct.

`feed/jobs.json` holds public listing evidence and timestamps only. All-source failure leaves the previous published file unchanged and fails the workflow. Partial failures appear in `sources`. A complete official board can establish closure; a missing community entry cannot.

The private dashboard checks this feed automatically when opened and every five minutes while visible. Application progress stays in its private database. Resume generation and fit assessment remain separate.

## Setup

1. Use an existing GitHub account and create a public repository for these files only. Standard hosted Actions runners are free for public repositories.
2. Push the `main` branch and enable Actions if prompted. The workflow's built-in `GITHUB_TOKEN` handles commits: no API key to paste.
3. Run the workflow once and confirm the green check and `feed/jobs.json`.
4. Set the private dashboard's `JOB_FEED_URL` to the raw URL of that file. No private credentials belong in this public repository.

GitHub can disable public scheduled workflows after 60 days without repository activity. Successful feed commits provide activity. Check Actions if the dashboard warns that its feed is stale.
