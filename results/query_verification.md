# Query checkpoint verification — 2026-10-17

The query checkpoint's automated evaluation and source/output review passed. This report distinguishes implementation checks from source/output review; no population accuracy score is claimed.

## Answer design

`query.py` loads the persisted current corpus/index and produces a structured plan, an answer, exact body evidence/offsets, source URLs and limitations. No earlier pipeline stage is rerun. Each answer persists independently under `data/queries/runs`. The answer layer uses deterministic operations and verbatim source excerpts, not a generative LLM. The assignment permits this; no API key or remote inference is required.

AI/company overviews use real semantic retrieval constrained by eligible article IDs. Article-specific revenue resolves a unique title and retrieves only within that article, then scans full revenue passages so a top-k miss cannot hide the metric. Complete location lists, funding reports, layoff mentions and investor aggregation scan all validated records. Supported company/location constraints can combine with financial/semantic operations; an explicitly empty eligible set never broadens retrieval.

Query plans expose an aware UTC reference instant and publication bounds. Recent defaults to rolling 30 days; last seven days is rolling; this/previous month are UTC calendar windows. Previous-month upper bound is exclusive, reference instant is inclusive and future publications are excluded. Publication does not establish an event/transaction date. Explicit CLI flags complement a bounded natural-language pattern parser.

## Reviewed source outcomes

The reproducible evaluation uses **2026-10-17T12:00:00+00:00** as a visibly frozen reference. The corpus spans 2026-09-26 to 2026-10-17. These are not claims about today's live news/weather.

1. AI: five relevance-ranked articles selected from 15 eligible title/category matches; exact source lead excerpts. A supported selection rather than an exhaustive thematic synthesis; the startup-ranking article is only partly about AI.
2. Funding: three reported venture announcements in the rolling publication week—As You Asked (₹45 lakh), Circle (₹25 crore), ThinkMetal (₹27 crore). Inner Sky's ₹300 crore round is shown separately as closing. This is not a certified list of transactions completed that week. Debt/support/strategic financing excluded deliberately.
3. ServiceNow: AI Passport announcement with source passages. Thirty-day default displayed. This query has one eligible article.
4. Bengaluru/Bangalore: all 14 explicit body mentions across the accepted corpus, independently cross-checked with a word-boundary regex. Includes contextual mentions; does not imply all articles are primarily about the city.
5. Layoffs: two publication-window articles contain mentions—ranking eligibility and the visa-policy article's historical/unresolved-time references. No new current-month layoff event is established. The older Infosys denial article is outside the month filter. This is a truthful corpus limitation, not proof that no layoffs occurred.
6. Repeat investors: no repeat established across nine reported venture announcements and 23 extracted named participants. IAN Alpha Fund and IAN Angel Fund remain distinct. Historical round investors, debt/support, closing status and undisclosed participants are not invented. Missing investors and ambiguous same-company identity can undercount.
7. Revenue: the selected Adani-affiliate article reports Vishakha Renewables' FY26 revenue of ₹1,893.4 crore, up 24.8% YoY. The answer preserves source context and period; it does not use the IPO amount or profit as revenue.
8. Mumbai weather: explicit refusal, no invented weather and no external lookup.

These judgments are agent review against saved publisher text, not independent human annotation or verification of publisher truth. `sample_queries.md` is generated from actual engine outputs. Review judgments attach to a digest of the specific plan/answer/items/sources; changed outputs revert to pending review.

## Tests and evaluation

Final suite: **62 tests pass** (24 scraper, 15 extraction, nine indexing, 14 query), recorded in `query_test_run.txt`. Final real-corpus evaluation completed at **2026-10-17T13:04:16.011459+00:00** with all declared checks passing: eight samples, eight paraphrases and four negatives; exact evidence spans/URLs; all 14 city matches; matching structured paraphrase item sets; expected revenue evidence; correct unknown-company/profit-only/ambiguous-title/unsupported outcomes; and **zero network attempts**. See `query_evaluation.json`. Earlier development output is preserved in `query_evaluation_initial.json`.

All eight final sample answers have matching digest-bound judgments in `query_source_review.json`, rendered into `sample_queries.md`. Review is by this coding agent against saved source text, not an independent annotation study. No answer text was manually replaced with an ideal result.

Direct CLI smoke check: `query.py "List all articles that mention Bengaluru." --as-of 2026-10-17T12:00:00Z --json` exited successfully and returned the same 14 article IDs/order as the evaluator. All eight review digests match, no sample judgment remains pending and the shared lock was released. See `query_cli_smoke.json` and `query_cli_verification.json`.

Focused query tests cover common paraphrase families; rolling boundaries/future exclusion; UTC calendar windows with an IST reference crossing a month boundary; exhaustive 35-item location recall independent of top-k; company word boundaries and unknown entities; combined funding/location/company constraints; closing/debt exclusion; duplicate/ambiguous rounds and legal-suffix/stage aliases; distinct funds; profit versus revenue, forecast/industry subject context and table rows; title ambiguity; historical/negated/conditional layoffs; and unsupported-request refusal without retrieval.

The real offline evaluator runs all eight sample queries, eight paraphrases and four negative/ambiguity probes. It validates exact evidence spans/URLs, independently checks the complete city set, compares structured paraphrase results and checks weather refusal, known source revenue and negative statuses. Socket connections are blocked throughout model loading/querying. These checks do not prove every unsupported phrasing or semantic inference correct.

## Limits and next checkpoint

- Pattern-based intent coverage is bounded. Arbitrary multi-part questions, unrecognized aliases and unfamiliar phrasing may need explicit flags or clarification; this is not a general conversational assistant.
- Extractive summaries can retain source formatting and do not offer an LLM's fluent multi-document synthesis. Candidate filters can miss synonyms; rank order is not a correctness probability.
- Layoff event timing is conservative and currently recognizes explicit relative timing only for positive events. Absolute-date or complex mixed historical/current narratives may remain unconfirmed.
- Round counting is a conservative heuristic, not a globally resolved financing-event database. Corporate alias coverage is limited; same-company repeated stage/unknown identity may undercount. Named investor extraction is incomplete.
- Revenue passages retain context; the engine does not normalize every financial table or infer company attribution where the source is unclear.
- Every query checks full corpus/index integrity under the shared lock. This is slower and less concurrent than a production serving architecture.
- Remaining delivery work: clean-machine setup under ten commands, final sample-sharing/packaging review, repository delivery and 3–5 minute demo. No deployment/publication is claimed.
