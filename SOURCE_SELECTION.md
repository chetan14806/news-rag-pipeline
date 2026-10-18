# Source selection and five-page feasibility pilot

Checked: 2026-10-17, Asia/Kolkata. Decision: **IndianWeb2 is the selected development source; TechNode is the technical backup.** Use only one source in the final corpus.

Subsequent implementation update: the production scraper checkpoint is now complete with 81 saved originals. See [scraper verification](results/scraper_verification.md). The five-page pilot below remains historical source-feasibility evidence, not the current corpus count.

## Why IndianWeb2

- Site: https://www.indianweb2.com/
- Focus: Indian technology, startup and business news. Select relevant news/announcement stories; exclude unrelated advice, promotions, and non-news items during corpus preparation.
- Robots: https://www.indianweb2.com/robots.txt returned HTTP 200. The wildcard group disallows `/search` and allows other paths. The published sitemap URLs themselves use public Atom feeds. Article paths and the tested RSS endpoint do not match `/search`.
- Discovery: https://www.indianweb2.com/feeds/posts/default?alt=rss&max-results=100 returned HTTP 200 and **100 distinct article URLs**, dated September 23–October 16, 2026 in the saved feed. No search endpoint, private API, login, browser impersonation, or bypass was used.
- Five chosen HTML pages all returned HTTP 200, with full readable bodies available without browser rendering, a matching canonical URL, author byline, and publication timestamp with a +05:30 timezone.
- Bodies are substantial enough for meaningful passage retrieval: 589–1,135 words in the final pilot extraction.
- Better fit than TechNode for Indian startup funding and Bengaluru questions.

Discovery proves a route to more than 50 candidates, not that 50 records are already accepted. The production scrape/extraction is still to be built.

## Preliminary coverage screening

The saved 100-item feed was screened using titles and RSS descriptions. These are **keyword candidate counts**, not validated event/category/entity counts. The categories overlap.

| Keyword family | Candidate matches | Published in the preceding seven days |
| --- | ---: | ---: |
| Funding/raises/raised | 31 | 6 |
| AI | 34 | 11 |
| Bengaluru/Bangalore, word-boundary matching | 16 | 5 |
| Revenue | 12 | 2 |
| Layoffs/job cuts | 2 | 0 |

Reference instant: 2026-10-17T06:42:36Z, the feed probe's recorded start time. This is a reproducible screening reference, not the future query engine's fixed clock. See `research/indianweb2_feed_coverage.json` and `tools/summarize_source_feed.py`.

The initial exploratory location regex counted 17 loose substring matches; word-boundary matching reduces this to 16. Use the latter. Do not advertise either as exhaustive article-level location recall.

Coverage limitations:
- A funding keyword can refer to background funding or an investor's fund rather than a new startup round.
- The policy article mentions historical layoffs; that does not establish a new October layoff event. A layoffs summary may need a truthful empty/limited answer after classification.
- Repeated investors across distinct funding rounds have not yet been verified; inspect this when selecting the full corpus. Do not promise a positive aggregation result prematurely.
- Revenue can refer to an industry or a different company. The pilot's GE article reports Indian airline industry revenue, not GE Aerospace's revenue.
- Much of the site is announcement/press-release-style material. Preserve attribution and reported claims; do not describe publisher claims as independently fact-checked facts.

## Five real article checks

