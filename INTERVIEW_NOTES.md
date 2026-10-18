# Explain and defend the implementation

Use these as prompts for your own explanation, not a script to memorize. The README describes setup; PROJECT_LOG.md records how decisions changed.

## Trace one article

1. `newsrag/scraper.py: collect` discovers an eligible URL, respects robots/pacing, and saves original HTML plus its manifest entry. Hashes detect damaged files; URL normalization and redirect identity prevent duplicate counting.
2. `newsrag/extraction_runner.py: run_extraction` reads verified HTML, obtains the article body, runs local extraction, validates the schema, and stores accepted records or errors. A valid schema does not prove that every extracted entity is correct.
3. `newsrag/indexing.py: run_index` validates accepted inputs, chunks body text, computes real embeddings, and stores vectors plus source metadata in persistent Chroma. Changed source/model configuration cannot silently reuse stale vectors.
4. `newsrag/query_engine.py: QueryEngine` validates the stored index and plans an answer. `answer_records` uses exact operations for exhaustive lists/aggregations and retrieval for semantic selection. Evidence links back to exact body spans and source URLs.

## Questions to practice

| Question | Key points to explain |
| --- | --- |
| Why store original HTML? | Re-extract without refetching, inspect errors, preserve provenance, verify integrity. |
| Why GLiNER plus spaCy? | Development review exposed baseline entity mistakes; GLiNER adds type-aware entities and spaCy supplies linguistic/sentence analysis. Errors and omissions remain. |
| Why overlapping chunks? | Bounded model input and context around boundaries; overlap trades storage/repetition for context retention. Explain the actual 200-token body budget and 30-token overlap. |
| Why MiniLM? | Local CPU inference, small 384-dimensional vectors and no API credentials; actual retrieval probes establish limited evidence of relevance. |
| Why not use vector search for every question? | Top-k cannot guarantee all Bengaluru mentions or complete investor counts. Structured/body scans cover all eligible records. |
| What makes the answers grounded? | Accepted records, exact evidence spans, explicit filters/time bounds, source URLs, and refusal when evidence or supported intent is absent. Publisher truth itself is not verified. |
| Why no generative LLM? | The brief permits it. Deterministic/extractive answers avoid a provider dependency, while language coverage and fluency are limited. |
| What does “last seven days” mean? | Rolling UTC publication window relative to the query clock; publication time does not establish the financing/event date. |
| What happens after interruption? | Atomic file writes, manifests and incomplete-state checks make partial work detectable. Index replacement is recoverable, not a cross-system atomic transaction. |
| How would this scale? | Validated immutable snapshots, narrower integrity checks, read/write generation control, operational monitoring, better evaluation; current full validation per query is expensive. |
| What do the automated tests establish? | Defined parser, validation and lifecycle behavior. Development source/retrieval checks are separate; neither proves general accuracy. See the latest review for the current test count. |

## Small change exercise

Before an interview, implement a new explicit city filter on a temporary copy: inspect `mentions` and `answer_records`, decide exact aliases, add positive/negative boundary cases, and verify that the complete eligible set is returned. Explain why changing only the prompt text or top-k is insufficient.

## Be precise about completion

Distinguish implemented code, development tests, fresh-environment replay, packaged files, recorded video and published repository. See DELIVERY_CHECKLIST.md for the current state. Do not claim a completed video or independent-machine test on the basis of a guide or same-host virtual environment.
