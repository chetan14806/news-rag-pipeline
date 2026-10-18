# News RAG Pipeline — end-to-end implementation plan

Date: 2026-10-17 (Asia/Kolkata)
Status (updated 2026-10-18): extractor 2.0.5 retains paragraph/table and query/time fixes and corrects entity types in nine records, resolving the three recorded error cases. All 76 tests pass in both environments, all 81 records match byte-for-byte, the index contains 484 chunks, and the eight actual answers/review hashes remain unchanged. Five current sample pairs and the refreshed local archive are verified. See CURRENT_STATUS.md and results/entity_refinement_verification.json for the completed continuation; milestone sections below preserve development history. The verified source is now published at https://github.com/chetan14806/news-rag-pipeline (initial application commit `65616c4`). The narrated demo and final assignment submission remain.
Source of requirements: Zylabs_Intern_Coding_Assignment.pdf, all five pages.
Continuing work record: PROJECT_LOG.md.

## 1. Outcome and scope

Deliver a small, understandable Python application that turns at least 50 real technology/business articles from one permitted news site into a persistent, searchable collection. It must answer semantic questions, complete filtered lists, date questions, and funding aggregations with article URLs, and refuse unsupported requests.

RAG means retrieval-augmented generation: find relevant stored evidence first, then use it to construct an answer. Here, exact filtering and counting must also operate over structured records. A vector database alone cannot guarantee complete lists or accurate totals.

Core scope: four independent CLI stages, real data, persistent artifacts, accurate query operations, evaluation, clean setup, documentation, demo, interview preparation. UI, Docker, scheduling, reranking, and sophisticated orchestration are deferred until core acceptance criteria pass. No model training or fine-tuning is needed.

## 2. Proposed architecture and tool choices

```text
One permitted news source
        |
        v
SCRAPE -> untouched HTML + fetch manifest + failure log
        |
        v
EXTRACT -> schema-validated JSON records + validation/error log
        |                                  |
        v                                  |
INDEX -> article chunks + local vectors    |
        |                                  |
        +--------------+-------------------+
                       v
QUERY -> validated intent/filters -> semantic retrieval OR complete record operations
                       |
                       v
             supported answer + source URLs + coverage/limitations
```

Proposed Python components:

| Need | Planned choice | Reason / condition |
| --- | --- | --- |
| HTTP fetching | Standard-library urllib plus Protego robots handling | Implemented small retry/rate-limit wrapper and guarded redirects |
| Listing/metadata parsing | lxml and standard-library JSON/XML handling | Source pilot established Blogger microdata and article-container structure |
| Main article text | Trafilatura with a small site-specific fallback | Established body/metadata extraction; pilot determines actual quality |
| Schema | Pydantic | Explicit validated records and query plans |
| Entity extraction | Local GLiNER small-v2.1, explicit type vocabulary; spaCy linguistic analysis | Selected after measured entity errors in the initial spaCy-only baseline; source evidence retained |
| Embeddings | Sentence Transformers, one small English retrieval model | Local semantic retrieval without a per-query embedding API dependency |
| Vector storage | Chroma PersistentClient | Local persisted index, metadata, similarity queries, and article-level replacement |
| Structured operations | Load validated JSON records into Python | For 50–100 articles, a second database is unnecessary; complete filters/grouping remain transparent |
| CLI and tests | argparse and unittest | Implemented small surface area and focused behavioral tests |
| Answer synthesis | Deterministic structured operations and source excerpts | Chosen credential-free baseline; generative LLM adapter deferred, not simulated |

The initial functional baseline must run without a paid API key: deterministic extraction, entity recognition, extractive summaries, exact structured answers, and clearly labeled evidence excerpts. If an LLM is configured, it improves entity/funding extraction and prose synthesis using the same persisted evidence and validation. Missing credentials must not silently masquerade as a live generated answer. If the baseline performs poorly on funding/entity audits, improve it or use the configured LLM before claiming success; a fallback is not automatically submission quality.

Implemented model/dependency identities are pinned in requirements and local manifests. Documents and queries use the same local MiniLM encoder; incompatible indices are rejected. No paid provider or generative LLM is configured. A future optional prose model would require a separate verified adapter; it is not part of the current implementation.

