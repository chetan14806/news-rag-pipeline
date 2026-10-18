# Zylabs assignment — project log

## Working agreement

- Keep this file as the continuing project record: requirements, reasoning, decisions, changes, commands/results at a useful level, failures, limitations, questions, and next steps.
- Distinguish assignment requirements from proposed choices and verified implementation.
- Record meaningful work as it happens; never claim an unrun test passed or fabricated output came from the pipeline.
- Do not store API keys, tokens, passwords, or other secrets here or in the repository. Document variable names only.
- User requested understanding and assessment first. Implementation has not started.

## 2026-10-17 (Asia/Kolkata) — Initial assignment assessment

### Request and evidence reviewed

The user asked to understand the new assignment thoroughly, assess its difficulty against the recently completed LearnTrace project, and maintain a comprehensive project log.

Read all five pages of `Zylabs_Intern_Coding_Assignment.pdf`, extracted its text, rendered all pages, and visually inspected them. Workspace initially contained only this PDF; no application code or local AGENTS.md was found. Read the previous LearnTrace project's README, PROJECT_BRIEF, and the final 150 lines of PROJECT_LOG at `D:/projects/Multimodal AI hackathon`; inspected recent context from the chat titled `Review hackathon introduction (2)`. These documents describe implementation status; the old application was not rerun or audited in this session. Where the older log describes ambitions that conflict with the implementation README, use the README's explicit limitations for the comparison.

PDF tooling: the bundled interpreter lacked PyMuPDF, so the first extraction attempt failed without modifying the PDF. Used available pypdf for text and Poppler for rendering successfully. Page previews are under `tmp/pdfs/` and are review intermediates.

### Assignment in plain language

Build a News RAG Pipeline: collect real news articles from one technology/business news site, preserve their original HTML, produce validated structured records, build a persistent semantic index, and answer questions using article evidence and source URLs.

The brief allows 5 days and estimates 12–16 hours. Python is preferred. These are the brief's figures, not a verified personal deadline or a guaranteed implementation estimate. The actual submission due date and when the five-day clock starts are not supplied here.

### Mandatory requirements — stage 1: scrape

- At least 50 articles from one selected news site/technology or business section.
- Discover URLs from listing pages; a paginated listing or RSS feed is preferred. Deduplicate URLs.
- Respect robots.txt and rate limits; delay between requests.
- Store untouched article HTML plus URL, fetch timestamp, and HTTP status in raw files plus a manifest or a database table.
- Do not clean article HTML in this stage; parsing listing pages to discover links is still necessary.
- Timeouts, retries with backoff, and failed-URL logs.
- Re-running skips already stored articles. A failed fetch must not be treated as a successfully stored article.
- Name the chosen source in the README. The brief offers Inc42, YourStory, TechCrunch, and Economic Times Tech as examples, not mandatory choices.

### Mandatory requirements — stage 2: extract

One schema-validated record per raw page, with:

| Field | Requirement |
| --- | --- |
| id | Stable string, e.g. URL hash |
| url | Canonical URL |
| title | String |
| author | String or list; empty when unavailable |
| published_at | ISO 8601 datetime, normalized to one timezone |
| body | Clean article text without navigation, ads, footer |
| summary | 2–3 sentences |
| companies | List of organization names |
| people | List of person names |
| locations | List of cities/countries |
| category | String such as funding, product launch, policy, M&A, layoffs |
| funding | Object or null; amount, currency, round, investors for a fundraising article |

Additional fields are allowed. Log schema validation failures. Explain extraction method and why, plus how extraction accuracy would be checked, in the README. Rules, NLP, LLMs, or a mixture are allowed.

Important interpretation: a valid schema proves the record has the right structure, not that entities, amounts, dates, or summaries are true. Missing dates need an explicit policy; never substitute fetch time or invent a publication date silently. Funding information must describe the relevant raise, not unrelated historical amounts in the article.

### Mandatory requirements — stage 3: index

- Chunk article bodies and explain size/overlap.
- Produce actual embeddings and store them in an allowed vector database/index with usable metadata, including publication dates, categories, and companies.
- Re-indexing replaces an article's old chunks; no duplication or stale leftover chunks after an article shrinks.
- Persist outputs so indexing and querying can run without re-scraping/re-extracting.
- Any listed vector option and local/hosted model providers are permitted. No specific vendor is required.

### Mandatory requirements — stage 4: query

- CLI is sufficient; API/UI is optional.
- Semantic search plus metadata filtering for dates, companies, categories, and relevant other fields.
- Answers with source article URLs. Generated answers must be grounded in retrieved chunks and explicitly acknowledge insufficient evidence.
- Support query types rather than hard-coding exact sample wording.
- Run all eight sample queries, saving actual answers, source URLs, and a one-line correctness assessment to `results/sample_queries.md`.

| Sample intent | Required behavior / likely execution path |
| --- | --- |
| Main AI stories | Semantic retrieval plus evidence-grounded overview |
| Startups funded in last 7 days and amounts | Explicit reference time, publication-date/category filtering, structured funding records |
| Recent announcements by a corpus company | Company entity filter plus a defined interpretation of recent |
| All articles mentioning Bengaluru | Complete location-filtered result set over records; top-k retrieval is insufficient |
| Layoff news this month | Calendar-month/date and category filter, synthesis over matching articles with adequate coverage |
| Investors appearing in multiple rounds | Aggregate structured funding data, normalize investor names, count distinct rounds; multiple articles about one round must not inflate counts |
| Revenue in one specifically titled article | Resolve actual corpus title, constrain to article, retrieve revenue passage; do not invent a title or number |
| Mumbai weather today | Refuse as unsupported by the news corpus; no external lookup to mask missing evidence |

This means the system combines semantic retrieval with structured filtering and aggregation. It is not just a vector chatbot.

### Deliverables checklist

- [ ] One public repository link, or a private repository shared with the hiring team.
- [ ] Source with four independently runnable stages or one CLI with four subcommands.
- [ ] requirements.txt or pyproject.toml.
- [ ] .env.example with variable names/placeholders, no real keys.
- [ ] 50+ articles successfully processed for the working corpus.
- [ ] Submission data sample: 5 untouched HTML files and their 5 corresponding extracted JSON records. This sample does not replace the 50-article corpus requirement.
- [ ] results/sample_queries.md covering all eight sample types with real outputs, URLs, correctness notes.
- [ ] README setup in fewer than 10 commands; stage trade-offs, extraction justification, chunking/embedding decisions, limitations, and another-week plan.
- [ ] 3–5 minute screen recording demonstrating end-to-end pipeline and several queries.
- [ ] Clean-environment setup verification and repeat-run checks.

Optional bonuses: Docker Compose, tests, scheduled incremental scraping, hybrid search, reranking, web UI, evaluation script. Tests are listed as optional bonuses but a few tests are also part of the strong code-quality rubric, so focused tests are sensible baseline work. UI is not a core requirement.

### Scoring and interview

| Area | Points |
| --- | ---: |
| Query quality | 25 |
| Extraction quality | 20 |
| Pipeline design | 20 |
| Code quality | 15 |
| Scraping robustness | 10 |
| README and reasoning | 10 |

A submission that does not run from the README scores at most 30/100. Query, extraction, and pipeline design together account for 65 points. Red flags: committed keys, outputs inconsistent with code, untraceable answers, inability to explain code. AI assistants are allowed, but the candidate must explain every line. Shortlisted candidates have a 30-minute walkthrough and a small live change.

### Comparison with LearnTrace

LearnTrace's documented implementation included PDF/PPTX/text/captions ingestion, local audio/video transcription, BM25 lexical retrieval, evidence-linked tutoring, optional generated quizzes, grading/follow-ups, browser-local practice history, source connections, optional playlist metadata, and a polished learner UI. Its README explicitly says embeddings/semantic retrieval were not implemented, sources were held in server memory, and live model/YouTube behavior had not been verified in that audit.

| Dimension | LearnTrace | Zylabs |
| --- | --- | --- |
| Scope | Broad learner product and many connected interactions | Narrow four-stage data pipeline |
| Inputs | Several document/media types | One site's HTML, but uncontrolled real data |
| Retrieval | Implemented BM25 lexical matching | Actual embeddings/vector index required |
| Data lifetime | In-memory sources; browser practice history | Persistent outputs and independent reruns required |
| Reasoning | Tutor/practice workflow | Semantic answers plus exact filters and aggregation |
| Main effort | UI, media, learning flow, grounding | Scraping, extraction accuracy, query correctness, reproducibility |
| Demo/interview | Hackathon story and learner journey | Runnable repository, evidence, explainability, live change |

