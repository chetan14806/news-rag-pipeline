# Learning this assignment end to end

## Starting point

This learning path assumes solid Python and DSA knowledge. This is an applied backend, data-pipeline and retrieval project. A beginner Python course is unnecessary. The gap to fill is how network requests, durable data, document extraction and retrieval behave when real inputs are messy.

Prerequisites to refresh as needed: HTTP requests/status/headers/redirects, HTML/XML/JSON, Python exceptions/context managers/file IO, virtual environments, Git basics and basic tests. For embeddings, understand vectors, dot products, norms and cosine similarity. SQL-style filtering/grouping is useful for the structured questions. Training neural networks, advanced calculus, a GPU and competitive-programming practice are not prerequisites for the chosen application approach.

## Study in implementation order

### 1. HTTP and responsible collection

Read [MDN's HTTP overview](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Overview), then trace `scrape.py`, `newsrag/scraper.py`, `newsrag/source.py` and `newsrag/fetching.py`. Understand RSS discovery, robots matching, URL normalization, redirect checks, timeout versus total deadline, retries, Retry-After and rate limiting.

Exercise: explain why a 403 and a 429 get different treatment; trace one request through a redirect and retry, including elapsed time. Explain the restart-cooldown finding in `results/PROJECT_REVIEW.md` and design its persisted state before editing code.

### 2. Durable pipeline engineering

Read `newsrag/storage.py` and the relevant tests. Learn manifests, stable IDs, hashes, atomic replacement, locking, partial failure, idempotency and provenance. An atomic file write does not make two separate file writes a transaction.

Exercise: draw what is left on disk if the process stops before the raw write, after that write, and after the manifest update. Explain the redirect-identity finding and how an alias map would preserve provenance. Run the existing tests and diagnostic probes. Use [Python unittest documentation](https://docs.python.org/3.12/library/unittest.html) for unfamiliar test patterns and [Pro Git](https://git-scm.com/book/en/v2) for version-control fundamentals.

### 3. Extraction and evidence

Learn HTML trees, XPath/container selection, boilerplate removal and schema validation using [lxml HTML documentation](https://lxml.de/lxmlhtml.html), [Trafilatura's quickstart](https://trafilatura.readthedocs.io/en/stable/quickstart.html) and [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/).

Build one complete article record first. Then compare the five pilot pages and process the corpus. Distinguish publication time from fetch time, missing from null, company from investor, and a round amount from a fund size. Preserve supporting evidence for fields. Pydantic accepting an amount does not mean that amount was extracted correctly.

Exercise: use the Circle pilot to distinguish its INR 25 crore seed round from its INR 25 crore transaction-sales claim. Compare extracted body text against the original article container. Deliberately test a missing author/date and ambiguous funding statement. The existing pilot is a starting point, not the final schema.

### 4. Embeddings and semantic retrieval

Read [Sentence Transformers semantic search](https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html). Understand what an embedding represents, cosine similarity, chunk boundaries, overlap, top-k retrieval and model/input limits. A retrieved passage is a candidate, not a verified answer.

Exercise: calculate similarity for three tiny vectors manually, then compare real retrieval for a keyword query and a paraphrase. Inspect which chunks contain the necessary answer evidence. Use [retrieve and rerank](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html) later if basic retrieval demonstrably needs it; it is not required as the first implementation.

### 5. Persistent indexing and metadata

Use [Chroma's Python reference](https://docs.trychroma.com/reference/python) as a candidate implementation resource, subject to the project's final index choice. Learn collection persistence, chunk IDs, document metadata, filters and upsert/delete behavior. Keep structured article facts available independently of passage retrieval.

Exercise: index an article, restart, retrieve it, replace it with a shorter version and prove that old chunks are gone. Check that location/date filters use normalized metadata consistently.

### 6. RAG and structured question answering

Watch/read [Full Stack Deep Learning: Augmented Language Models](https://fullstackdeeplearning.com/llm-bootcamp/spring-2023/augmented-language-models/) for the architecture. It is a 2023 conceptual resource; consult current official documentation for whichever model/API is actually selected.

RAG supplies relevant source material to answer generation. Some assignment questions also require exact data operations: all Bengaluru articles, last-seven-day rounds, this-month layoffs and investors recurring across distinct rounds. Top-k passages alone cannot guarantee a complete list or correct aggregation. Define the date reference/timezone and count distinct rounds rather than repeated mentions.

Exercise: classify all eight assignment questions by retrieval, structured operations or both. For each, identify required evidence, filters, citation format and when the system should refuse. Do not silently treat missing revenue as zero or substitute sales for revenue.

### 7. Evaluation and delivery

Learn retrieval precision/recall selectively from [Stanford's Introduction to Information Retrieval](https://nlp.stanford.edu/IR-book/); the entire textbook is not a prerequisite. Separate storage tests, extraction accuracy, retrieval quality and answer correctness. Test exact values, dates, list completeness, citations and unsupported-answer refusal.

Exercise: hand-label a small varied article sample, record field errors honestly, run the eight real queries and inspect each answer against original evidence. Use a few additional questions to avoid tuning only to the supplied examples. Finally reproduce setup in a clean environment and explain the pipeline in a 3–5 minute demo.

## Learning method

For each module: read the concept, trace our implementation, predict behavior on a failure case, run a small experiment, then make and explain a change. Keep observations and unresolved questions in PROJECT_LOG.md. Follow one article from RSS to stored original to structured record to chunks to cited answer before attempting to memorize every file.

You should eventually be able to explain each line that affects behavior and make a small change without relying on generated code. Useful proof tasks: fix redirect aliases, add a category filter, handle a missing date, demonstrate stale-chunk deletion, and explain why an investor aggregation cannot depend only on a semantic top-k result.

Immediate order: understand the existing HTTP/storage flow, close the two review findings with tests, then learn and implement complete extraction. Indexing and query generation follow validated extraction.

## YouTube starting points

The broad field is applied AI/AI engineering, specifically retrieval-augmented generation (RAG), combined with data engineering and backend reliability. Collection is web scraping; parsing facts into a schema is information extraction; embeddings and search are information retrieval/NLP; answering from retrieved sources is RAG.

- [Corey Schafer — Web Scraping with BeautifulSoup and Requests](https://www.youtube.com/watch?v=ng2o98k983k): start here for HTML extraction fundamentals. This is an older fundamentals tutorial, not coverage of our complete retry/storage/restart requirements.
- [StatQuest — Word Embedding and Word2Vec, Clearly Explained](https://www.youtube.com/watch?v=viZrOnJclY0): optional intuition for representing text numerically. Word embeddings are background; our retrieval needs passage/sentence embeddings. Training details can wait.
- [freeCodeCamp — Learn RAG From Scratch, from a LangChain Engineer](https://www.youtube.com/watch?v=sVcwVQRHIc8): main RAG conceptual/code walkthrough.
- [freeCodeCamp — Learn LangChain and Gen AI by Building 6 Projects, taught by Krish Naik](https://www.freecodecamp.org/news/learn-langchain-and-gen-ai-by-building-6-projects): alternate project-oriented learning resource with the YouTube course embedded. It was published in 2024, so use current library documentation for API details.
- [DataTalks.Club — Data Engineering Zoomcamp](https://datatalksclub.github.io/podwiki/course-wiki/data-engineering-zoomcamp/): broader pipeline study with YouTube lectures; optional after this assignment. Its full cloud/distributed stack is larger than our project needs.

Recommended immediate order: Corey for scraping, optional StatQuest intuition, then the freeCodeCamp RAG course. Choose one main RAG course rather than watching several covering the same ground. Learn the concepts independently of LangChain; using that framework is not itself an assignment requirement.

## Extraction implementation to study

Follow `extract.py` → `newsrag/extraction_runner.py` → `newsrag/extraction.py` → `newsrag/models.py`. Then inspect `newsrag/local_entities.py`, `newsrag/entity_rules.py`, and `tests/test_extraction.py`.

The first entity baseline used spaCy's general ORG/PERSON/GPE labels. Manual review found products/facilities in company lists and missing people/companies. The current implementation uses [GLiNER](https://github.com/urchade/GLiNER), a local pretrained entity model with explicit company/organization/person/location/product labels, while spaCy still supplies sentence/linguistic analysis. Its [pinned model](https://huggingface.co/urchade/gliner_small-v2.1) is downloaded during setup, saved locally and checked by hash. This is entity extraction, not the embedding model or answer-generating LLM.

Exercises: explain why the model needs overlapping, bounded windows; trace source character offsets through those windows; explain why a model score of 0.6 is not a guarantee of 60% factual accuracy. Compare the preserved baseline evaluation with the final audit, noting which examples were used to develop corrections. A development-sample improvement is not an unseen-data accuracy estimate.

For financial extraction, trace Circle (raise versus transaction sales), ThinkMetal (round versus investor fund size), Unveilr AI (valuation with undisclosed round amount), Inner Sky Labs (closing), Peptris (committed debt support versus historical Series A), and Capital India Finance (NCD debt). Identify which fields are supported, which are unknown, and what a later query may safely claim.

## Indexing implementation to study

Read `newsrag/chunking.py`, then `newsrag/embeddings.py`, then follow `index.py` into `newsrag/indexing.py`. Finally inspect `tools/search_index.py`, `tools/audit_index.py` and `tests/test_indexing.py`.

An embedding represents the meaning of a passage as a vector. Our pretrained MiniLM encoder produces 384 numbers; we are not training it. Masked mean pooling averages contextual token vectors while excluding padding, and L2 normalization makes vector length one. Cosine distance compares directions. Read the [model's pooling example](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) and [Chroma's Python client reference](https://docs.trychroma.com/reference/python).

Exercises: explain why a wordpiece budget differs from a word count; trace how overlapping chunks retain exact original offsets; explain why title text cannot be casually appended beyond the token limit. Follow a shorter article replacement and identify where old tail chunks disappear. Simulate an interruption after upsert and explain why search must reject the incomplete index until a repair run succeeds.

Compare lifecycle tests using fake vectors with actual model retrieval probes. The first checks storage behavior; only the second exercises semantic retrieval. Neither proves final answer correctness. Explain why nearest-neighbor search cannot guarantee all Bengaluru articles or an accurate investor count, why an empty eligible-ID list must remain empty, and why a small cosine distance is not a probability that an answer is supported.

## Query implementation to study

Follow `query.py` → `newsrag/query_planner.py` → `newsrag/query_engine.py`, then `tools/evaluate_queries.py` and `tests/test_query.py`. The planner expresses the requested operation and time window. The engine chooses either complete record operations or vector retrieval with eligible IDs; evidence spans and URLs make outputs auditable.

Try explaining each distinction: rolling seven days versus calendar month; publication time versus event time; an investor's parent group versus a specific fund; two articles versus two financing rounds; revenue versus profit, a forecast, an industry total or a valuation. The code keeps uncertain cases visible rather than treating missing facts as zero.

The answer layer is intentionally extractive/template based. No generative LLM is required by this assignment, and none is secretly simulated. A later LLM could improve phrasing and intent coverage, but it would still need the same verified filters, calculations and supporting passages. A fluent unsupported sentence would be a regression.

Exercises: add a new company alias and test word boundaries; show that a list with 35 location matches returns all 35 regardless of top-k; add two copies of one funding report and verify the investor count does not rise; make a date-boundary test with an IST reference crossing the UTC month boundary; explain why an article mentioning 2025 layoffs cannot answer a question about layoffs this month. Inspect the eight actual sample outputs, including truthful empty/unsupported outcomes.
