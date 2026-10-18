# Independent checkpoint review — 2026-10-17

**Historical scraper checkpoint.** This report predates the completed extraction, index and query stages. See [the latest end-to-end review](FINAL_REVIEW.md) for current findings and verification; counts and pending-stage statements below describe the original checkpoint.

**Follow-up status:** both findings below were fixed later on 2026-10-17. The original review is retained as history. Current suite: 24 passing tests; updated probes report one article for A-to-B plus B, and zero publisher requests on restart during cooldown. Evidence: `results/scraper_hardening_verification.json`. The actual 81-page corpus re-audit passes with no duplicate destinations or orphan files. Full extraction/index/query stages remain pending.

## Verdict

The single-source scraper is implemented, has collected a usable raw corpus, and passes the current checks. It is not a completed assignment or a fully hardened production system. Two reproducible robustness gaps remain open. Earlier references to the scrape stage being complete describe the original checklist, not proof that all edge cases are correct.

## Evidence checked again

- All 19 existing behavioral tests pass.
- A new offline audit verifies 81 original HTML artifacts, totaling 25,493,154 bytes: no invalid hashes/sizes, duplicate final URLs, or orphan HTML files.
- All 81 pass the existing title/body/byline/canonical/publication-marker structure checks; no flags.
- Environment dependency check reports no broken requirements.
- Prior recorded live rerun: zero article downloads and 81 verified skips. This review rechecked saved artifacts offline; it did not repeat live collection.
- The current folder has no Git repository yet. Repository setup and delivery packaging remain pending.

These checks prove specific transport, storage and structural properties. They do not prove complete article text, correct entities, funding amounts, summaries, or truthful publisher claims.

## Open findings

### 1. Redirect aliases can inflate the article count

`newsrag/storage.py` keys records by the requested URL. If discovered URL A redirects to discovered URL B, both can be stored and counted independently. The synthetic probe reports two ready records with only one unique final URL. This can make a requested article target misleading and duplicate downstream input.

The actual 81-page corpus has zero repeated final URLs, so this reproduction does not invalidate its current unique-final-URL count. Fix by explicitly tracking final-destination aliases and counting unique article identities; preserve original request provenance. Add a regression test covering A-to-B plus direct B discovery and rerun behavior. This is distinct from two different articles reporting the same funding round, which needs downstream semantic handling.

### 2. Server cooldown is lost when the process restarts

`newsrag/fetching.py` correctly stops the current batch for a long Retry-After, but its cooldown is only held in memory. With a simulated 600-second Retry-After, an immediate second run attempts the article after 12 seconds of simulated elapsed time (robots/feed pacing). The README currently depends on the operator waiting before a retry.

No 429/503 occurred during the recorded live collection, so no violation was observed there. Fix by persisting a source-scoped UTC resume-after timestamp and checking it before network requests in a new run. Test immediate restart, expiry, and both forms of Retry-After. Until fixed, automated restarts must not assume the scraper itself retains a publisher cooldown.

Original evidence: `results/review_probe_results.json`. The updated `.venv\Scripts\python.exe tools\review_scraper_probes.py` now writes post-fix evidence to `results/scraper_hardening_verification.json`, preserving the original reproduction. These use fake network/time and workspace-local temporary files; they do not contact the publisher or change the real corpus. Dedicated regression tests are now included in the automated suite.

## What remains for the assignment

1. Close these two scraper findings with regression tests.
2. Implement the complete extraction schema and validate at least 50 accepted articles; audit text completeness and factual fields against originals.
3. Implement persistent embeddings/indexing, filtering and replacement of old chunks.
4. Implement grounded answers plus structured date/location/funding/investor operations and refusal when evidence is absent.
5. Run all eight real sample questions, check their answers and citations, and record limitations.
6. Package five final HTML/JSON pairs with an appropriate sharing basis, a reproducible README/configuration, repository and 3–5 minute demo. Test setup from a clean environment.

No production source code was modified by this review. Findings remain open; the corpus remains available for extraction development. Do not describe schema accuracy or query behavior as verified before those stages exist.