Subjective assessment, not a benchmark: LearnTrace overall about 8/10 for its breadth; this assignment about 6–7/10 overall, with extraction/query correctness around 7–8/10. Zylabs should need less total product work, but is more exacting about data correctness and repeatability. It is not a trivial copy of LearnTrace. The prior work gives us useful experience with chunking, evidence, refusal, and tests, but does not already satisfy vector search, scraping, persistence, or aggregate queries.

### Proposed approach — not yet selected or implemented

Keep a small Python CLI with four clear stages and shared modules. Use persisted raw HTML/manifest and JSON records, schema validation, a local persistent vector index, and a query layer that routes between semantic retrieval and structured record operations. Introduce a generator only behind a clear evidence contract. Preserve complete record access for exhaustive lists and aggregations; vector search cannot replace it.

Choose a source only after checking current robots rules, permitted access, article cleanliness, date availability, RSS/listing coverage, and enough relevant recent content. No site, library version, provider, deployment target, or paid service is selected yet, and none has been researched live in this session. Library/site choices must be verified when we make them.

Useful defaults to evaluate later: normalize datetimes to UTC, record an explicit evaluation reference time, stable article and chunk IDs, deterministic metadata filters, and provenance for extracted entities/funding. Keep structured records as the source of truth and the vector index as a rebuildable derivative.

### Main risks and mitigations

1. Site blocks, robots restrictions, paywalls, dynamic content: inspect candidate sources early; use a permitted source instead of bypassing restrictions.
2. Poor corpus coverage: ensure recent funding, location, layoffs, company, and revenue examples where available. A truthful zero-result answer is valid when the corpus lacks a match, but a corpus with no useful examples weakens demonstration coverage. Never manufacture articles.
3. Publication dates vs update/fetch dates: preserve distinctions, timezone policy, and explicit time reference. Last seven days and this month are different windows.
4. Entity aliases: company/investor/location normalization matters; Bengaluru/Bangalore aliases need an explicit policy. Names in navigation/related stories must not pollute records.
5. Funding ambiguity: preserve currency and units; do not mix revenue, valuation, and money raised or assume exchange rates. Distinct funding rounds need careful treatment for aggregation.
6. Semantic retrieval misses exhaustive answers: list/filter/aggregate over complete structured records, with citations to their articles.
7. Fluent unsupported generation: answer only from evidence, verify cited URLs belong to supporting records, include unsupported-question checks. A valid citation alone does not establish claim support.
8. Broken reruns or setup: test skipped successful downloads, isolated stage runs, replacement of old chunks, restart persistence, and clean setup.
9. Interview complexity: favor a small understandable design; document reasoning and explain functions and failure paths as we build.

### Planned acceptance checks

- At least 50 distinct successful article records from the selected source, with matching saved HTML and manifest entries.
- Raw HTML preservation and metadata present; failures observable and recoverable.
- Each stage runs from persisted prior outputs, including after process restart.
- Scrape rerun does not fetch already successful articles; index rerun does not grow duplicates and removes stale chunks.
- Manual review of representative records for body cleanliness, publication time, names, summary support, and funding amounts/investors; include failure cases and document measured results honestly.
- Queries cover paraphrases, complete listing, date boundaries, entity aliases, repeated-round aggregation, article-specific revenue, refusal, and empty corpus matches.
- All saved sample outputs generated by the actual code; sources traceable.
- README works in a clean environment within the command budget.

### Tentative work sequence and effort

Five-day sequence: (1) source feasibility and scrape, (2) extraction and record audit, (3) index and query operations, (4) sample runs and correctness/repeatability checks, (5) clean setup, documentation, recording, interview preparation.

The brief's 12–16 focused hours is plausible for an experienced developer using an accessible source and a minimal CLI. A cautious planning allowance is roughly 16–24 focused hours including data review, verification, documentation, and recording; this is an estimate, not a commitment. Extra learning/debugging or a difficult source can increase it. Avoid a UI until required behavior is demonstrated.

### Open questions and next action

- Actual deadline/start of the five-day window is unknown; no calendar due date inferred.
- Preferred local-vs-hosted model path and available API access are unknown; do not expose keys in discussion/logs.
- Source choice is pending live feasibility checks.
- Exact handling of missing publication dates, funding schema, company aliases, and vague recency needs documented decisions during design.
- Current status: understanding phase complete; no scraping, dependency installation, model calls, application code, submission, or recording performed.
- Next practical step: verify candidate source access and representative articles, then settle the smallest explainable architecture and build the four stages.

## 2026-10-17 — Detailed planning requested

- User explicitly requested a proper end-to-end plan and step-by-step explanation before implementation.
- Created PROJECT_PLAN.md covering architecture, proposed stack and rationale, project structure, source/environment pilot, four stages, schema/error policies, date semantics, all eight query execution paths, provenance, idempotency, validation/evaluation gates, packaging, recording, and interview preparation.
- Checked official current documentation for Trafilatura extraction, Sentence Transformers semantic search, and Chroma persistence. These support the proposed component roles; package compatibility and exact model/version choices remain for the pilot.
- Proposed local embeddings and persistent Chroma; JSON records remain authoritative for exhaustive lists and aggregations. Proposed local extraction/evidence baseline with one configurable model adapter for richer extraction/synthesis. API access/provider and actual model quality remain unverified. No paid service selected.
- Detailed safeguards include date precision/timezone provenance, explicit reference time, funding vs valuation separation, distinct-round counting, body-level location recall, tokenizer-aware chunking, index configuration fingerprints, rerun repair, and honest no-key behavior.
- Plan estimates approximately 16–24 focused hours across five day slots; actual deadline unknown. Initial implementation scope is CLI; optional UI and infrastructure are deferred until core requirements pass.
- No application code, dependency installation, source crawling, model download/call, publishing, or submission performed during this planning turn.
- Next action after planning: permitted source/environment pilot, then finalize source and tested model/dependency choices using actual evidence.

## 2026-10-17 — First checkpoint: news-source selection and real extraction pilot

### Authorization and outcome

User requested proceeding with the first checkpoint: choosing suitable news sources. Completed live source/access/discovery research and two five-article technical trials. Selected **IndianWeb2** for development, **TechNode** as backup. They will not be mixed into the final corpus. Full evidence, links, comparison table and limitations are in SOURCE_SELECTION.md; PROJECT_PLAN.md now reflects this checkpoint.

### Investigation and decisions

- Read current robots files directly for YourStory, Inc42, TechCrunch, Entrackr, Silicon Canals, Startup News Australia, Crunchbase News, TechNode, Silicon Republic, Indian Startup News and IndianWeb2. Techdirt and EU-Startups robots requests returned 403; no bypass/retry disguise attempted.
- Compared published terms where discoverable. Inc42's positive ai-input signal does not override its separate restrictions on automated copying/archiving. YourStory and Entrackr likewise have explicit automated-collection restrictions; not selected. Indian Startup News restricts reproduction/copying. TechCrunch has bot/content-use complexities; not selected. These are practical source-selection findings, not a formal legal opinion.
- Initial best technical candidate TechNode: 2,000 unique URLs from its public RSS; 49 feed articles in the preceding seven days at the screening reference. Title screening: 59 funding, 12 layoffs, 40 revenue candidates. Five real pages produced clean bodies (69–135 words), canonical URLs, authors and UTC dates. Bengaluru/Bangalore absent from screened RSS content. Therefore weaker geographic fit than the final source.
- IndianWeb2 RSS returned 100 distinct URLs spanning 2026-09-23 to 2026-10-16. Improved word-boundary keyword screening: funding 31 (6 last seven days), AI 34 (11), Bengaluru/Bangalore 16 (5), revenue 12 (2), layoffs 2 (0). These are candidate keyword hits, not verified categories/events. An initial loose substring location screen gave 17; the final report uses 16.
- IndianWeb2 robots disallows /search and permits tested article/feed paths. Homepage-linked privacy/editorial policies reviewed; no explicit automated-collection prohibition found in that limited review. No blanket redistribution licence established. Raw HTML and full text remain local/ignored; review the required sample's sharing basis before external publication.

### Five-page IndianWeb2 pilot

Saved and reviewed real articles on Circle funding, ThinkMetal funding, ServiceNow AI Passport, GE Aerospace India expansion, and a US visa-policy report with historical layoff mentions. All five returned HTTP 200; canonical URLs match; original copies are byte-identical. Blogger microdata supplies bylines and +05:30 timestamps, normalized to UTC in pilot JSON. RSS timestamps have seconds while on-page dates are minute precision; production extraction should retain this provenance/precision.

Pydantic validates five metadata/body records. These intentionally do not implement the complete assignment schema: entities, summaries, category and funding objects remain future work.

Generic Trafilatura dropped some body spans in four articles (1, 2, 1, 4 respectively), including substantive product-availability and policy evidence. Added a small article-container fallback for IndianWeb2. After scripts/styles/forms/iframes are removed, all **112 compared long body spans** are present after normalization. Final body word counts: Circle 675; ThinkMetal 795; ServiceNow 1,135; GE 1,061; policy 589. This comparison is not a factual-accuracy metric or proof that every format/detail is retained. Read primary outputs and restored spans; excluded navigation/comments/sidebar content by container scope.

