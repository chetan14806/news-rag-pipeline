# News RAG Pipeline

A persistent news pipeline for the Zylabs coding assignment. Four independent commands collect real articles from [IndianWeb2](https://www.indianweb2.com/), extract structured records, build a local vector index, and answer questions with source URLs.

The verified development snapshot contains **84 articles and 497 chunks**. Answers combine semantic retrieval, complete-record filtering and deterministic source excerpts. No generative LLM or API key is required.

## Setup and run

Prerequisite: **Python 3.12**, internet access for installation/model downloads, and several GB of disk space. From the repository root, these **nine commands** install dependencies and run all four stages on Windows:

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

The scraper intentionally waits at least six seconds between requests; collecting 80 pages normally takes eight minutes or more. Dependency installation and the first model downloads/extraction also take time. Each stage saves its output, so subsequent commands do not rerun earlier stages. Models load locally after setup.

On Linux/macOS, use `python3.12` and `.venv/bin/python` in place of the Windows executable paths; these operating systems have not been tested. Python 3.12 on Windows was used for verification. A separate environment on the same host reproduced the records and answers using saved HTML and existing model assets; this was not a fresh scrape or another-machine test.

## Repository contents

```text
scrape.py / extract.py / index.py / query.py   independent stage entry points
newsrag/                                    implementation and schemas
tools/                                      the two model setup commands
tests/                                      automated regression tests
samples/raw/ + samples/records/              five original HTML / extracted JSON pairs
samples/*manifest.json                      fixture provenance and checksums
results/sample_queries.md                   eight required answers, URLs and judgments
```

The full corpus, model weights, vector database and local environments are generated under `data/` and excluded from Git. The five included pairs are inspection fixtures, not the full 50+ article corpus. See [sample details](samples/README.md) and [third-party attribution](THIRD_PARTY_NOTICES.md).

## Design and trade-offs

| Stage | Method | Persistence and trade-off |
| --- | --- | --- |
| Scrape | IndianWeb2's public RSS feed discovers dated technology/business/startup pages. Robots rules, redirects, sequential delays, bounded retries and server cooldowns are enforced. | Original response bytes, URL/fetch metadata and SHA-256 hashes go into `data/raw/` and `data/manifest.json`; failures and request attempts are logged. Valid existing pages are verified and skipped. Discovery is limited to the latest 100 feed entries; an insufficient eligible set is reported as a shortfall. |
| Extract | Trafilatura plus a checked article-container fallback cleans the body. Source metadata supplies dates/bylines; spaCy and local GLiNER identify entities. Financial rules retain amounts, round, investors and supporting spans. Summaries select 2–3 source sentences. | Validated records go into `data/records/` with an extraction manifest, provenance and error log. Unchanged raw/model/extractor fingerprints skip work. Missing mandatory metadata or invalid raw bytes quarantine a record. Local extraction avoids credentials but is slower and can miss or mistype entities. |
| Index | `sentence-transformers/all-MiniLM-L6-v2`, pinned to a fixed revision, produces normalized 384-dimensional embeddings. Chroma persists a cosine index. | `data/index/` stores the database, manifest and run reports. Unchanged records skip embedding/vector writes; changed records replace chunks, and obsolete records are removed. Incomplete/stale state is rejected and an interrupted update is repaired by rerunning. |
| Query | Real vector retrieval selects relevant AI/company stories. Complete structured/body scans handle exhaustive locations, publication dates, funding, layoffs and investor aggregation. Revenue lookup inspects the selected article's full text. | Answers, sources, evidence offsets and plans go into `data/queries/`. Extractive answers avoid invented prose but have limited synthesis and natural-language coverage. Unsupported questions, including live weather, are refused. |

IndianWeb2 was selected because it provides real technology/business/startup coverage, a public RSS feed and article publication metadata. Source labels guide collection; they are not assumed to be accurate extracted categories. All requests, including retries and redirects, pass through the same rate limiter and policy checks.

### Extraction and chunking choices

Local **spaCy `en_core_web_md` 3.8.0** supplies linguistic/sentence analysis; **GLiNER `urchade/gliner_small-v2.1`** supplies company/organization/person/location predictions. Setup pins model revisions and records asset hashes. Rule corrections disambiguate institutions/platforms and financial expressions; unknown financial values remain null. Funding preserves reported/closing/committed status and distinguishes venture funding from debt, strategic investments and financial support. Amounts use exact decimal strings; no currency conversion is inferred.

Extractor 2.0.8 retains the financing-deal checks: the word "deal" alone neither establishes nor excludes funding. Contract/order headlines and services-deal leads remain excluded, including when a later passage mentions historical funding. Changed extractor versions invalidate cached records; rerun extraction and indexing after updating.

When the headline has no usable raise amount, a conservative fallback checks for an explicit amount directly raised by the named recipient in the lead evidence. It preserves source units/currency and amount text. Valuations, historical/cumulative figures, future plans, other companies, investor fund sizes and revenue are not substituted. Conflicting amounts, currency equivalents, approximate quantities and indirect wording can remain unknown. A conflicting explicit headline amount is not silently overwritten.

Chunks preserve source character offsets, prefer sentence/paragraph boundaries, and contain at most **200 wordpieces**, with approximately **30 wordpieces overlap**. This retains context while staying below the encoder's 256-token input limit, including special tokens. Metadata stores title, URL, article ID, publication time, category and record hash. Titles are metadata rather than duplicated embedding text. Mean pooling uses the attention mask and L2 normalization; questions and document chunks use the same encoder. Oversized questions fail explicitly rather than being silently truncated.

### Query behavior

```powershell
.venv\Scripts\python.exe query.py "Which startups raised funding in the last 7 days, and how much?" --as-of 2026-10-17T12:00:00Z
.venv\Scripts\python.exe query.py "Recent announcements" --intent company --company ServiceNow
.venv\Scripts\python.exe query.py "List all articles that mention Bengaluru."
.venv\Scripts\python.exe query.py "What is the weather in Mumbai today?"
```

Read [all eight sample answers](results/sample_queries.md). They use the collected 84-article snapshot and a frozen reference time of **2026-10-17T12:00:00Z**. A fresh scrape or later reference time can change the results. The normal default is the current UTC instant.

- `--as-of`, `--since` and exclusive `--before` accept timezone-bearing ISO timestamps. Windows filter **publication dates**, not transaction dates. Last seven days is rolling; this month is a UTC calendar window; recent means 30 days. Explicit years and this/last/previous year use UTC calendar-year bounds. Unimplemented date expressions (such as named months, quarters or yesterday) ask for clarification instead of substituting a recent window. Explicit `--since`/`--before` replace inferred date bounds as a pair, with the reference-time cap retained.
- Company/location/title ambiguity can be resolved with `--intent`, `--company`, `--location` and `--title`. `--json` includes exact source evidence and retrieval traces. Run any stage with `--help` for its options.
- Explicit place phrases also constrain funding, AI, company and layoff operations through body mentions. This does not establish headquarters or event location. Recognized negative/exclusion requests and inferred multiple-location AND/OR expressions ask for clarification; use separate positive queries or one explicit `--location`.
- Every inferred operation is selected semantically: the local MiniLM encoder represents the entire question, then a regularized linear classifier selects one of seven operations or an unsupported request. The keyword-first routing chain has been removed. Only explicit `--intent` bypasses classification. Without a semantic provider, the planner clarifies rather than restoring keyword routing. No generative model, hosted embedding API or per-query API charge is involved.
- The classifier is fitted locally from labeled operation examples, with ridge regularization 0.3. Acceptance requires a score of at least 0.30 and a margin of at least 0.05; a competing unsupported-request score of 0.38 also causes abstention. Scores are uncalibrated classifier outputs, **not probabilities or cosine similarities**. Known names and quoted titles are masked for scoring; operation examples do not store answers or article membership. The small in-memory classifier is separate from the persistent Chroma article index. `--json` exposes the normalized question, all operation scores and abstention reason.
- After semantic selection, the planner independently binds known company/place names from accepted corpus records and validates title, date, Boolean and count constraints. Rules still parse these slots and enforce supported execution; they do not choose the operation. Unknown targets and unfamiliar date expressions may require explicit flags. A parsed count records its unit, comparison and value: "exactly one funding round" becomes `rounds / eq / 1` and requests clarification because that calculation is not implemented. It cannot silently become a funding list or a repeated-investor calculation. Unsupported temporal units also clarify instead of silently applying a default window.
- Ambiguous "earnings" requests ask whether you mean revenue or profit. Investor requests for distinct-company counts, exact counts or higher thresholds do not silently reuse the more-than-one-round calculation; they request clarification. Rephrase using the supported operation or use explicit flags when appropriate.
- Count phrases such as "a lone funding round", "a single funding round" and "just one funding round" mean exactly one and request clarification. They do not become location filters. An actual place later in the question is preserved; no exact-one request silently becomes a more-than-one calculation.
- Bengaluru/Bangalore checks every accepted article body, including names missed by entity extraction. AI/company overviews show a relevance-ranked selection of up to five articles. AI eligibility checks body text as well as titles/categories; incidental mentions may qualify, and implicit references can still be missed.
- Funding lists reported startup venture announcements and distinguishes closing/committed rounds. Investor aggregation conservatively normalizes aliases and avoids counting ambiguous reports of the same company/round twice. Distinct funds under a parent remain distinct.
- Funding questions can filter one exact stage, such as seed, pre-seed or Series A. Seed and pre-seed are distinct; unknown stages are disclosed and excluded from confirmed matches. Multiple stages, monetary thresholds/currency conditions and investor/lead-investor filters request clarification rather than returning an unrestricted list. These checks also protect investor aggregation; an investor's participation is not proof they led a round.
- Layoff answers bind timing and certainty to the layoff clause, preserving historical, conditional/negated/speculative and unresolved mentions. Direct cuts with explicit relative timing are recognized; conflicting passages remain unresolved. Revenue answers require a direct revenue/sales/turnover-to-value relationship, preserve periods and forecasts, and retain complete table headers; funding/profit/valuation do not substitute for revenue.
- Extraction records pending and quarantined raw IDs. A limited run that leaves new pages unprocessed is incomplete; finish extraction before indexing/querying. After collection changes, rerun extraction and indexing. Debt/loan financing and ongoing or explicitly unclosed rounds are excluded from completed venture counts.

All stages accept `--data-dir PATH`; model setup must use that same directory. Index/query also accept `--index-dir PATH`. Querying requires a complete current index, not an arbitrary subset. `--refresh` deliberately re-fetches raw pages; ordinary runs verify and skip them. Concurrent writers must not share one data directory.

## Validation and limitations

Run the regression suite after setup:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The current suite passes **177 tests** after the entity-ambiguity, funding-constraint, funding-deal, count-wording, body-amount, revenue-evidence and layoff-context repairs. Exact funding stages execute; unsupported amount and investor filters clarify. The corpus remains **84 records / 497 chunks**; extractor 2.0.8 refreshed record provenance and index metadata while retaining article facts. The offline rebuild and checks observed zero network attempts. The earlier semantic checkpoint passed 130 tests, retained the eight sample statuses/article sets, passed 13 constraint/real-corpus controls, and selected the intended operation in 24/24 separate questions. Across its 128 semantic benchmark questions, every execution used the requested operation or refused/clarified; supported-language refusals are not counted as intent understanding. See [semantic evaluation and limits](results/semantic_query_validation.md) for those historical metrics, development reuse and exact scope. The earlier 94-case extraction/query repair replay and ten retrieval probes remain evidence for their checkpoints.

Earlier pipeline verification reproduced 81 byte-identical extracted records across two local environments and checked ten retrieval probes. Financial extraction was checked against 91 declared checks across 18 development articles. Sample pairs retain exact original bytes and checksums. These are development/regression checks, not held-out accuracy estimates; source/output judgments were agent-reviewed, not independently human-annotated. The latest replay reused local models and saved articles on the same Windows host; it was not a fresh installation or crawl.

Accuracy is assessed by checking extracted fields against source text, validating exact evidence spans and manually reviewing sample answers for support. Exhaustive location results are also compared against an independent full-body scan rather than semantic top-k. Entity recall is not exhaustively measured, and fixing known errors does not establish perfect extraction.

Known limitations:

- Entity recognition can omit names or confuse products/facilities with organizations. Financial rules can miss implicit funding details or incomplete investor rosters; coarse categories are not event classifiers.
- Semantic operation recognition is primary, while entity/date/count binding remains bounded. The classifier can still abstain or select the wrong operation for unfamiliar language; the labeled examples and thresholds do not establish unrestricted understanding. Explicit flags resolve uncertain targets/operations. Article eligibility, financial/event extraction and extractive synthesis retain documented rules. Extractive summaries provide less fluent multi-article synthesis than a generative model.
- Publication-window matches do not prove an event occurred during that window. Layoff timing and funding-round deduplication remain conservative and may undercount.
- RSS coverage is bounded; publisher markup, labels and access rules can change. Publisher claims are not independently fact-checked.
- Query-time integrity checks recheck records, raw hashes and vectors. This is useful for a small assignment corpus but adds startup/response latency and needs a snapshot design at service scale.

With another week, I would add tested archive pagination, a larger independently annotated extraction/query evaluation set, stronger entity/round resolution, conditional refresh with ETag/Last-Modified, and a validated query snapshot to reduce repeated integrity work.

## Demo

The narrated screen recording has been recorded; its link will be added here when available.
