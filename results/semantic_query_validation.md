# Semantic query verification - 2026-10-20

This records the earlier 130-test semantic checkpoint. Later fixes, including exact-one count wording and count/location separation, are summarized in the [current README](../README.md), which carries the current test count. The benchmark scores below describe their original checkpoint and have not been relabeled as a new evaluation.

Follow-up count-wording regression: the real local classifier and answer path were checked on five phrases ("a lone funding round", "a single funding round", "just one funding round", "one round only", and "exactly one funding round"), both alone and followed by "in New Delhi". All ten automatically select investors, parse rounds/eq/1, preserve the requested location, and return clarification_required with no results. Explicit-intent versions also pass. All eight original sample statuses and article sets remain unchanged on the 84-record / 497-chunk corpus, with zero network attempts. These are targeted regression checks, not a new held-out accuracy benchmark or a guarantee for arbitrary wording.

Semantic matching is now the primary operation selector. The keyword-first dispatch chain has been removed. Every inferred operation uses whole-question local MiniLM features and a regularized linear classifier; only explicit --intent bypasses it. No generative LLM, API key, hosted inference, new dependency or article-index rebuild was added.

130 unit tests; all eight original sample queries retain their status and article sets; 13 strict constraint/real-corpus controls pass. The final separate set selects the intended operation in 24/24 cases.

| Set | Questions | Raw classifier intent | Actual planner intent | Correct operation or refusal |
| --- | ---: | ---: | ---: | ---: |
| development | 24 | 20 | 21 | 24 |
| evaluation | 48 | 43 | 45 | 48 |
| acceptance_regression | 32 | 30 | 31 | 32 |
| final_acceptance | 24 | 23 | 24 | 24 |

These are separate measurements: raw inference does not mask corpus names; the actual planner masks recognized names/titles before classifying and then binds/validates slots. Correct operation or refusal counts a wrong/uncertain supported request that clarifies as safe, not understood. It is not an answer-accuracy score. The execution checks use the real local encoder, actual shared planner, 84 accepted records, 497 Chroma chunks and exact source-span checks. The first eight calls use the full QueryEngine API; the benchmark/control calls reuse one validated immutable index snapshot with real retrieval, not cached answers.

All 128 benchmark questions avoid exact training strings. The first sets informed development and gate changes; they are regression evidence, not independent held-out accuracy. The final 24-question set is separate from training and earlier sets. It first scored 24/24 before the last conservative unsupported-conflict gate adjustment and still scores 24/24 afterward. The gate was tightened using failures in the earlier sets. All sets were agent-written/reviewed on the same host, without independent human annotations. These results do not prove unrestricted language understanding.

## Behavior and limitations

- Regularization 0.3, minimum score 0.30, minimum margin 0.05, unsupported-conflict cutoff 0.38. Outputs are uncalibrated ridge scores, not probabilities or cosine similarities. Those cutoffs are engineering choices.
- Labeled examples describe supported operations and out-of-scope requests. Training and query normalization mask known names/titles consistently. JSON traces expose semantic scores, candidate, normalization and abstention reasons.
- Separate rules bind known corpus companies/places and validate dates, title, negation, comparisons and arithmetic. Rules do not select the operation. Unknown entities and unsupported expressions may clarify or need explicit flags.
- Exactly/only one funding round is typed as rounds / eq / 1 and clarifies, with no funding-list or repeated-investor substitution. The executor currently implements only more-than-one distinct funding round. Cross-operation count constraints are not silently dropped.
- Unknown temporal-unit expressions clarify; known company names such as May Mobility are not mistaken for dates. Multiple locations, negation, uncertain scores and unsupported comparisons clarify.
- This changes query interpretation. Corpus eligibility, financial/event extraction, body-mention matching and extractive answer composition still use bounded rules. Some unusual supported paraphrases abstain. This is not a general semantic parser or a promise about every entity/date/condition.

## Reproduce

After normal model/data/index setup, from the publishing repository:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -q
.venv\Scripts\python.exe tools\evaluate_semantic_queries.py --as-of 2026-10-17T12:00:00Z
```

The evaluator blocks network connections, uses a locked real index snapshot, and separately reports intended operation and safe refusal. Use --questions and --split to run other saved sets. Full local proof: results/semantic_primary_final_verification.json and results/semantic_primary_unit_tests.txt in the parent workspace. Earlier failed prototypes and measurements remain in parent results/; they are not current passing proofs.

Raw HTML, extracted-record bytes and index manifests stayed unchanged, with zero network attempts. Source parity, current samples, CLI behavior and the clean archive are checked separately by their saved proofs. All changes are local and uncommitted/unpushed. Existing demo/publication history is unaffected.