Important extraction lessons recorded:
- Circle's INR 25 crore seed raise and INR 25 crore transaction sales are different facts; sales are not automatically revenue.
- ThinkMetal's INR 27 crore round is separate from its investor fund's USD 100 million size.
- ServiceNow availability statements must be preserved.
- GE's industry-revenue context must not become GE's own revenue.
- A policy article's historical layoffs are not new layoffs this month.
- Publisher/press-release claims are not independently fact-checked by this pipeline.

### Files, environment and verification

- Added SOURCE_SELECTION.md, `.gitignore`, `research/pilot-requirements.txt` and small research tools: source_probe.py, extract_source_pilot.py, summarize_source_feed.py.
- Original responses and request metadata are under research/source_probe; pilot HTML, JSON and verification are under research/pilot. Full raw bodies/review outputs excluded by ignore rules; required final five submission samples are not yet packaged.
- Existing bundled Python could not resolve public DNS in restricted execution. Authorized network checks/installations succeeded after normal tool escalation. No automatic approval rejection occurred.
- Bundled Python lacked requests/bs4/Trafilatura; used urllib and available lxml initially. Created local `.venv`; ensurepip bootstrap failed. Used bundled pip targeting that environment to install Trafilatura 2.3.1 and Pydantic 2.14.1; repaired the missing environment pip separately. No global package edits intended.
- Fixed a local shell quoting error and console Unicode-output issue during inspection. An initial exact paragraph comparison falsely flagged inline-link punctuation/spacing; normalized word sequences resolved it. For Blogger, no p elements existed, so comparison was corrected to meaningful text spans rather than incorrectly treating zero paragraphs as complete coverage.
- Request helper initially used three-second sleeps; increased to six seconds after reviewing candidate crawl-delay requirements. Five-page pilots used six-second spacing. Production scraper still needs automatic robots/delay/retry enforcement; research helper is not represented as production-ready.
- Offline extraction rerun and coverage-report generation succeeded. All five canonical/raw-byte checks and pilot schema validations pass. Final dependencies, embeddings, LLMs and full corpus are not tested here.

Final checkpoint verification: `.venv` package dependency check passed with no broken requirements. Explicit checks confirmed five pilot articles, 112 compared body spans with none missing, preserved original bytes, and saved plan/source-report/log files.

### Next step

Implement the production scraper against IndianWeb2 RSS with source-scope filtering, fresh robots enforcement, six-second minimum spacing, manifest/failure logging, bounded retries/timeouts, and successful-article skipping. Target enough candidates for 50+ accepted final records. Full entity/funding extraction follows after the scraper. No model calls, 50-article production scrape, external publishing, repository sharing or submission were performed in this checkpoint.

## 2026-10-17 — Production scraper implementation, ordered execution

User authorized building the production scraper carefully in a clear sequence, with organized progress tracking. Created SCRAPER_CHECKLIST.md before implementation to record contracts and sequential gates.

Implemented independent scrape.py CLI plus source.py (RSS/scope/URL identity), fetching.py (HTTP/robots/pacing/retries), storage.py (atomic raw files/manifest, exclusive writer lock, checksums), and scraper.py (orchestration/run summaries). No article parsing/cleaning in the scrape stage. Added pinned requirements, no-key configuration example, ignore rules and behavioral tests.

Design decisions:
- Retain standard-library HTTP rather than introduce a large scraping framework. Added Protego 0.7.0 after checking official documentation because wildcard/longest-match rules matter; Python's simpler parser is insufficient for the general redirect/rule tests.
- IndianWeb2 public RSS only, exact HTTPS host, dated HTML article paths, objective site-label scope (Business/Technology/Startups/Startup Funding), explicit advice/book exclusions, conservative tracking/mobile-alias normalization.
- Fresh saved robots snapshot each run; no cached permission fallback on policy fetch failure; six-second floor, larger robots crawl-delay/request-rate honored; unsupported visit windows abort visibly.
- Guard redirects before each request; do not leave source or follow redirects into search/private endpoints. Access denial is not retried/bypassed.
- Transient errors use bounded backoff and Retry-After; long cooldown or exhausted 429/503 pauses the batch. Response-size limits, socket timeouts, Content-Length completeness checks, explicit identity encoding.
- Stable full URL SHA-256 IDs; untouched bytes, atomic versioned manifest with status/time/type/hash/source provenance; skip only artifacts that pass byte-count/hash checks. Missing/damaged files repaired on rerun; malformed manifest aborts instead of overwriting state.
- Single writer; ordinary interruption preserves completed pages and releases the lock. Per-request/terminal-failure/article logs and per-run summary, raw feed snapshot and discovery exclusions retained under ignored data/.

Verification to date:
- Initial test attempt failed because the Windows sandbox temporary directory was not writable/cleanable. Moved test artifacts to a verified workspace-local temporary root, checking containment before cleanup; no relaxation of scraper logic needed.
- First 16 behavioral tests passed. Added response completeness/size and persistent throttling tests; corrected the new test's mock context object. Final **18 tests passed** before the larger crawl.
- A real --limit 5 run completed: run 2026-10-17T065640609948-0000; 7 requests (robots, RSS, 5 articles), 5 successful pages, 0 failures; 94 eligible URLs and 6 recorded exclusions. All five saved hashes verified; separate offline QA confirmed article title/body/date metadata in each original. Body QA does not write extraction records.
- Starting target-80 collection after passing the small live gate. This will skip the five verified pages. Full results and real rerun evidence will be recorded after completion.

### Production collection completed and verified

- Main collection run `2026-10-17T065841242212-0000`, 12:28:41–12:36:21 IST: 75 new downloads + 5 verified skips = 80 ready originals; 0 failed article URLs; 77 requests including robots/RSS. Recorded 94 eligible candidates and six explicit exclusions. All observed source HTTP statuses were 200, with no actual transient retries or redirects needed; those edge paths are covered by tests, not claimed as live failures encountered.
- Added two offline helpers: audit_scrape.py checks hashes/counts/URL identities/final-URL duplicates/orphans; check_raw_inputs.py checks article body/title/byline/canonical/time markers without creating final extraction records. Both use the writer lock.
- Final review strengthened non-object JSON manifest rejection and malformed redirect isolation; added request start/duration audit fields and failed-refresh preservation coverage. Final suite: **19 tests pass**. CLI help and package dependency checks also pass.
- The first restricted offline audit was slow (about 110 seconds), appearing stalled; a structural check correctly refused its active lock. Inspected the exact process outside the restricted process view. By the time a guarded attempt to stop that own audit was evaluated, its identity no longer matched because it had finished; the guard raised and **no process was stopped and no lock manually removed**. That audit passed. Subsequent audits with normal file access completed promptly. This was not an automatic approval rejection and no scraper/data bypass was introduced.
- Initial corpus audit: 80/80 hash-valid, no orphan files or repeated final URLs; 80/80 structural checks passed. During rerun, the live RSS added an eligible Jio IPO URL. Incremental run `2026-10-17T070932566202-0000`, 12:39:32–12:39:47 IST: 1 new page, 79 skips, 0 failures, 3 requests. All original 80 hashes and modification times remained unchanged. The increase to 81 is genuine incremental discovery, not duplicate data.
- Final rerun `2026-10-17T071020641864-0000`, 12:40:20–12:40:30 IST, target81: **0 article downloads, 81 verified skips, 0 failures, 2 requests** (fresh robots and feed). Exact manifest-file hash unchanged; all 81 raw modification times and recorded SHA-256 values unchanged. Evidence saved in data/before-rerun-81.json and data/rerun-evidence.json; incremental evidence in data/incremental-rerun-evidence.json.
- Re-audited final collection after the new article: **81/81 valid raw artifacts, 25,493,154 bytes, zero invalid files, zero duplicate final URLs, zero orphan HTML files**. Article-input structure: **81/81 ready, no flags**. These are transport/storage/structure checks, not entity/funding correctness or full extraction acceptance.
- Created results/scraper_verification.md with measured run table, test coverage, evidence paths and limitations; completed SCRAPER_CHECKLIST.md; updated README.md, PROJECT_PLAN.md and SOURCE_SELECTION.md to current status. No raw corpus, publisher content, API keys or project repository was published/shared.

### Remaining limits and next sequential work

