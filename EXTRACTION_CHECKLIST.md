# Extraction checkpoint

1. [x] Define schema, evidence, missing-field and persistence contracts.
2. [x] Build offline metadata/body extraction with completeness checks.
3. [x] Add local named-entity recognition, extractive summaries and conservative funding/category rules.
4. [x] Verify one representative article, then the five source-pilot articles.
5. [x] Add behavioral tests for missing dates, financial ambiguity, validation, reruns and stale-record quarantine.
6. [x] Process saved manifest inputs and inspect failures/warnings.
7. [x] Audit varied records against original evidence; report errors and limitations (18 financial/null cases; 10 entity cases).
8. [x] Document commands, measured results and next-stage handoff; update project log.

Completed 2026-10-17: 81 accepted records, 39 passing tests, 91/91 declared financial checks, independent saved-output audit, offline no-write rerun and five byte-matching sample pairs. Entity review retains two known false fragments and omissions; no whole-corpus or held-out accuracy claim. Evidence and limits: results/extraction_audit.md. Indexing is next.

## Contracts

- No publisher requests during extraction. Read only manifest-referenced, hash-valid originals under the existing writer lock.
- Required article fields: id, url, title, author (list of bylines), published_at (UTC), body, summary (2–3 source sentences), companies, people, locations, category, funding (object or null). Retain raw hash/path, original publication string, extraction fingerprint/version, evidence and warnings as provenance.
- Missing/unreliable title, body, timezone-bearing publication date, or mismatched canonical URL quarantines the record. Missing byline is an empty list plus warning, never invented.
- Named entities are model predictions supported by exact source spans. Organizations include institutions/funds as well as companies. Recognition is imperfect; normalize Bangalore/Bengaluru explicitly. No inferred headquarters location.
- Summary is explicitly extractive, consisting of 2–3 complete body sentences. It is not an LLM-generated synthesis or independently fact-checked account.
- Funding: explicit reported raises/backing or financial-support agreements, corroborated by body evidence. Preserve amount text, exact decimal base-unit value/currency when unambiguous, round, company, named investors/funders and evidence. Distinguish venture, strategic investment, debt/support, and reported/closing/committed status. Unknown subfields remain null/empty with warnings; valuation, fund corpus, revenue, merely planned investment and transaction sales are not substituted for a current raise. Historical rounds do not become current support terms. Ambiguous events must be flagged, never filled by guessing.
- Accepted means schema/body pipeline validation, not blanket factual correctness. Development audit separately checks critical facts and entity type precision on a declared sample, recording known omissions; exhaustive recall remains unmeasured. Gate to indexing requires at least 50 records and an honest audit.
- Atomic record writes, a current accepted-record manifest, append-only errors and per-run summary. Fingerprint raw hash plus extractor/model/rule versions; skip only matching valid JSON. Invalid/changed inputs must be excluded from the current extraction manifest even when old record files remain on disk. Downstream reads that manifest, never globs records.
- Save five matching full-schema pilot pairs locally; redistribution/sample publication remains a packaging decision.

Implementation choices: GLiNER small-v2.1 with pinned revision and local safetensors assets, spaCy en_core_web_md for sentence/linguistic analysis, Trafilatura plus source-container fallback, explicit financial rules, and extractive lead summaries. Entity input windows preserve source offsets and enforce model budgets; scores are not accuracy guarantees. Development vocabulary corrections and prior failed baseline scores are retained in the audit history.
