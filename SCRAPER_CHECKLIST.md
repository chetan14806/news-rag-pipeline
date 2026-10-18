# Production scraper work sequence

Scope: reliable, single-source assignment scraper; extraction/index/query remain separate.

The original sequence below is complete. Independent review subsequently reproduced two gaps, now fixed with regression tests; see results/PROJECT_REVIEW.md and results/scraper_hardening_verification.json:

- [x] Deduplicate redirect aliases by final article identity and add regression tests (both feed orders, target filling, repair/refresh, reruns).
- [x] Persist publisher cooldown across process restarts and add restart/expiry regression tests (seconds, HTTP date, short cooldown, corrupt state).

Current automated suite: **24 tests pass**. Real corpus re-audited after changes: 81 valid originals, no duplicate destinations or orphan files. No new publisher requests were needed for this checkpoint.

1. [x] Inspect existing pilot, source labels, access rules, dependencies.
2. [x] Define contracts before implementation (below).
3. [x] Implement discovery, guarded fetching, persistent state, CLI.
4. [x] Verify failure handling, access rules, original bytes, integrity repair, reruns with automated tests (19 passing).
5. [x] Run a small live batch and inspect saved artifacts (5 successful, all hashes/body/date metadata checked).
6. [x] Collect 80 successful raw articles at a respectful pace (81 final: one new feed article appeared during verification).
7. [x] Rerun; verify no article downloads, stable IDs/hashes/counts (0 downloads, 81 verified skips; unchanged manifest bytes and raw modification times).
8. [x] Write measured results, limitations, run instructions and extraction handoff; update project log (results/scraper_verification.md).

## Contracts agreed for this build

- Source: IndianWeb2 only; HTTPS and exact source host; dated `.html` article paths discovered from its public RSS feed.
- Scope: feed labels Business, Technology, Startups, or Startup Funding. Exclude Business Tips/advice and book posts. Save exclusions and source labels; do not hard-code the eight sample answers or cherry-pick articles around them.
- Default target: 80 successful stored raw pages. These are not yet 80 schema-validated extracted articles.
- Honest crawler identity, single sequential request stream, at least six seconds between request starts, longer robots/server delays honored. No fast-delay override for live scraping.
- Fresh robots check each run; fail closed if unavailable/invalid. Use Protego for wildcard/longest-match rules. Check redirect targets before requesting; stay on source host and permitted endpoint types.
- Bounded timeout/response size/attempts; transient errors retry with exponential backoff and Retry-After. Access denial does not trigger retries/bypass. A long server cooldown pauses the run instead of retrying early.
- Raw response-body bytes preserved. No article parsing/cleaning in this stage. Discovery parses RSS metadata only.
- Stable full SHA-256 URL IDs. Tracking parameters and Blogger's known mobile alias normalize to the article URL; unknown article parameters are rejected.
- `data/raw/<id>.html` plus versioned `data/manifest.json`; manifest stores original/final URL, fetch UTC time, status, content type, bytes, SHA-256, discovery provenance and redirect history.
- Manifest updates and file writes atomic; exclusive writer lock. Skip only a successful manifest entry whose saved bytes match size/hash. Missing/corrupt artifacts are repaired by refetching. Broken manifest aborts visibly.
- Append request-attempt/failure logs; save original robots/feed snapshots, discovery decisions, per-run summaries. Interrupts preserve completed articles and release the lock.
- Raw corpus/logs ignored in Git; sharing five required samples is handled separately during packaging. No external publication in this step.
- Tests use injected fake network/time plus actual temporary files, so access/failure/pacing logic can be checked without hammering a publisher.
