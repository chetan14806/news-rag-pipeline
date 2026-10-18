# Scraper verification — 17 October 2026

**Result: scraper checkpoint passed.** Final local collection: **81 original HTML pages**, all passing file integrity and extraction-input structure checks. The initial target was 80; a live-feed update introduced one additional eligible article during rerun verification.

## Real runs

| Run | Start → finish (Asia/Kolkata) | Newly downloaded | Verified skips | Failed articles | HTTP requests |
| --- | --- | ---: | ---: | ---: | ---: |
| Small live gate, target 5 | 12:26:40 → 12:27:19 | 5 | 0 | 0 | 7 |
| Main collection, target 80 | 12:28:41 → 12:36:21 | 75 | 5 | 0 | 77 |
| Incremental rerun, target 80 | 12:39:32 → 12:39:47 | 1 | 79 | 0 | 3 |
| Final no-download rerun, target 81 | 12:40:20 → 12:40:30 | 0 | 81 | 0 | 2 |

Requests include fresh robots and RSS requests each run. The last run made exactly those two requests and no article requests. During the incremental run the feed introduced `jio-prices-indias-biggest-ipo.html`; its addition explains the count increasing from 80 to 81. This was not a duplicate or a replacement of an earlier page.

Saved run IDs (UTC encoded):
- Small gate: `2026-10-17T065640609948-0000`
- Main collection: `2026-10-17T065841242212-0000`
- Incremental rerun: `2026-10-17T070932566202-0000`
- Final rerun: `2026-10-17T071020641864-0000`

## Final corpus checks

| Check | Measured result |
| --- | --- |
| Manifest article count | 81 |
| Raw HTML files | 81 |
| Total original response-body bytes | 25,493,154 (about 25.5 MB) |
| Valid raw sizes/SHA-256 hashes | 81/81 |
| Invalid raw artifacts | 0 |
| Duplicate final fetched URLs | 0 |
| Unreferenced/orphan raw HTML files | 0 |
| Expected title/body/byline/canonical/publication markers | 81/81 |
| Structural input-readiness flags | 0 |
| Changed original 80 files during incremental run | 0 |
| Manifest change during final 81-page rerun | None; exact manifest-byte hash unchanged |
| Raw changes during final rerun | None; all 81 recorded hashes and filesystem modification times unchanged |

Discovery processed 100 current feed entries, retained 94 eligible URLs and logged six exclusions. Three exclusions are advice/book posts; three lack the selected broad labels (including two potentially relevant technology/business stories and one climate/weather story). This is a conservative label-based corpus definition, not an exhaustive crawl of all relevant publisher news. Publisher labels are not final extracted entity/category facts.

The separate input check reads saved HTML without changing it. It verifies an article title, `.post-body` container with at least 200 characters of text, byline, source-compatible canonical URL and parseable timezone-aware publication marker. This does **not** prove full body completeness, correct entity/funding extraction, publisher factual accuracy, or final assignment-schema acceptance.

## Automated verification

**19 behavioral tests passed** in the project environment. They cover:

- Source URL boundaries, tracking/mobile normalization, scope exclusions and duplicate URLs.
- Malformed/empty discovery feeds and DTD rejection.
- Robots longest-match/wildcard rules, denial, crawl-delay, request-rate and unsupported visit windows.
- Redirect validation before fetching, including malformed/cross-site/disallowed targets.
- Timeout retry bounds, exponential backoff, Retry-After seconds/date values, persistent throttling and long cooldown pauses.
- Partial/oversized HTTP bodies and non-HTML article responses.
- Failed-article isolation, shortfall reporting and discovery-only operation.
- Byte-preserving saves, hash/missing-file repair, no-download reruns and failed refresh preservation.
- Corrupt JSON/non-object manifests, writer locks and interruption recovery.

Tests use simulated network/time and real temporary files. The four real publisher runs separately exercised the actual HTTP transport. Dependencies passed `pip check`; the CLI help/run path was checked. A fresh-machine setup test remains for final packaging.

## Evidence and reproduction

Commands from the repository root, with dependencies installed:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe tools\audit_scrape.py
.venv\Scripts\python.exe tools\check_raw_inputs.py
.venv\Scripts\python.exe scrape.py --limit 81
```

The audit commands use saved files only. The scraper checks the current live feed, so later runs can discover genuinely new articles; exact corpus counts may grow. The recorded no-download result applies to the run above, not a promise that the feed never changes.

Local machine-readable evidence:
- `data/manifest.json`
- `data/integrity-audit.json`
- `data/input-readiness.json`
- `data/incremental-rerun-evidence.json`
- `data/rerun-evidence.json`
- `data/runs/<run-id>.json`
- `data/logs/requests.jsonl`

The raw HTML, full feed snapshots and logs are ignored by Git and have not been published. Required final HTML/JSON sample packaging and redistribution review remain separate.

## Extraction handoff

Read manifest-referenced originals, verify their hashes, and preserve IDs/source URLs. Resolve publication dates from article metadata rather than fetch time or server Last-Modified. Implement the complete article schema and validate actual entity/funding correctness. Retain the pilot's completeness comparison and IndianWeb2 article-container fallback. Target at least 50 accepted final records from these 81 raw inputs; no full extraction/index/query completion is claimed here.