Official documentation checked during planning:
- https://trafilatura.readthedocs.io/en/stable/extraction-overview.html
- https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html
- https://docs.trychroma.com/reference/python

## 3. Intended project layout

```text
README.md
PROJECT_LOG.md
PROJECT_PLAN.md
requirements.txt
.env.example
.gitignore
scrape.py
extract.py
index.py
query.py
newsrag/
  config.py
  models.py
  fetching.py
  extraction.py
  entities.py
  chunking.py
  vector_store.py
  query_planner.py
  query_engine.py
  llm.py
tests/
data/
  raw/                 # untouched response bodies
  manifest.jsonl       # URL, ID, fetch time, status, raw path, hash
  records/             # validated article JSON
  index/               # persisted vector database and index configuration
  samples/             # five matching raw HTML/JSON pairs for submission
logs/
results/
  sample_queries.md
  extraction_audit.md
  verification.md
```

Final module count follows actual complexity; do not create empty abstractions simply to match the diagram. Exclude secrets, virtual environments, model caches, transient logs, and derived vector files from version control. Commit the required article sample. Document how to regenerate the 50+ corpus; decide whether to include additional records after checking source reuse constraints and repository size. Do not claim all 50 raw pages must be committed: the stated submission sample is five.

## 4. Phase 0 — source and environment feasibility

1. Confirm actual deadline when available; the brief says five days but does not supply a calendar start.
2. Inspect machine/Python capacity and a clean project environment. Verify supported package versions together before committing to them.
3. Check candidate sites from the brief for current robots rules, access conditions, RSS/listing pagination, clean HTML, dates, and relevant content. Indian business/startup coverage is desirable for Bengaluru/funding queries, conditional on permitted access.
4. Fetch a small permitted pilot: approximately five representative pages spanning funding, general business/AI, and another category where available.
5. Inspect body extraction, canonical URL, publication time, author, entity and funding evidence. Reject unsuitable sources early rather than building around blocked/paywalled content.
6. Choose one source and record the reason, access policy, discovery method, and limitations. Then choose exact embedding/LLM settings based on pilot quality and available resources.

Exit gate: one permitted source with a workable route to 50+ useful articles, five inspectable pages, and a viable local dependency/model setup. If no candidate passes, report the concrete blocker before committing to an unsuitable source.

## 5. Phase 1 — scrape and preserve

1. Discover article URLs from RSS and/or listing pages; constrain to the chosen section/site.
2. Normalize conservatively, remove obvious tracking parameters, deduplicate, and generate stable URL-based IDs. Preserve original/canonical URL relationships; avoid merging genuinely distinct pages.
3. Check robots and apply a descriptive user agent, configurable delay (initially about two seconds, increased if policy requires), timeouts, bounded retries, and backoff. Respect server retry instructions; do not repeatedly retry access denial.
4. Save response body bytes unchanged for successful article fetches. Record fetch timestamp in UTC, status, URL, file path, and content hash in a manifest. Record failed requests separately with reason and attempt information.
5. On rerun, skip successful saved pages with valid artifacts; retry only appropriate failures/missing files. Use an explicit refresh option if a page must be fetched again.
6. Collect beyond the minimum if necessary, targeting roughly 60–80 candidate articles so extraction failures do not leave fewer than 50 accepted records. Corpus size and coverage are measured, not assumed.

Exit gate: at least 50 usable raw article pages eventually available; no duplicate successful IDs; a rerun skips them; one failed URL does not stop the batch. Discovery, raw saving, and extraction remain separate operations.

## 6. Phase 2 — structured extraction and audit

