# Extraction checkpoint — 2026-10-17

Final v2.0.2 corpus processing, independent saved-output audit and offline rerun passed. Schema validation and factual development review are separate measures.

## Implemented behavior

`extract.py` is independent of scraping: it enumerates the saved raw manifest, verifies original bytes and extracts full-schema JSON. Missing mandatory publication metadata, invalid canonical URLs, damaged raw inputs and validation failures are logged/quarantined. Publication times retain original evidence and normalize to UTC; fetch timestamps are never substituted. Accepted IDs and record checksums are published in data/extraction/manifest.json. Downstream must require a completed manifest scan and verify current hashes; historical JSON files are not acceptance evidence.

Body extraction uses Trafilatura with a narrow IndianWeb2 post-body fallback when long publisher text spans are lost. Summaries contain 2–3 supported source sentences; this is an extractive lead-summary baseline. Named companies/organizations, people and places use a local GLiNER model with explicit competing product labels and documented normalization/type rules. Named physical places/facilities may appear in locations; those are not commercial companies. Investor relationships are parsed separately rather than treating every mentioned organization as an investor.

Funding includes exact decimal base-unit amounts/currencies, original amount text, company, round, named investors and evidence. Unknowns remain null/empty. Kinds separate venture, strategic investment, debt and financial support; statuses distinguish reported, closing and committed. An announcement does not establish an independently verified transaction or disbursement date.

## Why the entity model changed

The initial spaCy-only baseline passed schema/storage tests but the five-pilot manual review found **13 wrong classifications among83 returned display strings** (70/83, approximately84.3% type precision), plus omissions. Product-rich articles outside those five were substantially worse. The original result is preserved in extraction_label_evaluation_v1_3.json; the additional pre-GLiNER lists are in entity_baseline_additional_review.json.

After comparing real outputs on ServiceNow, Funskool and Circle, selected `urchade/gliner_small-v2.1`, revision `4e091416cf7c3481db542c2a3d26156916f3a47f`. Setup downloads this public model once, saves safetensors/tokenizer/embedded encoder configuration and checksums locally, then extraction uses local-only loading. spaCy en_core_web_md3.8.0 remains for linguistic/sentence analysis. GLiNER0.2.29/PyTorch2.14.1/Transformers5.16.1 are pinned. No paid key, remote inference, article upload or GPU is required.

Entity windows have a90-word initial target and15-word overlap, shrinking to at most240 subtokens and300 model word units. Over-budget indivisible input fails visibly. Evidence uses original body character offsets. Model scores are not calibrated accuracy probabilities. Type vocabulary and generic-name cleanup were developed from reviewed examples; improved scores on those examples are development results, not held-out accuracy.

## Development factual review

Reviewed the five original pilot articles and all11 initially identified funding articles, plus Federal Bank, then added three financing edge cases: **18 distinct articles** in total. This is an agent review against saved source text, not independent human annotation or fact-checking of the publisher.

The declared labels cover company, amount, currency, round, named-investor relationship and status on the initial funding set; the extra debt/support cases also check kind. Four nonfunding examples check null funding. The final v2.0.2 corpus passes **91/91 declared checks**. Labels and evaluator are saved in extraction_manual_labels.json and tools/evaluate_extraction_labels.py; final evaluation output is extraction_label_evaluation.json.

The final entity review covers **10 articles and 147 returned display strings**: 145 were judged correctly typed, with two incorrect company fragments (`Group`, `Kuehne+NagelWith`) in the Kuehne+Nagel article. This is approximately **98.6% development-sample type precision**, not unseen-data or whole-corpus accuracy. Aliases count as separate display strings. Known omissions remain, and exhaustive recall was not measured. The same examples informed model/rule choices, so this is not a held-out evaluation.

Important checked distinctions:

