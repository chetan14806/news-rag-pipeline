# Delivery checkpoints and current status

**Continuation complete:** extractor 2.0.5 resolves the three recorded entity-error cases and corrects nine records. Both replays, all 76 tests, 25 query cases, record/source comparisons and refreshed sample checks pass. See CURRENT_STATUS.md and results/entity_refinement_verification.json. There is no unfinished pipeline stage; the remaining work is the narrated demo and remote delivery.

Last updated: 2026-10-18. Extractor 2.0.5 retains the query-planning, paragraph/table, time and verification-tool fixes and adds evidence-backed entity type corrections. All 81 records and eight sample answers match across environments; the answers remain unchanged from 2.0.4. Earlier 2.0.3/2.0.4 reports are historical evidence.

| Checkpoint | Status | Exit evidence |
| --- | --- | --- |
| 1. Reproducible setup | Complete within documented same-host scope | Separately installed isolated dependencies; current 76 tests; 81 identical rebuilt records; 484 chunks; eight identical reviewed answers; raw/index/CLI audits; nine-command README |
| 2. Submission package | Complete locally | Five current 2.0.5 pairs; import/overwrite-refusal checks; current archive reopened and every file hash checked (see submission_package_verification.json); credential-pattern scan clear; attribution retained |
| 3. Demo | User will narrate and record using DEMO_GUIDE.md; recording pending | Actual 3–5 minute recording still needs capture/review; user explicitly chose their own narration |
| 4. Repository delivery | Deferred until verification, packaging and demo; local main branch initialized | User chose chetan14806 and public visibility; proposed empty repository news-rag-pipeline; remote link and Git author identity still pending |

## What is already finished

- Source selection and production scraper: 81 original HTML articles, verified skips, redirect identity and durable cooldown fixes.
- Extraction: 81 validated records, audited facts/entities, explicit unknowns/limitations, five verified local pairs.
- Index: 484 real vectors/chunks across 81 articles, verified persistence, replacements and offline reruns.
- Query: eight actual sample answers, eight paraphrases, four negative checks and five additional wording probes; 76 tests pass. Source evidence and digest-bound review judgments are saved.

## Plan changes and reasons

- User corrected the delivery sequence: finish full verification and packaging, then the demo, then GitHub/submission. Do not ask the user to create the repository during the unfinished verification gate.

- Model choice evolved from a spaCy entity baseline to local GLiNER after measured entity errors. The initial failed-quality baseline remains in the log/results.
- Answers use deterministic calculations and source excerpts rather than an optional generative LLM. The brief permits this; it removes credential/provider dependencies but limits prose fluency and language coverage.
- Delivery verification uses a new isolated environment and copied code/input workspace. This is stronger than rerunning the development venv, but it is still the same Windows host—not a claim of independently tested Linux/macOS or a different computer.
- Existing verified local model assets may be copied for offline verification after installation. Model download commands were already exercised separately; the report must distinguish reused downloads from new installation/model inference.
- User selected GitHub account chetan14806 and public visibility. Recommended repository name: news-rag-pipeline, created empty without generated README, licence or ignore file. Local main branch is initialized; no remote publication has occurred. Third-party source samples retain attribution and ownership; their inclusion does not grant an open-source licence to publisher content.

## Update discipline

Current handoff: two delivery gates are complete (verification and local package); two remain (user-recorded demo, then GitHub/submission). Local archive: dist/news-rag-pipeline-submission.zip. The adjacent report results/submission_package_verification.json holds its current hash and file manifest. Regenerate the archive after any later source/document edit.

At every gate, update this table, PROJECT_PLAN.md and PROJECT_LOG.md with the action, reason, actual command/test outcome, failures/fixes, and next unfinished item. A prepared script/package is not a published repository or recorded demo. Count a checkpoint complete only after its exit evidence exists.