- Discovery is the latest 100 RSS items with conservative source labels; two otherwise relevant technology/business stories lack the selected broad labels and were excluded. This is an explicit bounded news scope, not exhaustive publisher coverage. Semantic story/round deduplication remains downstream.
- The 81 raw pages still need complete article-schema extraction, body completeness checks, entity/funding/date auditing and at least 50 accepted final records. Structural readiness does not guarantee those facts.
- Code is reliable for this single-source assignment scope; no internet-scale crawler, scheduler, browser bypass or general multi-site support is claimed. Socket timeout is not a total streaming deadline. Hard crashes can leave a writer lock requiring careful PID inspection.
- Fresh-machine setup, required sample reuse/packaging, embeddings, query engine, sample answers, demo and interview preparation remain pending the appropriate phases.
- Next: define extraction schema/error/provenance contracts; implement one representative article, verify the five-page pilot behavior, process the complete saved corpus and record a manual accuracy audit. The scrape stage is complete and can be re-run independently.

## 2026-10-17 — Independent review and learning roadmap

User requested an honest check of all work so far and prerequisites/resources for learning the entire assignment. They clarified that they already know Python well and have DSA and professional programming experience. The learning roadmap therefore targets applied backend/data/retrieval engineering rather than beginner Python. Employer-specific career details are omitted from this repository-facing document.

Re-read scraper modules, tests, implementation notes and measured evidence. Re-ran all 19 existing tests: pass. Dependency consistency check: no broken requirements. Re-audited the real corpus offline at approximately 08:52 UTC: 81 valid raw artifacts, 25,493,154 bytes, no invalid files, duplicate final URLs or orphan HTML; 81 structurally ready inputs and no flags. No new publisher collection was performed in this review. Previous live no-download rerun remains historical evidence. Confirmed no Git repository exists yet; final repository/setup packaging remains pending.

Added tools/review_scraper_probes.py to reproduce two edge cases with injected fake network/time and contained workspace temporary files. Results saved in results/review_probe_results.json:

1. Two feed URLs A and B, where A redirects to B, yield two ready/stored records but one final destination. URL-request identity does not currently deduplicate redirect aliases. The real corpus has no repeated final URLs; this is a prospective counting/downstream-duplication bug.
2. A 600-second Retry-After stops the first run, but an immediate second run attempts the article after only 12 simulated seconds because cooldown is not persisted. Current instructions rely on the operator waiting. No live 429/503 was observed in the collection, so this was not an observed publisher-policy violation.

These are diagnostic reproductions, not regression tests claiming a fix. No production modules or real raw corpus were changed. Both findings remain open. The existing green suite did not cover them. Earlier wording that the scraper was complete should be read as completion of the original checklist, not comprehensive production hardening.

Created results/PROJECT_REVIEW.md with evidence, findings, proposed fixes and remaining assignment work. Updated README.md and SCRAPER_CHECKLIST.md to expose the open gaps. Created LEARNING_PATH.md with prerequisites, ordered modules, official resources and hands-on exercises linked to our implementation. Verified primary learning sources: MDN HTTP, lxml HTML, Trafilatura quickstart, Pydantic models, Sentence Transformers semantic search/retrieve-rerank, Chroma Python reference, FSDL augmented language models, Python unittest, Pro Git and Stanford IR textbook. FSDL is explicitly identified as an older conceptual resource, not a current API guide. Git/HTTP/vector math are targeted refreshers, not assumptions that the user lacks programming ability.

Remaining assignment stages: full extraction with at least 50 accepted records and factual audit; persistent embedding/index/replacement; grounded and structured query handling; all eight real sample results; five final HTML/JSON pairs with sharing basis reviewed; clean setup, repository and demo. No score estimate, extraction-accuracy claim or completed-query claim is justified yet.

Next recommended sequence: understand HTTP/storage flow, fix redirect identity and durable cooldown with regression tests, then proceed to the full extraction contract and representative-article verification. This turn was review/documentation, not authorization assumed for implementing later pipeline stages.

### Follow-up — subject names and YouTube resources

User asked what umbrella topics this work belongs to and for familiar YouTube instructors. Mapped the project to applied AI/AI engineering (RAG), data engineering, web scraping/information extraction, information retrieval/NLP and backend reliability. Verified creator/publisher resources for Corey Schafer's BeautifulSoup/Requests tutorial, StatQuest's word-embedding explanation, freeCodeCamp's RAG-from-scratch course, Krish Naik's six-project course on freeCodeCamp, and DataTalks.Club's broader data-engineering course. Added a YouTube starting-points section to LEARNING_PATH.md. Recommended scraping fundamentals then a single main RAG course, with optional embedding intuition; noted older API examples and that LangChain/full data-engineering cloud stacks are not mandatory for our assignment. No application code or corpus changes.

## 2026-10-17 — Scraper review findings fixed

User authorized continuing to the next step. Completed the previously recommended scraper fixes before extraction:

- RawStore resolves original URLs, final destinations and persisted alias provenance. A newly observed alias retains the first verified saved ID/raw original and stores its discovery/redirect observation. Repairs and explicit refreshes keep stable identity, preserve alias mapping, and can replace missing or refreshed bytes. Existing v1 manifests remain readable; no automatic destructive migration of legacy duplicates was introduced.
- Collection counts distinct final destinations, rather than each discovered request URL, toward its target. A feed with only A-to-B plus B now correctly reports one ready article and a shortfall for target two. An additional distinct C fills the target. Both feed orders and no-download alias reruns are tested.
- SiteClient persists positive valid Retry-After as a source-scoped timezone-aware resume-after timestamp in policies/cooldown.json. Restart checks this before even robots/feed requests and pauses without network activity until expiry. Corrupt/mismatched/naive timestamp state fails closed. Exhausted 429/503 without a server header persists computed backoff. In-run pacing/backoff behavior remains covered. Accurate wall clock is required; expired state is retained as evidence and no longer blocks requests.
- Added five regression tests (parameterized scenarios within several): both alias discovery orders/reruns, target filling, alias refresh/repair identity, restart/expiry for numeric and HTTP-date plus short cooldowns, corrupt cooldown rejection. Initial expanded suite passed 23 tests; added refresh/repair coverage and corrected save behavior to honor explicit refresh via aliases. Final **24 tests pass**.
- Updated diagnostic probes now write results/scraper_hardening_verification.json, preserving original results/review_probe_results.json as historical evidence. Fixed behavior: one stored/ready unique destination, no duplicate final URL; immediate restart during 600-second cooldown makes zero publisher requests.
- Offline audit at 09:03:07 UTC: existing 81 originals remain hash/size-valid, 25,493,154 bytes, zero duplicate final URLs, zero orphan raw files. No publisher requests or real corpus changes were made for this checkpoint. Updated README, checklist, plan and review follow-up status.

Next checkpoint: full extraction, beginning with schema and missing-field/evidence contracts, followed by one representative article, five-page verification, full-corpus processing and manual factual audit. At least 50 accepted complete records remain required. Full extraction, indexing and query engine have not been implemented in this checkpoint.

## 2026-10-17 — Full extraction implementation and accuracy review (in progress)

User authorized implementing extraction. Created EXTRACTION_CHECKLIST.md first with schema/evidence/quarantine/persistence contracts. Added ArticleRecord/Funding Pydantic models, offline metadata/body extraction, local spaCy entity recognition, source-sentence summaries, conservative financial rules, independent extract.py CLI and persistent extraction runner. Manifest records, not globbed JSON files, define current acceptance. Added raw/extractor/model fingerprints, record checksums, skip-on-valid-cache behavior, per-record errors and atomic outputs. Changed/failed raw inputs exclude stale old records; malformed/missing publication timezone is not replaced by fetch time. Missing authors produce explicit warning/empty list.

Installed spaCy 3.8.14 and en_core_web_md 3.8.0 into project environment. Initial CLI model-download attempt exposed missing click despite resolved package requirements; installed click 8.5.0 explicitly and pinned it. Model download then succeeded. An early synthetic test exposed missing UTF-8 HTML declaration in its fixture; made source UTF-8 parsing explicit and corrected fixture metadata. Windows console encoding caused an initial progress-print failure after a successful record write; extract.py now sets UTF-8 output. These failed attempts are retained in local extraction run/error logs, not presented as successful runs.

Verified Circle first, then all five source pilots. All five preserve compared body spans. Model-only NER initially misclassified Circle/Raveen Sastry and financial relationship rules incorrectly included an investor's affiliation. Added paragraph sentence boundaries, explicit role/subject disambiguation and relationship parsing. Financial corrections distinguish fund sizes/valuation/sales from raised capital, preserve names containing ampersands, handle follow-on participants, identify the funded company behind a product-led title, and mark Inner Sky Labs' round as closing rather than completed. Undisclosed/ambiguous amounts remain null. Generic unnamed angels are not fabricated as named investors. Investor completeness is explicitly warned, especially MoneyTruVa's long shareholder list.