- Circle: ₹25 crore raised versus ₹25 crore transaction sales; Myntra/Delhivery are affiliations, not investors in this round.
- ThinkMetal: ₹27 crore company round versus the investor fund's $100 million corpus;3i Partners is a participant.
- byteXL: $9 million; “The Michael & Susan Dell Foundation” remains one investor.
- Unveilr AI: ₹16.7 crore is valuation, so the raised amount remains unknown; AJVC is the named investor.
- MoneyTruVa: undisclosed amount. The audit requires the two headline investors but **does not claim a complete shareholder list**.
- Inner Sky Labs: ₹300 crore round is described as closing; not asserted closed/disbursed.
- Subvocal: approximately $1.3 million reported for The Subvocal Company, not a product named WearableTech. Approximation remains in source evidence.
- Arma/EBG: ₹10 crore current strategic investment is separate from a planned larger commitment.
- Peptris: ₹86 crore current committed support through optionally convertible debt is separate from historical ₹70 crore Series A funding/investors.
- Capital India Finance: ₹100 crore NCD issue is debt financing; its ₹50 crore components are not separate rounds.
- WASH bond: ₹180 crore raised by NABKISAN Finance Limited; coupon/tenure figures are not the raised amount.
- ServiceNow/GE/visa-policy/Federal Bank: no current funding object inferred from unrelated financial or historical statements. Federal Bank's net profit is not mislabeled as revenue.

## Final evidence

- Final v2.0.2 run `2026-10-17T094321433861-0000`: 81 records written, zero failures, 81 accepted; 09:43:21–09:49:28 UTC (about six minutes on this CPU environment).
- Independent saved-output audit at 09:50:11 UTC: 81/81 records pass schema, checksum, original metadata and long-span coverage checks. All 1,431 compared long publisher body spans are retained. Categories: business 26, AI 12, funding 14, technology 29. See `data/extraction/audit.json`.
- **39 automated tests pass**, covering the scraper and extraction behavior. Real model outputs were reviewed separately from synthetic/stub tests. Package consistency check passes.
- Final declared financial/null evaluation: 91/91 checks across 18 articles; entity development review as described above. See `results/extraction_label_evaluation.json`.
- Offline rerun `2026-10-17T105656511799-0000`: 81 skipped, zero written, zero failures and zero socket connection attempts while network connections were blocked. Record bytes and modification times remained identical. Run/manifest bookkeeping is updated normally. See `results/extraction_rerun_verification.json`.
- Independently checked all five local sample pairs: HTML is byte-identical to the original raw input, JSON is byte-identical to its accepted record, and every JSON passes ArticleRecord validation. See `results/extraction_sample_verification.json`.

## Limits that carry into indexing/query work

- Entity recognition is not exhaustive. Alias display strings may coexist and source-name boundaries can be imperfect. The audit has not exhaustively labeled entity recall across the corpus; no whole-corpus precision/recall score is justified.
- Exact company/location lists must normalize aliases and check original body mentions. Physical facilities are distinct from the city containing them. A model-only entity filter cannot guarantee complete results.
- Investor arrays contain supported named participants, not proof of complete shareholder coverage. Repeat-investor aggregation needs distinct-round identity, kind/status handling and source checks; unknown or historical rounds must not be silently counted as new.
- Coarse categories use headline/source-label rules. Temporal layoff/event interpretation belongs to later query logic and cannot rely on category alone.
- Summaries are extractive and may preserve source heading/formatting quirks. Long-span coverage checks do not independently establish every word boundary, table layout or publisher fact.
- Model setup was exercised on this Windows/Python3.12 environment. A genuinely clean-machine setup remains a final packaging gate.
- Five full-schema HTML/JSON pairs are retained locally under `data/samples`, with a sample manifest. No publisher corpus/samples, credentials, repository or demo has been published in this checkpoint. Sharing basis remains a packaging decision.

Next stage: chunking, real embeddings and persistent indexing, followed by grounded queries and the eight real query evaluations. This extraction checkpoint does not establish query correctness.
