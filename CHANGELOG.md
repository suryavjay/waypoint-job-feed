# Changelog

## 2026-09-18 — Retain employer evidence after closure

- Closed internships keep their checked employer description, dates and requirements when community copies refresh. Missing source provenance no longer counts as employer verification.
- An empty employer description cannot stamp an older community summary as verified. Previously checked employer wording retains its original check date; a new complete employer description can still update or reopen the listing.
- Verification: regression cases reproduced the previous failures before the fix; fixtures cover closure, missing provenance, empty descriptions, official updates and saved application history. No schema change or source removal.

## 2026-09-17 — Recover intermittent source failures

- Retry a read once, after one second, for network timeouts/resets and HTTP 502/503/504. Other errors, including 404 and rate limits, keep their existing failure behavior.
- Public-address validation, redirect checks and bounded downloads remain in place. Exhausted retries still leave the source incomplete so it cannot close saved jobs.
- Verification: simulated timeout recovery, bounded repeated failures, non-retried 4xx/rate-limit responses, download limits and private-address rejection.

## 2026-09-17 — Google link variants

- Treat Google career links with and without `www` as the same application URL. Verified with a regression fixture; distinct requisition paths remain separate.

## 2026-09-17 — Conservative cross-board duplicate matching

- Fixed San Francisco normalization; normalize location order, NYC/SF aliases and common US state spellings without collapsing different countries.
- Match equivalent internship title wording and known company-name variants across boards.
- Protect distinct same-site requisition URLs, distinct ATS IDs and PhD-specific titles from weak title/location matching.
- Verification: fixtures cover successful merges, preserved private progress, and jobs that must remain distinct. Existing stored fields are reused; no schema change.

## 2026-09-17 — Direct HRT internship coverage

- Added HRT’s verified public Greenhouse board (`wehrtyou`) to priority company coverage. The company and existing requisition IDs matched the current employer API.
- Live adapter verification returned three relevant Summer 2027 internships (software engineering, quant research/trading, and PhD quant research/trading) with full descriptions. Other seasons and permanent jobs were excluded.
- Existing community leads remain; no scraper removed or schema changed.

## 2026-09-17 — Domain-style Ashby boards

- Accept valid dotted Ashby board names, restoring checks for `persona.ai` and `rivianvw.tech`.
- Keep invalid paths, query strings, fragments and unbounded identifiers out of requests.
- Verification: adapter tests for valid/invalid names; live public API checks returned 28 and 137 total jobs respectively before filtering to relevant Summer 2027 internships.
- No schema change, scraper removal, or dependency change.

## 2026-09-17 — Internship scope and role classification

- Exclude explicit new-grad, permanent, and mixed internship/full-time titles from discovery and the published public feed.
- Preserve graduate-student internships, internships with full-time hours, and 2028 graduation windows.
- Classify the role title before broad source headings, so a Data Science role under a combined AI/ML heading stays Data.
- Include explicit trading/trader internships in Quant matching.
- Verification: `python3 -m unittest discover -s tests`; fixture coverage includes mixed listings, return-offer language, student internships, and source-heading ambiguity.
- No schema change, scraper removal, or dependency change.