Added nine extraction tests beyond the 24 scraper tests: metadata/UTC/evidence, missing-date quarantine, monetary units, valuation/fund confusion, no-write reruns/stale exclusion, corrupted cached summaries, checksummed schema-valid record tampering, investor affiliation/ampersand handling, and closing status. Final suite at extraction v1.3.1: **33 tests passed**. A synthetic investor test initially exposed abbreviation-based sentence merging that incorrectly selected a company lead as an angel; corrected attribution to require an explicit person/role/joined relationship.

All 81 originals processed. Final v1.3.1 run 2026-10-17T091827433270-0000: 81 written, zero failures. Independent output audit: 81 schema/hash/metadata-valid records, 1,431 compared long publisher body spans, none missing; categories business28/AI12/funding11/technology30. These are not semantic-fact accuracy guarantees. Fifteen-article development review (11 funding plus four nonfunding) yielded 70/70 declared financial/null checks, including known investor names, amounts/currencies/rounds/status. MoneyTruVa's check intentionally covers only two named headline investors and does not imply complete shareholder extraction. Labels/evaluator saved in results/extraction_manual_labels.json and tools/evaluate_extraction_labels.py.

Entity review of the five pilot articles found 13 false classifications among 83 output display names (70/83, about84.3% precision), with known omissions; no exhaustive recall score is claimed. Saved original measured result in results/extraction_label_evaluation_v1_3.json. Added transparent domain-type vocabulary/suffix filtering (newsrag/entity_rules.py) rather than concealing known product/program/person/company confusions. v1.4.0 regenerated all81 with zero failures. Further review outside the five pilots (Funskool, Viyona, WeWork, Cygni, Kuehne+Nagel) exposed substantial remaining product/facility/entity mistakes, especially product-rich articles. Therefore the initial model/rule baseline is not yet represented as final extraction quality or a completed semantic acceptance gate.

Evaluating a type-aware local GLiNER alternative against these errors; installation/model experiment pending. Primary GLiNER repository/docs and model card checked. This is a quality-driven model experiment, not an assumed improvement. Publisher collection remains unchanged; no paid API or external publication used. Final extraction checkpoint status, rerun evidence and sample pairs will be recorded after this review.

### Type-aware model adopted after comparison

- Installed GLiNER 0.2.29, PyTorch 2.14.1, Transformers 5.16.1 and their dependencies. Installation was slow while expanding the Windows PyTorch wheel; inspected only this task's process/CPU/file progress twice, confirming progress. No process was stopped or lock removed. Initial model load exposed missing protobuf for the SentencePiece tokenizer; installed/pinned protobuf 7.36.2 and SentencePiece 0.2.2. No fallback to an untested tokenizer was accepted.
- Compared GLiNER on ServiceNow, Funskool and Circle. The product label materially separated toy/software products from companies; recovered omitted companies and real people. Recorded experiment in data/extraction/entity-model-pilot.json. Selected `urchade/gliner_small-v2.1` at fixed revision `4e091416cf7c3481db542c2a3d26156916f3a47f`. The newer v2.5 model was inspected but not downloaded/adopted. Model/setup are public downloads, not uploads of source articles or remote inference.
- Added local_entities.py and setup_entity_model.py. Setup saves a standalone safetensors model, tokenizer and embedded encoder configuration with an identity/asset checksum manifest. Extraction requires these local assets and uses local_files_only loading. Includes model/revision/assets/settings/library versions in each fingerprint. Keeps spaCy for linguistic/sentence analysis and funding-source parsing. No silent production fallback to the weaker entity baseline.
- Entity windows overlap by 15 words, begin with a 90-word target, and shrink until within 240 subtokens and 300 model word units. Over-budget indivisible tokens fail rather than silently truncate. Batches retain global source character offsets and model scores; scores are not calibrated correctness guarantees. Product predictions are excluded from the requested entity lists.
- Added tests for entities near the end of long articles, exact evidence offsets, oversize-token failure and generic group/name cleanup. Final suite so far: **39 passing tests**; dependency check reports no broken requirements. Synthetic tests use a stub backend where appropriate; the real downloaded model was separately exercised on original source pages.
- Extended financial coverage after reviewing Peptris, WASH bond and Capital India Finance: distinguishes venture rounds, strategic investment, debt, and other support; reports closing/committed status; prevents committed current support from inheriting historical Series A investors/stage. Explicitly handles NCD/bond amounts and source board/funder where supported. These three supplementary source checks extend the original 15-article sample to18. The updated v2.0.1 corpus passes **91/91 declared financial/null checks**; this remains development review rather than independent population accuracy.
- First GLiNER pipeline run on five pilot pages succeeded. Full v2.0.1 run `2026-10-17T093622534435-0000`, 09:36:22–09:42:33 UTC: 81 written, zero failures, all81 accepted structurally. Final entity review identified residual generic groups and a joined heading fragment; added type-neutral cleanup and regression coverage. Running v2.0.2 across the corpus so stored fingerprints/content reflect the corrected final rules. Raw originals remain unchanged.
- Preserved initial entity evaluation and broader pre-GLiNER lists in results/extraction_label_evaluation_v1_3.json and results/entity_baseline_additional_review.json. Do not advertise corrected development-sample precision as unseen-data accuracy. Named physical facilities may appear as locations; they are not commercial companies. Known omissions and incomplete shareholder lists remain explicit limitations for downstream filtering/aggregation.

### Extraction checkpoint completed — final evidence and handoff

User reiterated authorization to continue carefully. Completed the final verification and documentation sequence without starting the next implementation stage.

- Final extractor v2.0.2 run `2026-10-17T094321433861-0000`, 09:43:21–09:49:28 UTC: processed/wrote 81 records, zero failures, 81 accepted, 102 explicit warnings. All raw originals remain unchanged.
- Independent saved-output audit at 09:50:11 UTC verifies 81/81 schemas, record/raw checksums, original title/date/byline and 1,431 long source body spans. No failures. Categories: business 26, AI 12, funding 14, technology 29. Coverage is not proof of perfect table layout, every word boundary or publisher truth.
- Final financial development evaluation: 18 distinct articles, 91/91 declared checks. Entity review: 10 articles, 147 returned display strings, 145 judged correctly typed and two incorrect company fragments (`Group`, `Kuehne+NagelWith`). Approximately 98.6% development-sample type precision; known omissions remain and recall is not exhaustively labeled. Examples informed tuning, so this is not held-out/generalization accuracy or independent human review.
- Automated suite remains 39 passing tests and package consistency check passed. No production logic was changed after that final suite; the remaining edits were verification evidence/documentation.
- Offline rerun `2026-10-17T105656511799-0000`, 10:56:56–10:57:29 UTC: processed 81, skipped 81, wrote zero, failed zero, accepted 81. With socket connections blocked and offline model mode enabled, observed zero network attempts. All accepted record hashes and nanosecond modification times are identical before/after. Run and manifest bookkeeping updates normally. Evidence: results/extraction_rerun_verification.json. A library FutureWarning about torch.jit.script was emitted; the run completed successfully.
- Saved five original-pilot full-schema HTML/JSON pairs locally in data/samples with a manifest. Independently verified all five against raw and accepted-record bytes and validated ArticleRecord schemas; hashes/results are in results/extraction_sample_verification.json. Samples remain ignored local artifacts; no redistribution/publication took place.
- Completed EXTRACTION_CHECKLIST.md and updated README, PROJECT_PLAN and results/extraction_audit.md. Learning references/modules remain in LEARNING_PATH.md. Historical failed baseline results are retained.

Next implementation checkpoint: chunking, real embeddings and persistent vector indexing, including metadata filters, restart/rerun checks and obsolete-chunk removal when a record changes. Downstream must use a complete current acceptance manifest and verify checksums, never glob old record JSON. Exact lists/aggregations must normalize aliases, inspect source body/event evidence and retain unknowns; model entities/investors are not exhaustive truth. Query implementation, eight real query evaluations, clean-machine setup, sample-sharing review, repository and demo remain unfinished. Extraction checkpoint completion does not claim the overall assignment is complete or deployment-ready.

## 2026-10-17 — Persistent indexing implementation (in progress)

User authorized the next checkpoint and emphasized sequential implementation. Created INDEXING_CHECKLIST.md before coding: model/storage choice, bounded chunks, validated inputs, failure recovery, lifecycle tests, five-page pilot, full corpus and final evidence. Read the existing extraction contracts and phase 3 requirements. Verified primary MiniLM model/pooling documentation and Chroma client/configuration documentation.

Selected sentence-transformers/all-MiniLM-L6-v2 revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384-dimensional masked mean pooling with L2 normalization, through the existing Transformers runtime. Same encoder serves documents/questions. This is a real trained sentence model, not hash/random vectors. Chroma 1.5.9 supplies persistent cosine search. Initial restricted-network package/model-metadata requests failed DNS; approved network-enabled retries succeeded. Installed/pinned Chroma, downloaded fixed model weights once, saved local safetensors/tokenizer/config checksums. No article uploads or paid inference. Package consistency check passes. Hugging Face emitted harmless anonymous-download/symlink-cache warnings; setup completed.