1. Read saved HTML only; no network requirement for extraction.
2. Prefer article JSON-LD and trustworthy metadata for canonical URL, title, author, and publication time; clean body with the body extractor. Keep original date evidence and distinguish publication, modification, and fetch time.
3. Normalize times to UTC. If a date has no timezone, use a documented site policy with provenance. Date-only inputs retain precision information. Missing/unreliable mandatory dates go to a logged review/quarantine path rather than using fetch time as publication time.
4. Extract organizations, people, locations, category, and a 2–3 sentence summary. Use controlled category labels including an unknown/other case. Preserve display names separately from normalized matching keys. Treat aliases such as Bengaluru/Bangalore explicitly.
5. Extract funding only when the article describes a raise. Store amount as a precise value/string, currency, reported units/text, round, investors, funded company, and supporting body passages. Unknown subfields remain null/empty; the funding object is null when not applicable. Never confuse valuation, revenue, cumulative funding, or another company's raise with the current raise.
6. Validate required fields and additional provenance with Pydantic. Log schema failures separately from factual warnings. Cache any model-assisted extraction by content hash, model, and prompt version so reruns need not repeat unchanged calls.
7. Write accepted JSON atomically, including extraction version/content hash. Index only accepted current records. Flag changed/quarantined records so stale prior versions are not accidentally treated as current.
8. Manually audit about 10–15 diverse records against HTML/body evidence, including multiple funding articles and difficult cases. Track field completeness and checked-field correctness separately. Review critical funding/date errors before moving on; document sample size and limits, without claiming population accuracy from a tiny audit.

Exit gate: 50+ accepted records, all mandatory schema fields, clean bodies, supported summaries, and a documented audit. Preserve five matched HTML/JSON sample pairs.

## 7. Phase 3 — chunk, embed, persist

1. Split body text on paragraph/sentence boundaries, with a tokenizer-aware maximum below the chosen model's input limit. Initial target: about 200 tokens and 30-token overlap if the selected model supports it; tune after pilot retrieval. Do not silently truncate long chunks.
2. Retain article ID, chunk order, title, URL, publication timestamp, category, and normalized filter information. Use supported Chroma metadata types; keep rich nested funding/entity structures in JSON. Resolve complex filters over records and constrain vector candidates by eligible article IDs if necessary.
3. Encode chunks with the configured document encoder and questions with its matching query encoder. Persist vectors locally, recording model identity/revision, chunking settings, and extraction fingerprint.
4. For a changed article, prepare/validate replacement chunks before replacing its index entries; remove all obsolete chunks, not just overwrite matching IDs. Log interrupted/failed updates and make rerunning repair them; do not claim multi-step operations are transactional without implementing that guarantee.
5. Verify unchanged reruns do not increase counts, shorter replacement articles leave no old tail chunks, and query results survive process restart.

Exit gate: real semantic retrieval works on paraphrases; index is persistent and reproducibly rebuildable; reruns have no duplicate/stale chunks.

## 8. Phase 4 — query planning and execution

Use an explicit query plan with intent, entity/location/category filters, time range, optional article target, and whether a complete result set is needed. Keep a deterministic baseline and explicit CLI filter flags; optionally use the LLM to interpret varied language into this validated plan. Never execute model-produced code or SQL. When an important ambiguous condition cannot be resolved, expose the assumption or request clarification instead of silently fabricating a filter.

Time policy: use a captured UTC reference instant per run; expose `--as-of` for reproducible evaluation. Last seven days is a rolling window; this month is the current calendar month through that instant. Proposed default for vague recent/recently: last 30 days, stated in the answer and overridable. A reproduced sample with a frozen time must visibly say so; ordinary live queries use current time. All answers are explicitly limited to the collected corpus.

| Query | Execution plan |
| --- | --- |
| AI stories | Semantic search, remove repeated chunks from the same article, synthesize main themes from relevant articles |
| Funding last seven days | Filter complete records by publication time and funding/category; report company, supported amount/currency, round, investors, URLs; explain that publication date need not equal transaction date |
| Company announcements | Normalize company alias, restrict records by company and recency, retrieve relevant announcement evidence |
| All Bengaluru articles | Filter every accepted record using normalized locations and an article-body mention check; return all matches/count, paginate display if needed without changing completeness; audit NER misses |
| Layoffs this month | Filter category/time over all records; summarize evidence across every match or use explicit per-article intermediate summaries if context is too large |
| Repeat investors | Group normalized investor names over distinct evidenced funding rounds; link each round's sources; mark ambiguous round matches instead of silently double counting |
| Revenue in named article | Resolve exact/normalized title, show ambiguity when multiple matches, constrain retrieval to the chosen article; preserve units/currency and distinguish revenue from valuation |
| Mumbai weather | Detect absence of supported evidence and decline; do not fetch live weather |

