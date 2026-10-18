# End-to-end assignment review - 2026-10-18

## Current verified checkpoint: 2.0.5

The application is built end to end. The continuation after the usage-limit interruption is complete: source-backed entity type corrections resolve the three recorded error cases and improve **nine records**, with no unexpected entity-list changes in the other 72. Institutions move to organizations, explicitly identified platforms leave the location list, and generic standalone company fragments are removed. Seven new tests protect these corrections and retain genuine geographic/named-group values.

Current results: **76 tests pass in both environments**, all **81 rebuilt records are byte-identical**, all **50 checked source/config files match**, and the index retains **484 chunks**. All ten retrieval probes and all **25 query cases** pass. The eight required answer payloads are unchanged from 2.0.4 and their source-review hashes still match. The 91 financial development checks pass; all correction-evidence spans match stored source text. Extraction reruns skip 81 without changing record bytes/mtimes. The actual CLI reproduces the 14-item city result, and the five current sample pairs import byte-for-byte with overwrite refusal.

Evidence: [aggregate verification](entity_refinement_verification.json), [actual before/after entity changes](entity_refinement_changes.json), [closed error cases](entity_refinement_spotcheck.json), and [where to resume](../CURRENT_STATUS.md). The refreshed archive is checked in `submission_package_verification.json`.

These are same-host development/isolated replays using saved originals and local model downloads. They do not establish perfect entity accuracy or cross-platform behavior. The remaining delivery tasks are the narrated demo and remote repository/submission; there is no unfinished pipeline stage at this checkpoint.

## Previous 2.0.4 review and fixes

Completed implementation review. All four stages remain independently runnable; the fixes, rebuilt outputs and remaining limitations are recorded below. The final verification is in [final_review_verification.json](final_review_verification.json). The recording and remote submission remain separate unfinished deliverables.

## Assessment

The core design is strong for this assignment: four independent commands, preserved originals, schema-validated records, a real persistent vector database, complete structured operations where top-k retrieval would lose recall, and source-backed refusal. The main quality risks are bounded natural-language parsing and imperfect entity/funding recall. Passing integrity checks is not proof of universal factual accuracy.

The implementation is more elaborate than a minimal internship submission. The interview risk is being unable to explain its safeguards and trade-offs; the optional diagnostics and historical checklists should not distract from the four entry points. A UI or another framework would add less value than the correctness fixes below.

## Defects corrected in this review

| Finding | Correction |
| --- | --- |
| HTML headings and nested blocks could merge words across paragraphs, including `modelLorazzo` | Preserve both sides of block boundaries, handle all six heading levels, and bump extractor to 2.0.4 to invalidate old records. Rebuild derived outputs. |
| Table cells in the body fallback could merge into invented-looking names such as `MumbaiCargoPilot` | Preserve column separators and check that revenue tables retain their headers, units and values. Seven affected articles are force-recomputed while finalizing 2.0.4. |
| Latest AI announcements were treated as a company query needing clarification | Recognize topic-level AI announcements while retaining explicit company-announcement requests. |
| Investors in two funding rounds returned funding articles | Recognize numeric repeated-round wording as an aggregation. |
| Revenue forecasts were mistaken for unsupported weather forecasts | Reserve the weather refusal for weather terms; revenue forecasts retain their revenue evidence and qualifiers. |
| `--before` could be overwritten by a natural-language month, or paired with an unintended default lower bound | Explicit time bounds take precedence as a pair. |
| Mumbai followed by a time window became a literal location name | Separate supported trailing time phrases from the location. |
| Layoff timing compared a quoted year with the query year and used current-month language for other windows | Anchor relative event context to article publication and describe the requested window. |
| Index audit could exit successfully when a declared retrieval probe failed | Include retrieval and filter checks in its overall pass flag and exit status. |
| Extraction rerun verification depended on an excluded development research file | Select its five sample IDs from the included fixture manifest, and require all five to be accepted. |