| Pilot article | Why included | Final words | Byline | Publication in UTC |
| --- | --- | ---: | --- | --- |
| [Circle funding](https://www.indianweb2.com/2026/10/circle-raises-rs-25-crore-led-by-nexus.html) | Exact funding, named investors, people, Bengaluru | 675 | IndianWeb2 Desk | 2026-10-14 04:23 |
| [ThinkMetal funding](https://www.indianweb2.com/2026/10/thinkmetal-secures-27-crore-led-by-ian.html) | Funding vs investor-fund-size distinction | 795 | IndianWeb2 Desk | 2026-10-13 07:09 |
| [ServiceNow AI Passport](https://www.indianweb2.com/2026/10/servicenow-launches-ai-passport-to.html) | AI/product launch and availability evidence | 1,135 | IndianWeb2 Desk | 2026-10-16 09:54 |
| [GE Aerospace India announcement](https://www.indianweb2.com/2026/10/ge-aerospace-announces-plans-to-nearly.html) | Business expansion, Bengaluru, revenue context | 1,061 | IndianWeb2 Desk | 2026-10-12 12:44 |
| [US visa-policy report](https://www.indianweb2.com/2026/10/us-freezes-microsoft-adobe-indian-it.html) | Policy, several companies, historical layoff mentions | 589 | IndianWeb2 | 2026-10-09 08:36 |

Read article text against the saved HTML. Checks performed:
- All five original HTML copies are byte-identical to the saved HTTP response bodies.
- All five canonical links match fetched article URLs.
- All five pilot metadata/body records validate with Pydantic, including timezone-aware publication dates.
- Article microdata retains +05:30 source timestamps; normalized records use UTC. RSS timestamps differ in seconds from minute-precision on-page timestamps; use the on-page publication evidence and retain original precision/provenance during production extraction.
- Generic Trafilatura extraction was insufficient on four pages: it omitted 1, 2, 1, and 4 compared body spans respectively. Some were company descriptions, but the ServiceNow omission included product availability, and the policy omission included substantive text.
- Added a narrow fallback to the known `.post-body` container, removing scripts/styles/forms/iframes and preserving text and line breaks. Circle still uses Trafilatura; the other four use the fallback.
- Final comparison finds **zero missing spans among 112 long body-text spans** after word/whitespace normalization. This checks the compared spans, not every byte/formatting detail or factual correctness.
- Manually reviewed the primary outputs and the identified restored spans. Site navigation, subscription UI, comments and unrelated sidebar content are outside the selected article-body container.

Example extraction traps for the next phase:
- Circle: the article reports both INR 25 crore seed funding and roughly INR 25 crore pre-owned sales. These are separate facts despite the identical amount; sales must not automatically become company revenue.
- ThinkMetal: INR 27 crore is the reported company round; USD 100 million describes IAN Alpha Fund's size, not ThinkMetal's raise.
- ServiceNow: availability statements must survive extraction, rather than turning an announced upcoming capability into an already available one.
- GE: industry revenue, supplier spending, facility investment, and the company's own revenue are different quantities.
- Policy: historical layoff mentions must retain their time and attribution; they do not automatically qualify as new layoffs this month.

Pilot records intentionally contain only metadata and body. They are **not the final assignment JSON schema**: companies, people, locations, summary, category and funding objects still need implementation and validation.

Artifacts:
- `research/source_probe/manifest.jsonl`: request outcomes, URLs, UTC times, HTTP status, saved paths and crawler identity.
- `research/source_probe/*.bin`: original research responses, kept local and ignored by Git.
- `research/pilot/indianweb2/raw/*.html`: five unchanged article responses, kept local and ignored.
- `research/pilot/indianweb2/records/*.json`: five pilot metadata/body records, kept local and ignored.
- `research/pilot/indianweb2/verification.json`: reproducible comparison results.
- `research/pilot/indianweb2/feed_candidates.json`: 100 candidate URLs/titles/dates.
- `research/pilot/indianweb2/extraction-review.txt`: local full-text QA output, ignored by Git.

## Other sites checked

| Candidate | Observed outcome | Decision |
| --- | --- | --- |
| Inc42 | Robots explicitly signals AI input allowed, public feed works; [terms](https://inc42.com/terms-and-conditions/) also restrict automated copying and archiving without permission | Do not select on robots signal alone |
| YourStory | Public article paths allowed for wildcard crawler; [terms](https://yourstory.com/terms-and-conditions) restrict artificial/automated collection | Not selected |
| Entrackr | Excellent topic match; robots/feed work; [terms](https://entrackr.com/page/terms-of-use) explicitly restrict systematic collection/database creation without consent | Not selected |
| TechCrunch | Feed and pages accessible; bot-specific restrictions, limited personal-use/reproduction terms and restrictive [RSS terms](https://techcrunch.com/rss-terms-of-use/) complicate this saved-HTML use | Not selected |
| TechNode | Robots-compatible article paths; RSS exposed 2,000 unique URLs; five HTML pages passed metadata/body pilot | Technical backup; weaker Indian/location fit |
| Silicon Canals | Robots-compatible and reachable; sampled latest feed is older and currently mixes technology with broader lifestyle/psychology content | Less suitable corpus fit |
| Startup News Australia | Robots-compatible and reachable; latest feed has sparse recent output, many grant/government items; reproduction limits in terms | Weaker fit for recent startup-round queries |
| Silicon Republic | Reachable robots/feed; requires five-second crawl delay, which the ongoing probe now exceeds with six-second delays | Not needed after finding a better Indian source; not a completed article pilot |
| Indian Startup News | Robots-compatible, good geographic fit; [terms](https://indianstartupnews.com/page/terms-and-condition) prohibit reproduction/copying | Not preferred for saved/shareable sample requirement |
| Crunchbase News | Robots reachable; separate content/use restrictions require more review | Not selected or article-tested |
| Techdirt | Reuse-friendly publisher statements, but robots request returned HTTP 403 | No bypass attempted; not selected |
| EU-Startups | Robots request returned HTTP 403 | No bypass attempted; not selected |

For TechNode, title-only feed screening found 59 funding-related candidates, 12 layoff-related candidates and 40 revenue-related candidates. Bengaluru/Bangalore was absent from the screened RSS text. Its five clean pilot bodies were only 69–135 words, while IndianWeb2 gives more substantial multi-passage examples. TechNode's pilot is retained as supporting research, not mixed into the final corpus.

## Access, pacing and redistribution boundary

Use an honest descriptive crawler identity, six-second minimum spacing, one request at a time initially, and fresh robots checks before production crawling. Respect failures, server rate limits and any longer advertised delay. Avoid `/search`, private APIs, account-only content and unrelated third-party resources.

IndianWeb2's checked homepage links, robots, privacy policy and editorial policy did not reveal an explicit automated-collection prohibition. This is a limited access-policy review, **not an affirmative licence to redistribute full pages**. Public availability/robots allowance does not establish such a licence. Keep originals local for the pilot; resolve the required sample's sharing/reuse basis during submission packaging before publishing full HTML. No publisher was contacted and no content was published/shared externally.

## Environment and reproducibility

Created a project-local `.venv` using bundled Python 3.12. Standard ensurepip bootstrap initially failed; installed the pilot packages into that environment using the bundled pip's `--python` option. Pilot pins: `research/pilot-requirements.txt` (Trafilatura 2.3.1, Pydantic 2.14.1). Final application requirements and embedding compatibility remain for implementation.

Offline reruns after dependencies exist:

```powershell
.venv\Scripts\python.exe tools\extract_source_pilot.py --site indianweb2
.venv\Scripts\python.exe tools\summarize_source_feed.py
```

These read saved responses and perform no fetching or model calls. `tools/source_probe.py` is a transparent research fetch helper, not the production scraper: it does not yet automate robots enforcement, retry policy, refresh/idempotence, corpus filtering or extraction. Every tested endpoint was checked manually against the reviewed robots paths; production code must implement the guardrails.

## Checkpoint result and next action

**Source-selection and technical extraction pilot passed.** Selected development source: IndianWeb2; discovery: public RSS; body extraction: general extractor with measured site-specific fallback; dates: on-page Blogger microdata normalized to UTC.

Next: build the production scraper with robots enforcement, retries, manifests and skip-on-rerun behavior; select/download enough relevant candidates to yield 50+ accepted articles. Then implement the complete extraction schema. Full-corpus accuracy, aggregate-query coverage, sample redistribution, final models, and final setup are not claimed complete by this checkpoint.
