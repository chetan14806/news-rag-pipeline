# Current local delivery verification — 2026-10-18

The latest continuation advances extraction to **2.0.5** and passes **76 tests in both environments**, with all **81 records byte-identical**, **484 chunks**, ten retrieval probes and 25 actual query cases passing. Nine entity lists improve and all three recorded error cases are resolved; earlier paragraph/table corrections are retained. The eight required answers remain unchanged and source-reviewed. The actual CLI reproduces the 14-item city answer. Five current sample pairs import byte-for-byte and refuse overwrite. See [the current end-to-end review](FINAL_REVIEW.md), [aggregate verification](entity_refinement_verification.json), and [current status](../CURRENT_STATUS.md). General model/recall limits remain; these checks do not establish perfect entity accuracy.

The existing isolated environment, original HTML and local model downloads were reused; dependencies were not reinstalled in this review. The narrated recording and remote repository/submission remain outstanding. The local archive is regenerated and checked after these changes; submission_package_verification.json holds its current file list/hash.

## Historical 2.0.3 installation and replay

The remainder of this document records the earlier initial installation/checkpoint, rather than the current source snapshot.

The four-stage implementation and same-host isolated replay are verified. The actual narrated demo and remote repository/submission remain outstanding. The user chose to record the demo personally using DEMO_GUIDE.md.

## What was verified

- Installed the pinned requirements and spaCy model into a new Python 3.12.14 virtual environment with system site-packages disabled. Dependency consistency passed; resolved versions are in clean_environment_freeze.txt.
- Reused 81 original HTML files and checked local model assets. Did not copy development site-packages. The first replay began without extracted records, vectors or query outputs; the corrected version then invalidated/rebuilt all records and indexes.
- Both environments passed 63 tests, including a regression that checks entity ordering across six Python hash seeds.
- Extractor 2.0.3 processed/wrote/accepted all 81 articles with zero failures. All 81 final record files match byte-for-byte across environments. Original HTML integrity/structure and 1,431 extraction reference spans pass.
- Both indexes contain 81 articles / 484 chunks. All ten declared retrieval probes find the expected article in the first five distinct results. The unchanged rerun skips all 81 and embeds zero chunks; integrity/filter checks pass.
- Eight sample families, eight paraphrases and four negative/ambiguity probes pass. All eight answer payloads match across environments and retain the original source-review hashes. The direct query.py CLI reproduces the evaluator's 14 location items. Index and answer audits report zero network attempts.
- Five current original-HTML/JSON pairs are packaged. Import preserves their bytes and refuses to overwrite an existing destination. Git attributes preserve sample line endings.

## Defect found and fixed

The first strict comparison found 80/81 identical records. CEAT's two case variants, `RPG Group` and `RPG group`, had equal casefold sort keys, allowing randomized set order to change serialization. Entity and funding-company lists now use a secondary original-spelling sort key. Extractor version 2.0.3 forces cache invalidation. The initial failed comparison is preserved in clean_environment_initial_comparison.json; it was not replaced with a false pass.

## Evidence and limits

The historical 2.0.3 replay/check results are in clean_environment_verification.json and development_refresh_verification.json, with per-step text logs. Current evidence supersedes those source hashes and sample outputs; see final_review_verification.json and final_review_sample_import_verification.json. tools/package_submission.py creates a local source archive and a separate submission_package_verification.json containing every archived file hash.

This is the same Windows host with a fresh dependency environment, saved HTML and reused model downloads. It is not a newly scraped corpus, a new physical computer, or Linux/macOS validation. Earlier live-scraper evidence remains in scraper_verification.md. Entity omissions/errors, bounded query language, publication/event-date distinctions, incomplete investor recall and full-index validation cost remain documented limitations. No new broad accuracy or deployment-readiness claim is made.

The archive excludes the full corpus, model downloads, virtual environments, temporary workspaces, Git internals and assignment PDF. Publisher samples retain attribution and ownership notices. Archive preparation is local; no GitHub upload or submission has occurred.