Implemented body-only source character chunks with a 200-wordpiece budget, about 30-wordpiece overlap and preferred paragraph/sentence endings. Retokenize slices and refuse encoder inputs over 256 total tokens. Metadata carries source, date, category, offsets, order and record checksum. Rich entity/funding records remain separate; eligible article-ID constraints support later exact filtering. Index/read validation checks the complete extraction manifest, record schema/hash/identity and raw hashes. Configuration records model assets/libraries, chunking and collection identity.

Synchronization uses the shared data lock and marks the index incomplete before writes. Each changed article's embeddings are prepared first, then chunks upserted and obsolete tails deleted. Completion follows exact chunk/metadata/vector verification and orphan removal. Interrupted operations remain explicitly unready for search until repaired. This is recoverable multi-step synchronization, not an asserted atomic Chroma transaction. Unchanged cache checks include vector digests; incompatible configurations require a separate index directory. Search revalidates the complete current corpus/index and refuses stale state.

Added nine lifecycle tests with actual Chroma and explicitly synthetic vectors. Initial run exposed a test cleanup typo in Chroma's private cache attribute (`_identifier_to_system`, singular), causing Windows file cleanup errors; corrected test teardown after inspecting installed source. All nine tests then passed, including shorter replacement, unchanged no-embedding rerun, empty/category/date/article-ID filters, unaccepted removal, corrupt raw/record inputs, incomplete extraction, configuration mismatch, interruption after upsert, vector tampering, orphan chunks and invalid embeddings. This does not establish semantic model quality. Five-page real-model pilot and predeclared retrieval probes are the next gates.

Five-page real pilot completed: run `2026-10-17T123529563940-0000` wrote five articles / 40 chunks, all using real 384-dimensional model embeddings. Initial full-body tokenization emitted a generic >512-token warning; only token offsets were being computed, not full-body model inference. Disabled that inappropriate tokenizer warning for the offset pass; bounded chunk inference still rejects oversized input. Final suite at this point: **48 tests passed** (24 scraper, 15 extraction, nine indexing); output saved in results/indexing_test_run.txt.

Separate-process pilot audit at 12:37:51 UTC: full source character coverage, checked vector/metadata persistence and all ten predeclared development retrieval probes found the intended article at rank one. The small five-document corpus makes this only a smoke test. Offline socket-blocked rerun skipped all five, encoded zero chunks and wrote/removed zero vectors, retaining vector-state digest; no network attempts. Evidence: results/index_pilot.json and results/index_pilot_audit.json. Full 81-article indexing follows this passed pilot gate.

Full build completed: run `2026-10-17T123850380274-0000`, 12:38:50–12:40:26 UTC, **81 articles / 484 real 384-dimensional chunks**, no failures. Preserved results/index_full_build.json before later run summaries changed. A separate isolated real-model probe shortened a copy of ThinkMetal from seven chunks to one, deleted six obsolete chunks, rejected stale search beforehand, and removed its final chunk when acceptance was removed. Original production record unchanged; zero network attempts. Fixture is retained under tmp/index-replacement; evidence is results/index_replacement_verification.json. This was a controlled extracted-record edit, not a live publisher refresh.

Full offline audit completed at 12:42:06 UTC: all 81 accepted inputs and 484 persisted vectors verified, every body character covered by source spans, largest encoder input 202 total tokens (cap 256). Rerun `2026-10-17T124125681923-0000` skipped all 81, encoded zero chunks, wrote zero article replacements and removed zero chunks; article/vector-state digest unchanged. Patched embedding calls to fail during the rerun, independently confirming the skip path. Socket connections blocked throughout local model load/rerun/retrieval: zero network attempts.