Funding round identity uses funded company, round label, event-date evidence and contextual amounts as available. Do not assume each article is a distinct round or that identical amounts always indicate one round. Preserve ambiguity in outputs where records cannot resolve it.

Answer contract: answer, evidence/source URLs, interpreted filters/reference time, and material gaps. Structured lists/counts are computed by code. LLM prose uses only selected passages/verified fields, cites sources, and treats article text as evidence rather than instructions. Check source IDs/URLs and numerical consistency; recognize these checks do not prove full semantic support. Evaluate refusals with unsupported and merely keyword-overlapping questions, rather than rely on a universal similarity cutoff.

Exit gate: all eight sample types run with paraphrase variants, truthful empty-result behavior, complete record operations, and traceable sources.

## 9. Phase 5 — tests and honest evaluation

Focused behavioral checks:
- Robots disallow, retry/backoff, timeout, failure isolation, successful-download skip, raw byte preservation.
- Clean extraction fixture, missing metadata, invalid schema, timezone/date boundaries, amount/currency/unit distinction, alias normalization.
- Persisted index restart, stable counts on rerun, old-chunk removal after replacement, changed embedding configuration rejection.
- Complete location lists beyond top-k, repeated-investor aggregation without repeated-round inflation, company/date/category filters, article-specific revenue, supported refusal.
- No credential mode and configured-model error handling. Live model behavior is verified separately from stubs and labeled honestly.

Run actual saved-corpus queries, inspect answers against evidence, and write `results/sample_queries.md`: exact question, run/reference time, answer, article URLs, one-line correctness judgment and any caveat. For query 7, choose a real title with relevant revenue evidence if available; otherwise report lack of evidence honestly. Add a few held-out paraphrases and negative questions. Keep observed outcomes, failures, and fixes in the log; never hand-write successful outputs as if produced by code.

Exit gate: appropriate tests pass, real eight-query evidence is saved, and known limitations are explicitly described. New failures trigger fixes and relevant rechecks.

## 10. Phase 6 — reproducibility, documentation, submission

1. Test setup in a fresh environment with documented model downloads and optional keys. Aim for 6–8 setup/run commands, fewer than the assignment's limit of 10.
2. README: chosen source and access policy; four commands; data flow; extraction rationale; chunk/model decisions; complete-query handling; time definitions; measured audit; limitations; one-more-week priorities.
3. Verify `.env.example`, ignore rules, dependency versions, five sample pairs, and actual query outputs. Keep keys out of all artifacts and the recording.
4. Prepare a 3–5 minute recording: explain architecture; show a real pipeline run or transparently identify saved-stage outputs; demonstrate rerun skipping, semantic query, structured filter/aggregation, source evidence, refusal. Label cuts/time compression; do not imply cached outputs are newly fetched. Model downloads/setup should be completed beforehand.
5. Prepare interview notes covering each function, schema, chunking trade-off, semantic vs exact operations, extraction limitations, retries, persistence, and a small practiced change such as adding a category/filter.
6. Final repository and recording review. Current user-authorized work has advanced from planning to implementation and local delivery verification. Finish verification and packaging, then the real demo, then GitHub/submission, as clarified by the user. Repository preference is public under chetan14806; do not treat a prepared archive or walkthrough as completed publication or recording.

Exit gate: a reviewer can follow README in under ten commands, reproduce the outputs, inspect evidence, and understand the code and limitations.

## 11. Sequence and time budget

| Day slot | Work | Approximate focused effort |
| --- | --- | --- |
| 1 | Source/environment pilot, schema contract, scraper | 3–4 hours |
| 2 | Extraction, normalization, manual audit | 4–6 hours |
| 3 | Embeddings/index, query planning/operations | 4–6 hours |
| 4 | Query evaluation, tests, corrections | 3–5 hours |
| 5 | Clean setup, README, recording, interview notes | 2–3 hours |

Total planning range: about 16–24 hours. Day slots describe order, not calendar deadlines; actual due date remains unknown. Source accessibility, local model setup, and extraction quality are the largest uncertainties. If time is tight, cut optional interface and tooling before cutting mandatory query behavior, extraction review, or setup verification.

