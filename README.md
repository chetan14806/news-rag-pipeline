# News RAG Pipeline

Repository: [chetan14806/news-rag-pipeline](https://github.com/chetan14806/news-rag-pipeline).

Zylabs coding assignment: build independently runnable scrape, extract, index and query stages over real news articles.

**Current implementation:** all four CLI stages are implemented. Extractor **2.0.5** passes **76 tests in both environments**, verifies **81 byte-identical records and 484 chunks**, and matches all eight sample answers across environments. Entity type corrections improve nine records and resolve the three recorded institution/platform/generic-name error cases, with no unexpected entity-list changes in the other 72. The earlier paragraph/table fixes are retained. The query evaluation covers eight required questions, eight paraphrases, four negative/ambiguity probes and five additional wording probes. The existing isolated environment, saved HTML and local model downloads were reused on this same Windows host; this is not a new live scrape or cross-platform test. Five sample pairs are packaged; the repository is published; the narrated demo and final assignment submission remain pending. Start with [current status and where to resume](CURRENT_STATUS.md), [current verification](results/entity_refinement_verification.json), [the end-to-end review](results/FINAL_REVIEW.md), or [actual sample answers](results/sample_queries.md).

Verified local result: **81 raw articles**, all 81 passing integrity/structure checks, and a recorded live rerun with zero article downloads and 81 verified skips. See [measured collection verification](results/scraper_verification.md) and [subsequent hardening evidence](results/scraper_hardening_verification.json).

Source: [IndianWeb2](https://www.indianweb2.com/), using its public technology/business/startup RSS metadata. See [source selection](SOURCE_SELECTION.md), [end-to-end plan](PROJECT_PLAN.md), [scraper checklist](SCRAPER_CHECKLIST.md) and [project log](PROJECT_LOG.md).

## Setup and run (Windows)

Prerequisite: an installed **Python 3.12** with pip/venv support (`py -3.12 --version` must succeed). Run from the downloaded/cloned repository root. A Python launcher alone is not an installed interpreter. No API keys or GPU are required. Dependency/model setup requires internet access and several gigabytes of free disk space.

The complete primary path is **nine commands**:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_md-3.8.0/en_core_web_md-3.8.0-py3-none-any.whl
.venv\Scripts\python.exe tools\setup_entity_model.py
.venv\Scripts\python.exe tools\setup_embedding_model.py
.venv\Scripts\python.exe scrape.py --limit 80
.venv\Scripts\python.exe extract.py
.venv\Scripts\python.exe index.py
.venv\Scripts\python.exe query.py "What are the main stories about AI in this collection?"
```

On macOS/Linux use `python3.12 -m venv .venv` and `.venv/bin/python` in place of Windows paths; those operating systems have not been executed in this project. This machine uses a bundled Python 3.12.14 runtime, because its launcher has no registered Python installation. An isolated second-environment replay on this Windows host passed; it reused saved raw HTML and checked model downloads, then recomputed extraction and embeddings. This is not a different-computer or cross-platform test. Installed dependency versions are recorded in results/clean_environment_freeze.txt. Scraping itself downloads no model and requires no key.

Optional verification after setup: `.venv\Scripts\python.exe -m unittest discover -s tests -v`. Stage-specific commands below are reference options, not additional mandatory setup commands.

Run the same scrape command again to verify/skip already stored pages. `--limit` counts ready pages among current eligible feed candidates, including verified earlier saves. It does not mean "download 80 more". A normal 80-page first run takes roughly eight or more minutes due to intentional delays and network time.

Other commands:

```powershell
.venv\Scripts\python.exe scrape.py --discover-only
.venv\Scripts\python.exe scrape.py --limit 5
.venv\Scripts\python.exe scrape.py --help
.venv\Scripts\python.exe tools\audit_scrape.py
.venv\Scripts\python.exe tools\check_raw_inputs.py
```

Optional flags: `--data-dir` (default `data`), `--delay` (six-second minimum always enforced), `--timeout` (socket timeout, default 25 seconds), `--attempts` (1–5, default 3). `--refresh` explicitly re-fetches verified pages; omit it for ordinary resumable runs. It replaces the current raw version, so use deliberately. The program does not load `.env` files; `.env.example` explains that no scraper secrets are needed.

Exit codes: 0 for a completed target/discovery-only run; 1 for a shortfall, failed startup, unavailable policy, fatal error or server pause; 130 for user interruption. Partial successes remain available. Inspect `data/runs/latest.json` and failures before retrying. Do not repeatedly retry a server pause or access denial.

## Scrape-stage behavior

1. Acquire an exclusive writer lock; load the existing manifest without silently resetting corrupt state.
2. Fetch and save fresh robots rules. Use a descriptive `ZylabsNewsRAG/0.1` identity. An unavailable/unrecognized policy stops the run. Protego handles wildcard rules and longest-match precedence.
3. Fetch [the public RSS endpoint](https://www.indianweb2.com/feeds/posts/default?alt=rss&max-results=100), save its original bytes, and discover article URLs and source metadata.
4. Keep dated HTML articles on the exact HTTPS host. Include source labels Business, Technology, Startups or Startup Funding; exclude Business Tips and Book/Books. Save every exclusion with its reason. Source labels are discovery hints, not our final extracted categories.
5. Deduplicate normalized URLs and saved final redirect destinations. Retain the first saved article ID and alias provenance; count each final destination once toward the target. Strip known tracking parameters and Blogger's `m=1` mobile alias; reject unfamiliar article parameters rather than guessing. Discovery is in feed order, not ranked to match the eight assignment questions.
6. For an existing successful page, read and verify its size and SHA-256 before skipping it. Re-fetch missing/damaged originals. For new pages, save unchanged HTTP response-body bytes and complete fetch provenance.
7. Persist manifest updates atomically after each successful article; retain per-request audit, failed URLs and run summaries.

Only one HTTP request is in flight. Requests, retries and redirects all pass through the same limiter: at least six seconds between starts, with longer robots delays/request rates and server Retry-After honored. Retries are bounded for network errors and transient HTTP statuses, with exponential backoff. Ordinary 401/403/404 are not retried. A server cooldown longer than 60 seconds, or persistent 429/503, stops the batch for a later retry rather than shortening the requested pause.

Redirects must stay on the selected source and remain a permitted endpoint type. Every article/feed redirect target is checked against robots before being requested. Limits also cover response size (8 MiB), redirects and socket timeout. Byte-count mismatches for declared Content-Length are retryable incomplete responses. Unexpected compression is rejected rather than stored under a misleading `.html` filename.

## Persisted output and extraction handoff

```text
data/
  manifest.json                       successful raw-page records (schema v1)
  raw/<sha256-of-normalized-url>.html  untouched response body
  policies/robots-<run>.txt/.json      policy snapshot and effective delay
  policies/cooldown.json              source resume-after, when a server cooldown occurs
  discovery/feed-<run>.xml            untouched RSS response
  discovery/candidates-<run>.json     candidates, exclusions and provenance
  discovery/latest.json
  logs/requests.jsonl                 attempts, status/errors and response bytes
  logs/articles.jsonl                 successful saves and repairs
  logs/failures.jsonl                 terminal article failures
  runs/<run>.json                     immutable completed run summaries
  runs/latest.json
```

Each manifest article has: stable ID, normalized original URL, final fetched URL, UTC fetch timestamp, HTTP status, content type/encoding, response size/SHA-256, relative raw path, available ETag/Last-Modified, redirect chain, run ID and feed provenance (title, labels, feed publication string, snapshot and fetch time).

The extraction stage should enumerate **manifest records**, verify their bytes, and read those raw paths. It must not blindly glob unreferenced/orphan HTML after an interrupted write. The raw stage does not infer article publication time, author, company, funding, category, summary or body text. Feed publication strings and fetch/server Last-Modified timestamps must not be confused with an article's actual publication date.

The separate offline `check_raw_inputs.py` verifies that saved pages contain the expected article container, non-trivial body text, title, byline, canonical URL and timezone-aware publication marker. It saves `data/input-readiness.json` without modifying originals or creating final extraction records. Passing this structural check does not establish entity/funding correctness or complete body extraction. Both audit tools acquire the writer lock and should run after collection finishes.

Atomic raw and manifest writes are separate operations, not one database transaction. An abrupt failure between them can leave an orphan raw file or a hash mismatch; rerunning repairs/refetches instead of trusting it. Normal Ctrl+C releases the lock. A hard crash may leave `data/.scrape.lock`; inspect its PID and remove that one lock only after confirming the old process is no longer running. Concurrent writer processes must not share one data directory.

## Checks and known limits

The automated suite uses fake network/time with real temporary file operations. It checks access restrictions and safe redirects, delay/backoff/cooldown behavior, failure isolation, malformed feeds, URL scope/deduplication, raw preservation, hash repair, no-download reruns, writer locking and interruption recovery. Live publisher requests separately verify the real transport. Measured collection/rerun results are in `results/scraper_verification.md`.

- RSS discovery currently reads the latest 100 entries. It reports a shortfall rather than silently enlarging the crawl into arbitrary archives if not enough eligible pages exist.
- A successful raw fetch is not proof of correct extraction or of publisher factual accuracy. A 200-status soft-error/access page may still need quarantine in extraction. The current scrape stage only checks transport, content type, non-empty body and byte integrity.
- Deduplication covers normalized URLs and known final redirect destinations. Distinct destination URLs describing the same story/funding round still need downstream semantic handling. Existing manifests with duplicate destinations are not automatically migrated; the current 81-page corpus has none.
- Valid positive Retry-After values are persisted as a source-scoped resume-after timestamp. A new run during that interval pauses before any robots/feed/article requests. Invalid saved cooldown state fails closed; expired state permits requests. Without a publisher Retry-After, exhausted 429/503 persists the computed backoff. Durable cooldowns use UTC wall time, so an accurate system clock is required.
- Socket timeouts limit blocking network operations, not the total runtime of a slowly streaming response.
- Partial/failed refreshes leave the previous successful record intact; its fetch timestamp remains the time of that older successful version.
- Source HTML/labels/access policies may change. The five-page extraction pilot established the need for an article-container fallback; future extraction must retain that completeness check.
- Full raw pages/feed snapshots and logs remain local and ignored. The five required submission HTML/JSON sample pairs retain source attribution and ownership notices; see THIRD_PARTY_NOTICES.md for the recorded reuse limitation. No sample licence is assumed here.
- Extraction yields 81 validated structured records with documented development checks and known entity omissions/errors. All eight query families have saved actual outputs and stated evaluation limits. Local packaging is verified; the recording and remote delivery remain outstanding.

With another week: add tested archive pagination, conditional refresh via ETag/Last-Modified, stronger extraction audits and query evaluation, then consider incremental scheduling or a small UI. These do not replace the required core pipeline.

## Offline extraction

After installing requirements, install the tested spaCy English model, then run extraction:

```powershell
.venv\Scripts\python.exe -m pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_md-3.8.0/en_core_web_md-3.8.0-py3-none-any.whl
.venv\Scripts\python.exe tools\setup_entity_model.py
.venv\Scripts\python.exe extract.py
.venv\Scripts\python.exe tools\audit_extraction.py
```

Tested models: en_core_web_md 3.8.0 for sentence/linguistic analysis, and `urchade/gliner_small-v2.1` at revision `4e091416cf7c3481db542c2a3d26156916f3a47f` for company/organization/person/location recognition with a competing product label. Setup downloads public weights once and saves checksummed local assets under data/models; no paid key or GPU is required. Initial dependency/model setup can take several minutes. For another data directory, pass the matching `--data-dir` to model setup and extraction.

Once models are installed, extraction loads local assets only. It uses Trafilatura with a checked article-container fallback, source metadata for dates/bylines, local NLP and explicit financial rules, and 2–3 extractive source sentences for summaries. Summary selection is a lead-sentence baseline, not abstractive synthesis. Entity input is split into overlapping windows bounded by both subtoken and word counts, with original character offsets retained. Model identity, settings and asset hashes are included in extraction fingerprints. The transparent entity vocabulary contains type disambiguations learned during development review, not prewritten article answers; development-sample scores must not be treated as held-out accuracy.

Optional `--limit N`, repeatable `--id FULL_ID`, `--force` and `--data-dir PATH` support representative checks and deliberate reprocessing. Stable raw/extractor/model fingerprints and JSON checksums allow valid unchanged records to be skipped. A changed or invalid input is excluded from current acceptance even when an older JSON file remains on disk. Unknown IDs fail visibly. Use the same data-directory writer lock as scraping.

Required fields are `id`, `url`, `title`, `author` (byline list), `published_at` (UTC), `body`, `summary`, `companies`, `people`, `locations`, `category`, `funding`. Additional provenance records original publication time, raw hash/path, extractor/model versions, source-span coverage, sentence evidence and entity spans. Organization output includes institutions/funds, not just commercial companies. Source-backed institution names are treated as organizations, explicit platform descriptions suppress spurious location predictions, and operations-role fragments are filtered. These corrections do not infer a city from an institution's name or headquarters. Amounts are exact decimal strings in currency base units; currency conversions are not inferred. Unknown amounts/rounds stay null. Funding preserves evidence, a kind (`venture`, `strategic_investment`, `debt`, `financial_support`) and a `reported`/`closing`/`committed` status. Do not count a closing or committed facility as disbursed/closed. Financial support must not inherit a previous equity round's stage or investors.

Current artifacts:

```text
data/records/<id>.json                 schema-validated article records
data/extraction/manifest.json          current accepted IDs, paths, fingerprints and checksums
data/extraction/errors.jsonl           append-only quarantine/error history
data/extraction/latest.json            most recent run summary
data/extraction/runs/<run>.json        per-run evidence
data/extraction/audit.json             schema/raw/metadata/long-span checks
```

Downstream indexing must require `complete_scan: true`, read only accepted manifest entries, and verify checksums/fingerprints against current raw inputs; it must never glob historical JSON files. A partial/limited run scans eligibility across the raw manifest but only extracts selected inputs. Missing mandatory publication metadata or raw-integrity failure quarantines that record. Accepted status means pipeline validation, not manually verified semantic accuracy.

Known extraction limits: NER can still confuse facilities/products with organizations and omit names; conservative financial rules can miss less explicit announcements and do not cover every financing structure. Named investor lists are not guaranteed complete, especially long shareholder profiles. Source labels/headline rules provide coarse categories, not a temporal event classifier. Exact location/layoff/funding queries must check underlying body evidence and event dates rather than trusting these labels alone. Publisher claims are not independently fact-checked by this pipeline.

Initial extraction checkpoint (historical): **81 accepted records**, 39 passing tests and 91/91 declared financial checks across 18 development articles. The initial ten-article entity review found two incorrect fragments among 147 display strings. Current 2.0.5 retains 91/91 financial checks and removes the previously identified fragments and the three recorded later type-error cases. This is development regression evidence, not a claim of perfect entity accuracy; recall is not exhaustively measured. The latest offline rerun skips 81 with zero writes and unchanged record bytes/mtimes. See the [latest review](results/FINAL_REVIEW.md), [rerun evidence](results/extraction_rerun_verification.json) and [current sample verification](results/submission_sample_verification.json).

## Persistent semantic index

After extraction and dependency installation:

```powershell
.venv\Scripts\python.exe tools\setup_embedding_model.py
.venv\Scripts\python.exe index.py
.venv\Scripts\python.exe tools\search_index.py "Investment in precision metal manufacturing"
```

Setup downloads the fixed revision of `sentence-transformers/all-MiniLM-L6-v2` once. Subsequent indexing/search load checked local assets with no API key. This is a separate model from extraction's GLiNER. Document and question embeddings use attention-masked mean pooling and L2 normalization, with 384 dimensions. Chroma 1.5.9 persists a cosine collection under `data/index/chroma`; telemetry is disabled and no default embedding function is used.

Body chunks preserve exact source character offsets, prefer sentence/paragraph boundaries, use at most 200 wordpieces and about 30 wordpieces overlap. Titles remain metadata; they are not appended to encoder input. Full documents are tokenized only to find offsets. Actual encoder inputs are checked against a 256-token total limit, including special tokens; oversized questions fail explicitly rather than truncating. Metadata includes article ID, order, offsets, title, URL, UTC publication time/epoch, category and record hash. Nested entities/funding remain in source JSON.

`index.py --data-dir PATH --index-dir PATH` supports separate inputs/storage. Repeatable `--id FULL_ID` explicitly creates a selected subset; use a separate index directory for pilots. The selection is part of the configuration and cannot silently change. Model revision/assets, library versions or chunking changes require a fresh `--index-dir`. Existing derived data is retained for review; the tool does not automatically delete an old database.

Indexing verifies current accepted records and original hashes, computes replacements before writing, removes obsolete chunks and quarantined/unaccepted article entries, and publishes a complete index manifest after verification. The shared project lock prevents overlapping tool operations. An interrupted update leaves the index marked incomplete; rerunning repairs it. Search refuses incomplete/stale/corrupt state. This is recoverable multi-step synchronization, not a database-wide transaction. Unchanged records skip embedding/vector writes; run reports still update.

The diagnostic search command returns evidence chunks, not final answers. Options include `--top-k`, `--category`, repeatable `--article-id`, `--data-dir` and `--index-dir`. The Python search function additionally accepts inclusive `published_from` and exclusive `published_before` UTC epoch bounds. An explicitly empty article-ID list returns no results. Later exact company/location/funding queries must determine eligible IDs from verified structured/body evidence; semantic top-k does not produce guaranteed complete lists. Multiple chunks from one article may appear, and distances are not confidence probabilities or an answerability threshold.

Operational evidence lives in `data/index/manifest.json`, `data/index/latest.json`, `data/index/runs/` and append-only `data/index/errors.jsonl`. Diagnostic audit: `python tools/audit_index.py --rerun`. It blocks socket connections, checks persisted vectors/chunk coverage and runs predeclared retrieval probes from `results/index_retrieval_cases.json`. These probes are development examples, not the final eight assignment queries.

At this corpus size, search deliberately rechecks every record/raw hash and chunk/vector digest before querying. This adds latency and does not scale to a large concurrent service. A production service would need a validated snapshot/read-generation design and explicit operational monitoring. Same-host isolated setup verification is complete; other machines and operating systems have not been tested.

Initial indexing checkpoint (historical): **81 articles, 484 chunks, 384 dimensions; 48 automated tests passed**. The current review retains those corpus dimensions and passes all ten development retrieval probes within the first five distinct articles (nine at rank one, one at rank two). The unchanged rerun skips all 81 without embedding/vector changes. Earlier separate-process retrieval and shortened-replacement checks remain in [the indexing milestone evidence](results/indexing_verification.md); current integrity/filter/retrieval results are in [the latest index audit](results/final_review_index_audit.json). These are retrieval/lifecycle checks, not broad answer-accuracy estimates.

## Grounded query interface

```powershell
.venv\Scripts\python.exe query.py "What are the main stories about AI in this collection?"
.venv\Scripts\python.exe query.py "Which startups raised funding in the last 7 days, and how much?" --as-of 2026-10-17T12:00:00Z
.venv\Scripts\python.exe query.py "Recent announcements" --intent company --company ServiceNow
```

The ordinary default is the current UTC instant. The second example deliberately freezes time to reproduce the collected snapshot; with a later live clock, recent-window results may legitimately be empty. `--as-of`, `--since` and exclusive `--before` accept timezone-bearing ISO timestamps. Last seven days is rolling; recent means 30 days; this month and previous month are UTC calendar windows. These filter **publication**, not transaction/event dates. Future publications are excluded.

Natural-language patterns cover the eight required query families and common paraphrases. Explicit `--intent`, `--company`, `--location` and `--title` flags resolve unsupported phrasing/ambiguity. `--json` returns the structured plan, answer, exact evidence spans, source URLs, retrieval traces and limitations. `--data-dir` and `--index-dir` select storage. Answers require the complete current index; a pilot subset is rejected. Queries persist in `data/queries/runs/<timestamp>.json` and `data/queries/latest.json` without rerunning prior stages.

Supplying either `--since` or `--before` overrides natural-language date defaults as a pair: only the explicit bounds apply, along with the reference-time cap. `--before` stays exclusive. For example, a question saying "last month" with only `--before 2026-09-15T00:00:00Z` searches all earlier stored publications; add `--since` to bound the start explicitly.

Answers use deterministic structured operations and **extractive source passages**, not a generative LLM. This choice runs without credentials and avoids invented prose/numbers; the trade-off is less fluent synthesis and a bounded language parser. There is no configured LLM provider/fallback pretending to generate answers. Unknown question families and live weather requests are refused, while missing/ambiguous company/title arguments ask for clarification.

- AI/company overviews rank eligible articles with real vectors and show up to five source summaries. These are selected stories, not exhaustive lists. Explicit company body mentions are checked with word boundaries and a small alias map; third-party announcements about a company may be included.
- Bengaluru/Bangalore queries check every accepted body, including NER omissions, and return all explicit mentions within the window. No city is inferred from an organization's headquarters.
- Startup funding scans complete records for reported venture announcements. It lists exact stored amounts/unknowns and flags closing rounds separately. Debt, bonds, support and strategic investments are outside this startup venture list. Publication within a week is not evidence of a transaction during that week.
- Layoff queries show all matching publication-window passages, separating historical, negated/conditional/speculative and unresolved timing. Conservative relative-time event rules do not prove exhaustive real-world event coverage.
- Repeated-investor aggregation works over named participants in reported venture rounds. Legal suffix/stage aliases normalize conservatively; distinct funds under one parent remain separate. Same-company reports with unknown identity collapse to avoid duplicate counts, potentially undercounting; ambiguous groups and incomplete extraction are exposed.
- Revenue queries resolve a unique title, retrieve within that article, then inspect full body revenue/turnover passages so a relevant metric is not lost to top-k. Source context, period, forecasts and table headers are preserved. Profit/valuation/funding do not substitute for revenue. No numerical company revenue is inferred from a bare mention or an industry total.

Reproduce the sample evaluation with `python tools/evaluate_queries.py`. It runs the eight required families, eight paraphrases and four negative/ambiguity probes, blocks network connections, checks source-span/URL integrity and independently checks exhaustive city mentions. Outputs: [actual sample answers](results/sample_queries.md) and [machine-readable evaluation](results/query_evaluation.json). These are development checks, not an independently annotated broad benchmark. Publisher claims themselves are not fact-checked. Source excerpts can preserve publisher/extraction formatting quirks.

Final query checks pass with zero network attempts: 14 explicit Bengaluru/Bangalore articles, three reported venture announcements in the frozen seven-day publication window plus one closing round, cautious layoff-context results, no repeated investor established in the extracted eligible roster, supported article revenue and weather refusal. The sample report includes per-answer source-review judgments bound to output hashes; changed outputs revert to pending review. See [query evidence and limitations](results/query_verification.md).