All ten declared development queries found their expected article within the first five distinct articles deduplicated from ten returned chunks: nine rank one, one rank two (Circle's broader used-goods investment question). Did not rewrite questions to improve the score. Inspected actual returned excerpts: relevant article retrieval is not the same as sufficient answer evidence; Circle's best chunk is a quote rather than the round amount, and a GE result contains aviation-growth context. Later answers must gather neighboring/source-record evidence for precise facts. Category and explicitly empty eligible-ID filtering passed. Full output: results/index_audit.json. Starting another fresh process for the final persisted-state/retrieval comparison.

### Indexing checkpoint completed

Fresh-process audit finished at 12:43:37 UTC, reopening the persisted full collection without rebuilding. All 81 records / 484 vectors verified again; ten retrieval result lists retained exactly the same chunk IDs/order, text, metadata and distances. Maximum distance difference: 0.0; article/vector-state digest unchanged. No network attempts. Saved results/index_restart_audit.json and the explicit comparison results/index_restart_verification.json.

Completed all eight INDEXING_CHECKLIST.md gates. Updated README setup/search commands and limitations, PROJECT_PLAN handoff, LEARNING_PATH module walkthrough/exercises, and .env.example (local embedding setup needs no keys). Full evidence narrative: results/indexing_verification.md. Tests: 48 passing; dependencies consistent. Original HTML/structured records were not modified by indexing or the isolated replacement fixture. No repository/sample publication, credentials or external messages used.

Next is query planning and grounded answers: combine semantic retrieval with complete structured/body filtering, handle publication versus event time and distinct financing rounds, expand evidence around retrieved passages, cite sources and refuse unsupported questions. The ten indexing probes are not the assignment's eight final query outputs. Full answer evaluation, clean-machine setup, sample-sharing review, repository and demo remain unfinished. Current per-search whole-corpus validation/shared locking is deliberately conservative for 81 articles and needs redesign for a large concurrent production service; indexing completion is not an unqualified deployment-readiness claim.

## 2026-10-17 — Query checkpoint implementation (in progress)

User authorized the next checkpoint. Created QUERY_CHECKLIST.md, re-read the phase 4 plan and actual five-page assignment with the PDF skill. The project venv does not have pypdf; used the available bundled document runtime for this read-only inspection instead of adding a production dependency. Confirmed the brief permits grounded non-LLM answers: an LLM is not compulsory. Selected explicit deterministic structured operations and source excerpts; no provider credentials, article upload or simulated LLM output.

Inspected all extracted funding records plus body revenue/layoff mentions. Important cases: revenue in the Adani-affiliate article is Vishakha Renewables' FY26 figure; GE's revenue sentence describes Indian airlines; Lorazzo has growth and a future target; Federal Bank reports profit, not revenue. Layoff mentions include explicit denial, historical years and ranking eligibility rules. Current extracted investors appear unique across distinct funds; parent IAN names must not collapse IAN Alpha Fund and IAN Angel Fund into one investor.

Added query.py, query_planner.py and query_engine.py. Plans expose intent, company/location/title and aware UTC publication windows. Last seven days is rolling; recent defaults to 30 days; this month uses the current UTC calendar month. Answers disclose the publication/event distinction. Complete location/financial/aggregation operations scan accepted records; semantic AI/company queries use eligible IDs and real Chroma vectors, and article-revenue retrieval is restricted to a resolved title. Exact source excerpts/offsets/URLs are retained, with corpus limits and explicit unsupported/ambiguous outcomes. Full current index/input validation and shared lock precede each answer; outputs persist in data/queries/runs and latest.json.

Initial 11 query tests found a planner bug: 'Recent company updates' treated 'Recent' as a company. Corrected generic-name handling; all 11 then passed. Added safeguards for numerical revenue evidence versus unrelated counts and preserved table headers/rows. Added a twelfth test and normalization for legal company suffixes and stage aliases, so repeated reports do not become false repeat-investor rounds. Missing/unknown same-company stages collapse conservatively, potentially undercounting; unknown identity is disclosed. Added original lead context to article-specific revenue evidence to retain its subject. These refinements require a final evaluation rerun.

Created tools/evaluate_queries.py: eight exact assignment-family questions, eight paraphrases and four negative/ambiguity probes, all with blocked socket connections and frozen reference 2026-10-17T12:00:00+00:00. Engine answers and source-span checks are recorded mechanically; results/sample_queries.md is generated from actual output, with final per-query judgments pending source review. This is a development evaluation, not independent semantic/population accuracy. First corpus run is in progress; no final query completion claim yet.

First actual corpus evaluation passed its automated checks: five AI stories, three reported weekly venture announcements plus one closing round, one ServiceNow announcement, 14 explicit Bengaluru/Bangalore articles, two current-month publications with contextual layoff mentions, no repeated investor established across nine reported venture reports/23 names, source revenue ₹1,893.4 crore FY26, and weather refusal. Eight paraphrases matched intended families and structured item sets; four negatives returned unknown-company no matches, profit-only insufficient revenue, ambiguous-title clarification and unsupported secret request. Zero socket attempts. Preserved initial output in results/query_evaluation_initial.json rather than hiding development history.

Source/output review verified the distinctions above. Enhanced revenue output with the article's original lead sentence to show Vishakha as the subject. Added actual previous-calendar-month bounds and normalized reference time to UTC before month calculations; an IST timestamp crossing the UTC boundary is tested. Review also found a combined-filter routing risk: a funding question mentioning Bengaluru could be routed as a location list. Financial intent now takes precedence and the location/company filters constrain its complete record scan. Added a regression test; final query unit count is 14 (62 total including existing stages). Subsequent full suite/evaluation are running against this frozen code.

Added digest-bound source-review rendering so a later changed answer cannot silently inherit an old correctness judgment. Actual answers remain generated from code; manually written material is limited to declared review judgments/limitations. No LLM or external service was introduced. Documentation explains conservative round grouping, incomplete investor recall, source-extractive summaries and bounded language/event interpretation. No overall assignment completion or deployment readiness claimed.

### Final query evaluation and source review

Frozen-code final test suite: **62 passing tests** (24 scraper, 15 extraction, nine indexing, 14 query), 13.577 seconds test execution excluding startup. Final real-corpus evaluation completed at `2026-10-17T13:04:16.011459+00:00`: all eight sample families, eight paraphrases and four negative/ambiguity probes pass the declared checks. Exact source spans and URLs validate; all 14 location matches agree with independent scanning; structured paraphrase sets match; expected revenue is present; weather is refused. Zero network attempts with connections blocked during evaluation. Evidence: results/query_test_run.txt and results/query_evaluation.json.

Reviewed all eight actual outputs against saved article evidence and retained material limits. Saved results/query_source_review.json with hashes covering each specific plan/answer/items/sources; tools/render_sample_queries.py applies judgments only on matching outputs, so future changes revert to pending review. Generated results/sample_queries.md contains actual engine answers plus one correctness judgment per question. No idealized answer text was substituted. Source review is agent-performed, not independent human annotation or publisher fact-checking.

Updated QUERY_CHECKLIST, README, PROJECT_PLAN, LEARNING_PATH, .env.example and results/query_verification.md. This completes the query implementation/evaluation checkpoint, subject to its explicit bounded parser/event/identity/recall limitations. Running a direct command-line smoke check as the final interface check. Next delivery gates remain clean-machine setup under ten commands, sample-sharing review/packaging, repository delivery and required demo; no remote publication or full-assignment delivery claim.

Direct query.py CLI smoke check completed successfully with the frozen-time Bengaluru question and --json. Returned exactly the evaluator's 14 article IDs in the same order. Verified all eight final source-review digests still match generated answers, no pending judgments remain, and the shared lock is released. Saved results/query_cli_smoke.json and results/query_cli_verification.json. No production code changed after the final 62-test suite/evaluation; final edits were reports and completion records. Query checkpoint is complete.

## 2026-10-17 — Delivery preparation

Started four explicit delivery gates in DELIVERY_CHECKLIST.md: isolated setup verification, submission packaging, repository delivery, and actual 3–5 minute demo. All four pipeline stages are complete; delivery gates are tracked separately to avoid claiming the assignment is already submitted.

Rewrote README's primary setup as nine commands, including pinned spaCy model installation and both local model setup commands. Installed Python 3.12 is a prerequisite: the current host's Windows launcher reports no installed Python, so the available bundled Python runtime bootstraps verification. Initial isolated venv creation failed because sandbox permissions blocked ensurepip's temporary writes; the same creation succeeded with approved elevated execution. Fresh requirements installation is still running; no successful clean-environment result is claimed yet.

Prepared tmp/submission-check/project with 44 hashed Python source files, all 81 saved original HTML inputs and checked local model assets. Did not copy extracted records, vector index, query outputs or development site-packages. This verifies a fresh isolated dependency environment on the same Windows host, not a different machine or operating system. Model downloads are reused explicitly; extraction and embeddings will be recomputed. Preparation evidence: results/clean_environment_preparation.json.

Packaged five original HTML/production JSON pairs with schema/identity/checksum verification; evidence: results/submission_sample_verification.json. Added provenance manifests, samples/README.md, THIRD_PARTY_NOTICES.md, an import helper that refuses existing destination folders, and Git attributes preserving sample bytes across Windows line-ending conversion. The publisher's public policies did not establish an affirmative redistribution licence; attribution is retained and publisher content is not represented as our own open-source code. No samples have been publicly uploaded.

User selected GitHub account chetan14806 and public visibility and asked which repository to create. Recommended empty public news-rag-pipeline with no generated README, ignore file or licence. Initialized local Git main branch. No remote, commit or push exists yet; Git author identity is not configured and GitHub CLI is unavailable. Continue independent local verification while awaiting the created repository link. Next: finish fresh installation, replay tests/extraction/index/query, finalize package checks and prepare the real demo walkthrough.

Sample import smoke check passed: tools/import_samples.py imported all five verified fixtures into the new tmp/sample-import-verification directory, without touching the production corpus. Added DEMO_GUIDE.md with a timed four-minute walkthrough, real CLI examples, evidence/limitation explanations and recording acceptance criteria. Its --as-of option was checked against query.py. This is a prepared guide, not a completed video. Fresh installation is still progressing through dependency installation; package filesystem timestamps show continued progress. A read-only system-process inspection was unavailable under the sandbox; no unrelated processes were stopped.

### Delivery verification resumed; sequence corrected

User correctly challenged bringing up GitHub before final verification. Agreed sequence: finish fresh setup/full replay, verify package, record/review demo, then GitHub and submission. The local Git initialization remains harmless preparation; do not move to remote publication while verification is unfinished.

Fresh requirements installation succeeded, followed by the pinned en_core_web_md 3.8.0 wheel. pip check reports no broken requirements. Saved the complete installed package snapshot in results/clean_environment_freeze.txt. Started tools/verify_clean_environment.py, which runs dependency check, all tests, extraction from all saved raw originals, extraction audit, fresh index, index integrity/rerun audit, and actual query evaluation in the separate workspace. It saves per-step output/exit codes and stops on any failure. The fresh environment passed all 62 tests (18.896 seconds test execution); full extraction is running and has begun writing new records.

Added tools/package_submission.py to build a local source archive from explicit allowed roots/extensions, check required deliverables/five pairs, scan common credential patterns, and reopen/hash-check every archived file. Runtime data, downloaded models, environments, temporary workspaces and the assignment PDF are excluded. The pattern scan has bounded coverage and is not claimed to recognize every secret format. Archive creation waits for final verification/report updates. Added INTERVIEW_NOTES.md for code tracing, tradeoffs, limitations and a small change exercise.

Read the Computer Use skill and recording-related runtime instructions. The supported desktop runtime failed before initialization with `failed to write kernel assets: The system cannot find the path specified. (os error 3)`. Resetting and retrying produced the same error. No desktop input or capture occurred. The actual screen recording remains blocked by this tool availability issue; the prepared walkthrough is not a video. Continue all independent verification/package work and provide a clear local recording handoff if the runtime remains unavailable.

## 2026-10-18 — Final comparison caught an ordering defect

The first complete fresh-environment replay passed installation, 62 tests, 81-record extraction/audit, 484-chunk indexing, ten retrieval probes, an 81-skip no-embedding rerun, eight query families, eight paraphrases, four negatives, raw input audits and a real query.py CLI check. All eight answer payloads matched the development snapshot. However, strict record comparison found only 80/81 byte-identical records. Preserved this failed strict comparison in results/clean_environment_initial_comparison.json, with the initial source snapshot in results/clean_environment_initial_preparation.json.

Investigated the single mismatch: CEAT's companies list contained identical values, but `RPG Group` and `RPG group` swapped positions. Sorting a set solely by casefold leaves tied values in Python's randomized set order. Fixed both entity-refinement and funding-company sorts to use `(value.casefold(), value)`, retaining original spellings with deterministic tie-breaking. Bumped extractor version from 2.0.2 to 2.0.3 so old cached records are invalidated. Added a separate-process regression covering six PYTHONHASHSEED values; it passes.

Updated the isolated source snapshot with the two changed production files and new regression test. Started complete development and isolated refreshes against separate data directories, with full tests, all 81 records re-extracted, indexes rebuilt/audited and answers re-evaluated. Initial saved HTML and model assets remain unchanged. No archive is considered final until the corrected comparison passes. Current implementation test count is expected to be 63, pending the full suite outcomes. The development refresh uses its existing environment; only the isolated copy is the fresh-environment verification.

Both corrected full test suites passed: 63 tests, 16.712 seconds in the isolated environment and 15.997 seconds in development (excluding startup). Full extraction refreshes are running. The Computer Use plugin/runtime was refreshed during the session; reading its new skill and retrying initialization now succeeds. The earlier runtime failure is therefore historical, not a current confirmed blocker. Asked the user whether to record their own narration using the guide or request a silent captioned walkthrough; no recording has yet been created.

User explicitly chose to narrate and record the demo themselves. Prepare the guide/commands and leave the actual capture to the user; do not create a substitute silent video. Added timing guidance to distinguish model startup cuts and saved run summaries from newly executed output. Continue verification and packaging before the handoff. GitHub remains after the demo, following the user's corrected sequence.

### Corrected verification complete

Both complete 2.0.3 refreshes passed every step. Each extracted/wrote/accepted 81 articles with zero failures, retaining 102 explicit quality/unknown-field warnings. Both extraction audits passed, including 1,431 source-reference spans. Both indexes rebuilt 81 articles/484 chunks; ten retrieval probes passed, metadata/integrity checks passed, and unchanged reruns skipped 81 with zero embeddings. Both query evaluations passed eight sample families, eight paraphrases and four negatives with zero network attempts during the audits.

Final independent comparison passed: all 81 records byte-identical; prepared production/test source hashes match replayed/current code; eight answer payloads match; all eight original source-review hashes still match; raw integrity/readiness audits pass; direct query.py returns the evaluator's location items and exit zero. Evidence is in results/clean_environment_verification.json, development_refresh_verification.json and per-step logs. Corrected the development report's scope label to identify its existing environment separately from the isolated verification environment.

Regenerated the five samples from accepted 2.0.3 records. Imported them into tmp/sample-import-v203 and verified all ten file bytes, five-pair count, existing-directory refusal and unchanged files after refusal. Updated README, plan, checklist and results/delivery_verification.md with scope and remaining work. Removed employer-specific biography from repository-facing learning/history documents while preserving the project rationale. Final local source archive verification follows; the user-recorded demo and GitHub/submission remain pending.

### Local package gate completed

Built dist/news-rag-pipeline-submission.zip with 135 source/document/report/sample files. Common credential-pattern scan found no matches; archive CRC/file-list validation passed and every archived file matched its source SHA-256. Models, complete corpus, environments, temporary workspaces, assignment PDF and Git internals are excluded. The verification manifest is results/submission_package_verification.json and is kept beside the archive to avoid a self-referential archive hash. Regenerate once more after these final status updates so the delivered archive includes the completed checkpoint records. No further production code changed after the corrected tests/replays.

Current handoff: all four pipeline stages, fresh-environment verification and local packaging are complete with their documented limits. Two delivery gates remain: the user narrates/records the 3–5 minute demo using DEMO_GUIDE.md; after that, create/publish the agreed public repository and submit. No video, repository URL or submission is falsely claimed complete.

## 2026-10-18 — End-to-end review and extraction 2.0.4

Reviewed the five-page assignment, all four entry points and core storage, fetching, extraction, indexing and query paths. The original 63-test suite passed. New probes reproduced AI announcements routed to a missing-company clarification, numeric repeated-investor wording routed to funding, revenue forecasts refused as weather, explicit date bounds overridden by defaults, and trailing time windows included in location names. Corrected these cases and preserved company/topic specificity. Layoff relative context now uses article publication year and its prose describes the requested window.

Real-source inspection found merged headings/paragraphs (`modelLorazzo`) and merged table cells (`MumbaiCargoPilot`). Extractor 2.0.4 preserves block boundaries, all heading levels and table columns. Both environments re-extracted all 81 originals for the heading fix, then force-reprocessed the seven bodies affected by the final within-review table adjustment. Seventeen bodies differ from the earlier snapshot. All 81 final bodies/title/date/byline values match recomputation by the final parser, and all 1,431 checked long publisher spans remain present. No original HTML or source manifest was changed, and no new live scrape occurred.

Hardened the index audit so failed retrieval probes affect its overall pass/exit status. Removed the rerun verifier's dependency on a development research file excluded from the archive; it now uses the included five-sample manifest. The demo guide explicitly includes the scrape stage. Added regressions for the corrected behaviors and five additional real-query wording probes.

Final evidence: 69 tests pass in both environments; all 49 checked source/config files match; all 81 record files are byte-identical; both indexes contain 484 chunks/384 dimensions; all ten retrieval probes pass; unchanged indexing performs no embeddings/vector writes. Extraction skips all 81 with unchanged bytes/mtimes and zero writes. All 25 actual query cases pass with exact source spans and zero network attempts. All eight sample answers match across environments. The actual isolated CLI reproduces the evaluator's 14-item city answer and exits zero.

The 18-article financial development check remains 91/91. The earlier ten-article entity sample now has one identified fragment among 146 display strings, but a fresh targeted review still finds institution/platform type errors and a generic Group fragment. Recorded concrete remaining examples in results/final_review_entity_spotcheck.json; no general accuracy estimate is inferred. Changed sample outputs 3, 4, 5 and 6 were reviewed again and their digests updated; preserved the earlier judgments in results/query_source_review_v203.json.

Regenerated the five 2.0.4 pairs. Their import preserves every paired byte; a second import refuses an existing destination without changes. Current aggregate evidence is results/final_review_verification.json and the human-readable assessment is results/FINAL_REVIEW.md. Updated README, plan and delivery status to distinguish current results from historical 2.0.3 installation/replay evidence. The existing separately installed isolated environment and checked model assets were reused; dependencies were not reinstalled in this review, and no other machine/OS was tested.

Refreshed the local submission archive after the final documentation changes; all 175 included files pass CRC/file-list/file-hash checks and the common credential-pattern scan. The actual archive hash is recorded in results/submission_package_verification.json. The narrated recording and remote repository/submission remain outstanding. No publication or messaging was performed by this review.

## 2026-10-18 — Resumed entity-quality continuation

The user returned after a usage limit and explicitly asked to continue. Confirmed the four stages were already implemented and the last complete snapshot was verified 2.0.4, rather than treating the interruption as an unfinished pipeline implementation. Continued with the concrete entity type errors in final_review_entity_spotcheck.json.

Added source-backed institution-name disambiguation, conservative removal of operations-role location fragments, explicit platform-list context checks, and filtering of standalone generic organization fragments. No article-specific platform names were added to a lookup table. Seven new regression tests include unseen institution/platform names and safeguards for genuine cities, unrelated later platform sentences, and named groups. Targeted tests pass; extractor version 2.0.5 invalidates old cached records.

Active verification: tools/verify_clean_environment.py is rebuilding all 81 records, indexes and 25 query cases in the development and existing isolated environments. Progress reports are results/entity_refinement_primary_verification.json and results/entity_refinement_isolated_verification.json, with matching per-step logs. Baseline entities/answers are preserved in tmp/entity-refinement-baseline.json. After successful replays: compare source/record/answer bytes, recheck the three known error cases, run extraction rerun and sample import checks, refresh source-review hashes only if answer payloads change, update current status and regenerate the archive. Do not describe the previous 2.0.4 archive as containing these new fixes until it has been rebuilt.

### Entity-quality continuation completed

Both complete replays passed. The final current-source suites pass 76 tests in each environment. All 50 checked source/config files and all 81 record bytes match. Actual entity changes are exactly the nine reviewed records; the other 72 entity lists are unchanged, and every correction-evidence span matches the body. All three recorded error cases are resolved. The original ten-article development labels contain no remaining identified fragments among 145 display strings, but recall remains incompletely labeled and this is not a held-out/general accuracy claim. The financial regression remains 91/91.

Both indexes retain 484 chunks, pass all ten retrieval probes and skip 81 articles without new embeddings/vector writes on unchanged reruns. All 25 query cases pass with zero network attempts. The eight required answer payloads are unchanged from 2.0.4 and match across environments, so their existing source-review hashes remain valid without rewriting judgments. The actual isolated CLI exits zero and reproduces all 14 city items.

The offline extraction rerun skips all 81 with zero writes and unchanged record bytes/mtimes; raw integrity still passes without duplicate destinations/orphan originals. Regenerated five current 2.0.5 sample pairs. Sample import preserves paired bytes, refuses an existing destination and leaves its files unchanged. Aggregate evidence is results/entity_refinement_verification.json; concrete deltas are in results/entity_refinement_changes.json. Original spot-check observations are preserved with a resolved follow-up pointer.

Created CURRENT_STATUS.md to remove ambiguity after future usage-limit interruptions. Updated the README, plan, review and delivery checklist with the completed 2.0.5 checkpoint. The archive is regenerated after these final documentation changes and checked using tools/package_submission.py; its authoritative file list/hash is results/submission_package_verification.json. No live scrape, new dependency installation, remote publication or message sending occurred. The only remaining delivery gates are the narrated demo and remote repository/submission; no pipeline stage or rebuild is left in progress.
