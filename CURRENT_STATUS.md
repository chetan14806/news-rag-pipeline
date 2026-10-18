# Current status - 2026-10-18

**The application is built end to end.** The four independent commands are `scrape.py`, `extract.py`, `index.py` and `query.py`. Each persists its output so later stages can run without repeating earlier stages.

## Latest completed checkpoint

Extractor **2.0.5** includes the entity-quality corrections resumed after the usage-limit interruption. The three recorded error cases are resolved; nine records have corrected entity lists with no unexpected changes in the other 72.

- 76 automated tests pass in both local environments.
- All 81 rebuilt records match byte-for-byte across environments.
- The persistent index contains 484 real chunks; all ten retrieval probes pass.
- All 25 query cases pass; the eight required answers remain unchanged and source-reviewed.
- The 91 declared financial development checks still pass.
- Five current sample pairs and the refreshed local submission archive are verified.

Evidence: [current verification](results/entity_refinement_verification.json), [actual entity changes](results/entity_refinement_changes.json), [end-to-end review](results/FINAL_REVIEW.md), [sample answers](results/sample_queries.md).

The two environments are on the same Windows host. Saved raw HTML and local model downloads were reused; this is not a new live scrape or another-machine/OS test. Development checks do not establish universal entity accuracy.

## Where to continue after another interruption

There is no unfinished pipeline stage or in-progress rebuild at this checkpoint. The verified project is published at [chetan14806/news-rag-pipeline](https://github.com/chetan14806/news-rag-pipeline) on `main` (initial application commit `65616c4`). Remaining delivery work is the narrated **3-5 minute demo** and final assignment submission with both links. See [demo guide](DEMO_GUIDE.md) and [delivery checklist](DELIVERY_CHECKLIST.md).

Remaining technical limits: entity omissions/type errors can still occur outside the reviewed cases, natural-language parsing supports bounded patterns and explicit flags, and model startup/full-index validation add latency. These are documented limits; the observed functional checks pass.
