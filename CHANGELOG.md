# Changelog

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