## 12. Change control and logging

Current delivery handoff (2026-10-18): the four pipeline stages and fresh-environment verification are complete; follow DELIVERY_CHECKLIST.md for packaging/demo/repository status. Repository destination is chetan14806, public; recommended name news-rag-pipeline. Local main branch exists; the user will record their own demo before repository delivery. README contains nine primary setup commands. Reusing saved raw inputs/model downloads is explicitly distinguished from a new live scrape or new model download.

At each phase record what was attempted, what changed, why, evidence of success/failure, unresolved limits, and next actions in PROJECT_LOG.md. Maintain this plan as decisions become concrete; label deviations and their reason. Source/model choices become final after the pilot, rather than pretending unknown constraints are already resolved.

Definition of done: 50+ real accepted articles; original HTML retained; four independent persistent stages; idempotent downloads/indexing; validated and audited records; actual vector retrieval plus complete filters/aggregation; grounded sources/refusal; eight recorded query results; reproducible setup; required sample pairs; documentation; recorded demo; understandable code for interview.

## 13. Source checkpoint outcome — 2026-10-17

Selected IndianWeb2 for the development corpus after current robots/access checks and five-page HTML/metadata/body extraction verification. Public RSS exposes 100 distinct candidate URLs with relevant Indian funding, AI, revenue and Bengaluru coverage. General extraction lost substantive spans on some pages; verified a narrow Blogger post-body fallback. TechNode is a tested technical backup, not an additional corpus source. See SOURCE_SELECTION.md for evidence, limitations, candidate comparisons and the unresolved public sample redistribution question. This source checkpoint led to the production scraper below; the pilot is not a full-schema extraction stage.

## 14. Production scraper checkpoint outcome — 2026-10-17

Completed the ordered SCRAPER_CHECKLIST.md. Scraper CLI, source scope, access/pacing/retry handling, atomic raw/manifest storage and integrity-aware reruns are implemented. Final automated suite: 19 passing tests. A five-page live gate preceded an 80-page collection. An incremental rerun discovered one new eligible article, resulting in 81 raw originals. Final rerun skipped all 81 with zero article downloads, unchanged manifest bytes and unchanged raw-file modification times/hashes. Offline integrity and article-structure checks pass for 81/81. Full results and limits: results/scraper_verification.md.

Independent review subsequently reproduced two open scraper gaps: final redirect aliases can inflate counts, and publisher cooldown is not persisted across restarts. The current 81-page corpus has no duplicate final URLs and encountered no live throttling; all 19 existing tests still pass. See results/PROJECT_REVIEW.md and results/review_probe_results.json. Close these findings with regression tests before describing the scraper as fully hardened.

Follow-up: both findings are now fixed, with 24 tests passing and post-fix synthetic evidence in results/scraper_hardening_verification.json. Redirect aliases retain the original saved ID/provenance, while unique final destinations determine readiness. Source cooldown is checked before any restarted network request. Offline re-audit confirms all existing 81 artifacts remain valid without migration or new downloads. The next checkpoint is extraction.

Then proceed to full extraction: finalize required schema and provenance/missing-field policies, implement/verify one article and the representative five-page set, then process all 81 originals with validation/error logs and a manual accuracy audit. At least 50 accurate accepted records are still required. No full extraction, embeddings, query results or final submission is claimed complete. The learning sequence and official resources are in LEARNING_PATH.md.

## 15. Extraction implementation — 2026-10-17

Independent extract.py and persistent schema/provenance/quarantine contracts are implemented. Circle preceded a five-page pilot check, then full-corpus processing. Initial model-only entity errors were measured and preserved; type-aware local GLiNER was selected after comparison. Setup pins its revision, saves safetensors/tokenizer/config locally with checksums, and requires local-only loading for extraction. Bounded overlapping windows retain source offsets. spaCy still supplies linguistic/sentence analysis. Summaries use 2–3 verbatim source sentences; no paid key or generative API is needed.