Regression coverage includes realistic heading/nested-block HTML, additional query wording, explicit date precedence, location/time separation and publication-anchored layoff timing. The real query evaluator also exercises five additional wording probes.

## Verification

| Check | Observed result |
| --- | --- |
| Automated behavior tests | 69 pass in both environments; see `final_review_table_tests.txt` and the isolated finalization evidence. |
| Source/config parity | All 49 checked source/config files match between environments. |
| Raw originals | All 81 valid; 25,493,154 bytes retained; no duplicate destinations or orphan HTML. No new live scrape. |
| Extraction rebuild | 81 accepted, no failures; all 81 record files byte-identical between environments. Seventeen bodies change through paragraph/table corrections. |
| Current-parser consistency | All 81 stored bodies/title/date/byline values match recomputation with the final parser; no stale table outputs remain. |
| Source coverage | All 1,431 checked long publisher spans preserved. This does not establish perfect formatting or factual accuracy. |
| Financial development labels | 91/91 declared checks across 18 articles; not held-out accuracy. |
| Persistent vectors | 81 articles, 484 chunks, 384 dimensions; all ten retrieval probes pass (nine at first rank, one at second rank). |
| Reruns | Extraction skips 81 with unchanged record bytes/mtimes and no writes; indexing skips 81 with no embedding/vector writes or removed chunks. |
| Actual query evaluation | All eight required families, eight paraphrases, four negative/ambiguity probes and five new wording probes pass. Exact evidence/URL checks and independent city-body scan pass; zero network attempts. |
| Cross-environment answers | All eight answer payloads match and retain current source-review judgments. Changed outputs 3, 4, 5 and 6 were reviewed again; earlier review hashes remain in `query_source_review_v203.json`. |
| CLI | The actual isolated `query.py` invocation exits zero and returns the same 14 city items as the evaluator. |
| Samples | Five current 2.0.4 pairs import byte-for-byte; a second import refuses to overwrite the destination and leaves files unchanged. |
| Local archive | Regenerated after the review; CRC, required file list, every file hash and common credential-pattern scan pass. See `submission_package_verification.json` for the current archive hash. |

The final table-formatting adjustment was made within unreleased 2.0.4 after the full heading-boundary rebuild. Both environments force-reprocessed the seven affected bodies, rebuilt/audited their indexes and reran all query checks. Final tests are `final_review_table_tests.txt`; earlier `final_review_tests.txt` and `final_review_isolated_verification.json` describe the intermediate full rebuild. The final comparison includes both finalization runs and current source hashes.

## Remaining limits and delivery work

- Entity recognition and financial relationship extraction can still omit or misclassify names. Existing development labels are useful regression checks, not held-out accuracy estimates.
- The earlier targeted spot-check found `IIT Hyderabad` classified as a location, mobility platforms such as `Namma Yatri` classified as locations, and standalone `Group` as a company. **These recorded cases are resolved in 2.0.5**; see `entity_refinement_spotcheck.json`. Original observations remain in `final_review_entity_spotcheck.json`. Development scores still must not be presented as general entity accuracy.
- Answers are deterministic structured results and source excerpts. AI/company overviews select stories; they do not provide fluent thematic synthesis. The language parser supports documented patterns and explicit flags, rather than unrestricted questions.
- Publication windows do not establish transaction/event dates. Investor grouping is intentionally conservative and may undercount distinct rounds; an empty aggregation is limited by extracted participants.
- Model downloads and startup are substantial; full-corpus integrity validation before each query prioritizes correctness over service latency. This remains a small local application.
- This review uses saved original HTML and existing local model downloads. It does not claim a new live scrape, fresh dependency installation, another physical machine, or cross-platform validation. Earlier live collection and initial isolated-installation evidence remain historical evidence.
- The required narrated 3-5 minute recording and remote repository/submission remain outstanding. The walkthrough now explicitly includes the scrape stage. Local package creation is not publication.
