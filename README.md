# News RAG Pipeline

A persistent news pipeline for the Zylabs coding assignment. Four independent commands collect real articles from [IndianWeb2](https://www.indianweb2.com/), extract structured records, build a local vector index, and answer questions with source URLs.

The verified development snapshot contains **81 articles and 484 chunks**. Answers combine semantic retrieval, complete-record filtering and deterministic source excerpts. No generative LLM or API key is required.

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

Chunks preserve source character offsets, prefer sentence/paragraph boundaries, and contain at most **200 wordpieces**, with approximately **30 wordpieces overlap**. This retains context while staying below the encoder's 256-token input limit, including special tokens. Metadata stores title, URL, article ID, publication time, category and record hash. Titles are metadata rather than duplicated embedding text. Mean pooling uses the attention mask and L2 normalization; questions and document chunks use the same encoder. Oversized questions fail explicitly rather than being silently truncated.

### Query behavior

```powershell
.venv\Scripts\python.exe query.py "Which startups raised funding in the last 7 days, and how much?" --as-of 2026-10-17T12:00:00Z
.venv\Scripts\python.exe query.py "Recent announcements" --intent company --company ServiceNow
.venv\Scripts\python.exe query.py "List all articles that mention Bengaluru."
.venv\Scripts\python.exe query.py "What is the weather in Mumbai today?"
```

Read [all eight sample answers](results/sample_queries.md). They use the collected 81-article snapshot and a frozen reference time of **2026-10-17T12:00:00Z**. A fresh scrape or later reference time can change the results. The normal default is the current UTC instant.

- `--as-of`, `--since` and exclusive `--before` accept timezone-bearing ISO timestamps. Windows filter **publication dates**, not transaction dates. Last seven days is rolling; this month is a UTC calendar window; recent means 30 days. Explicit `--since`/`--before` replace inferred date bounds as a pair, with the reference-time cap retained.
- Company/location/title ambiguity can be resolved with `--intent`, `--company`, `--location` and `--title`. `--json` includes exact source evidence and retrieval traces. Run any stage with `--help` for its options.
- Related phrases share routing rules: for example, "secured investment" selects funding, "workforce reductions" selects layoffs, and "ServiceNow's latest product launches" selects company announcements. Company/place names and date windows are extracted separately; they are not restricted to the sample values. This remains a bounded rule-based interface, not unrestricted language understanding.
- Ambiguous "earnings" requests ask whether you mean revenue or profit. Investor requests for distinct-company counts, exact counts or higher thresholds do not silently reuse the more-than-one-round calculation; they request clarification. Rephrase using the supported operation or use explicit flags when appropriate.
- Bengaluru/Bangalore checks every accepted article body, including names missed by entity extraction. AI/company overviews show a relevance-ranked selection of up to five articles.
- Funding lists reported startup venture announcements and distinguishes closing/committed rounds. Investor aggregation conservatively normalizes aliases and avoids counting ambiguous reports of the same company/round twice. Distinct funds under a parent remain distinct.
- Layoff answers separate historical, conditional/negated/speculative and unresolved event timing. Revenue answers preserve period, forecasts and table context; funding/profit/valuation do not substitute for revenue.

All stages accept `--data-dir PATH`; model setup must use that same directory. Index/query also accept `--index-dir PATH`. Querying requires a complete current index, not an arbitrary subset. `--refresh` deliberately re-fetches raw pages; ordinary runs verify and skip them. Concurrent writers must not share one data directory.

## Validation and limitations

Run the regression suite after setup:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The current regression suite passes **89 tests**, including additional paraphrase, entity-target, date-window, operation-precedence and ambiguity checks. Earlier pipeline verification reproduced **81 byte-identical extracted records** across two local environments and checked **484 persisted chunks**, ten retrieval probes and 25 query cases. A focused real-data replay also passes 62 query cases, including the original 25 checks and 37 additional paraphrase/clarification checks; all eight original sample answer payloads remain unchanged. The eight required answers include source URLs and correctness judgments in the sample report. Financial extraction was checked against 91 declared checks across 18 development articles. Sample pairs retain exact original bytes and checksums. These are development/regression checks, not held-out accuracy estimates; source/output judgments were agent-reviewed, not independently human-annotated.

Accuracy is assessed by checking extracted fields against source text, validating exact evidence spans and manually reviewing sample answers for support. Exhaustive location results are also compared against an independent full-body scan rather than semantic top-k. Entity recall is not exhaustively measured, and fixing known errors does not establish perfect extraction.

Known limitations:

- Entity recognition can omit names or confuse products/facilities with organizations. Financial rules can miss implicit funding details or incomplete investor rosters; coarse categories are not event classifiers.
- Natural-language parsing covers bounded patterns, with explicit flags available for other wording. Extractive summaries favor lead sentences and provide less fluent multi-article synthesis than a generative model.
- Publication-window matches do not prove an event occurred during that window. Layoff timing and funding-round deduplication remain conservative and may undercount.
- RSS coverage is bounded; publisher markup, labels and access rules can change. Publisher claims are not independently fact-checked.
- Query-time integrity checks recheck records, raw hashes and vectors. This is useful for a small assignment corpus but adds startup/response latency and needs a snapshot design at service scale.

With another week, I would add tested archive pagination, a larger independently annotated extraction/query evaluation set, stronger entity/round resolution, conditional refresh with ETag/Last-Modified, and a validated query snapshot to reduce repeated integrity work.

## Demo

The narrated screen recording has been recorded; its link will be added here when available.