Financial rules cover venture raises, strategic investments, NCD/bond debt and committed financial support, with amounts/currency/stage/investors/status and source evidence. Unknown amounts remain null; valuation/fund sizes/sales are not substituted. Current support does not inherit historical equity-round stage/investors. Investor lists and entities are explicitly not guaranteed exhaustive.

Final tests: 39 passing. Final v2.0.2 produced 81 records with zero failures; saved-output audit verifies all 81 and 1,431 long body spans. The 18-article financial development review passes 91 declared checks. Entity review finds two incorrect fragments among 147 display strings across 10 articles, with known omissions and unmeasured recall; this is not held-out accuracy. Offline rerun skips all 81 with unchanged record bytes/mtimes and zero network attempts. Five matching HTML/JSON pairs are retained locally. Results are recorded in results/extraction_audit.md and PROJECT_LOG.md.

At the extraction handoff, indexing was the next checkpoint; its completed outcome is recorded in section 16. Future exact filters must validate source body/event evidence and handle unresolved ambiguity rather than assuming all model labels are true. Clean-machine setup, sample sharing review, eight actual query evaluations, repository and demo remain final deliverables.

## 16. Persistent indexing — 2026-10-17

Implemented independent index.py with local MiniLM embeddings and persistent Chroma, source-preserving bounded chunks, scalar filter metadata, source/record/model integrity checks and recoverable updates. Configuration changes require a separate index directory; incomplete/stale indexes cannot serve search. Obsolete article tails and unaccepted entries are removed. Shared locking and validation prioritize correctness at this small corpus size; full validation per search is not a scalable serving design.

Nine indexing lifecycle tests pass with real Chroma and explicitly fake embeddings, bringing the suite to 48 tests. Five-article real-model pilot: 40 chunks, all ten declared retrieval probes ranked the intended article first. Full corpus: 81 articles / 484 real 384-dimensional chunks, complete source-span coverage and verified persisted vectors/metadata. Full offline rerun skips all 81 without embedding/vector changes; separate-process results and distances match exactly. Isolated real-model replacement deletes six obsolete tail chunks. Full-corpus retrieval: ten of ten probes find the intended article within the first five distinct articles deduplicated from ten chunks (nine first, one second). These are development probes, not broad retrieval accuracy. Follow INDEXING_CHECKLIST.md and results/indexing_verification.md.

Next checkpoint: grounded query planning and execution. Diagnostic tools/search_index.py already returns evidence chunks, not final answers. Implement explicit intents/filters, complete structured lists and aggregation, event/date/distinct-round interpretation, relevant neighboring/source-record evidence, source citations and unsupported-question refusal. Then run and save the eight actual assignment queries and paraphrase/negative checks. Finding the right article does not ensure the top chunk alone contains the requested financial fact. Keep extraction uncertainty explicit.

## 17. Grounded query checkpoint — 2026-10-17

Implemented independent query.py, validated intent/time/filter plans and deterministic structured/extractive answers. Full-record operations supply exhaustive city mentions, funding/date filtering and investor aggregation; eligible-ID vector retrieval supplies AI/company overviews and article-specific retrieval. Revenue also checks complete source passages to avoid top-k omissions. Exact evidence spans/URLs, interpreted time windows and limitations persist with each answer. No generative LLM/provider is configured or required.

Final suite: 62 passing tests. Actual offline evaluation runs the eight required families, eight paraphrases and four negatives, with zero network attempts and matching evidence/URL checks. At frozen 2026-10-17T12:00:00Z, results include 14 city articles, three reported weekly venture announcements plus one closing round, two contextual layoff publications without an established new monthly event, and no repeated investor established across nine eligible reports/23 named investors. Revenue is sourced to Vishakha Renewables' FY26 figure; Mumbai weather is refused. Outputs and digest-bound agent source-review judgments are saved in results/sample_queries.md, query_evaluation.json and query_source_review.json. Limits are explicit in results/query_verification.md; tests do not imply unrestricted language or population accuracy.

Next checkpoint: submission readiness. Verify clean-machine installation and setup under ten commands; review sample sharing basis and package five matched HTML/JSON pairs; check repository hygiene; prepare the required repository delivery and 3–5 minute demo. Do not call the overall assignment delivered until these gates pass. Continue preserving the local originals, known extraction/query limitations and truthful empty results.
