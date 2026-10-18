# Four-minute submission walkthrough

Status: walkthrough prepared; the user chose to narrate and record the actual video. No recording has yet been made or reviewed.

Before recording, finish setup and open the project terminal, README and results/sample_queries.md. Use the full 81-article data directory. Keep credentials and unrelated windows out of the recording. Preinstall models; explain that saved publisher HTML is being reused. Do not show a five-fixture demo as the required full corpus.

## 0:00–0:40 — Problem and architecture

Explain that this is a news retrieval pipeline: original publisher HTML → validated structured articles → persistent semantic index → evidence-backed answers. Point to the four independent entry points scrape.py, extract.py, index.py and query.py. State that the corpus contains 81 IndianWeb2 articles and that answers use deterministic operations and source excerpts.

## 0:40–1:20 — Scraping, saved inputs and extraction

Show one pair in samples/raw and samples/records. Point out source URL, date, body, entities, funding evidence and missing-field handling. Show the saved manifest and extraction audit. Explain that extraction has known entity omissions/errors; measured development checks are not universal accuracy.

Include the scrape stage in the walkthrough. Run the following during rehearsal, then show its actual output in the recording (label any removed waits). It checks fresh robots/RSS and skips verified saves; a changed feed can also add articles. If that happens, finish extraction/indexing before demonstrating queries. Use the existing recorded scrape evidence if live access is unavailable, and identify it as saved evidence.

```powershell
.venv\Scripts\python.exe scrape.py --limit 80
```

## 1:20–2:00 — Persistence and reruns

Run the commands below in the prepared project. Show their real skip counts; if execution is cut for time, label the cut. Explain that unchanged inputs reuse existing records/vectors and changed inputs are validated before replacement.

Model startup can exceed this segment's time budget. Run these beforehand and show their genuine saved run summaries, or cut the wait with an explicit "model startup wait removed" caption. Do not claim saved output is a new live run. The full first scrape/extraction should not be squeezed into the recording by implying it executes instantly.

```powershell
.venv\Scripts\python.exe extract.py
.venv\Scripts\python.exe index.py
```

The existing verified corpus has 81 articles and 484 chunks. Show the actual current values rather than relying on this document if the corpus changes.

## 2:00–3:20 — Actual answers and evidence

Run one semantic question, one complete structured list, and one unsupported question. Use the fixed evaluation time when comparing with saved evaluation results.

```powershell
.venv\Scripts\python.exe query.py "What are the main stories about AI in this collection?" --as-of 2026-10-17T12:00:00+00:00
.venv\Scripts\python.exe query.py "Which articles mention Bengaluru?" --as-of 2026-10-17T12:00:00+00:00
.venv\Scripts\python.exe query.py "What will the weather be tomorrow?" --as-of 2026-10-17T12:00:00+00:00
```

Show a source URL and exact supporting excerpt. Explain why complete location lists scan eligible records while semantic questions use vector retrieval. Open results/sample_queries.md to show all eight required families and their review judgments.

## 3:20–4:00 — Verification and limits

Show the test result and delivery checklist. Explain publication date versus event date, conservative investor grouping, the absence of a generative LLM requirement, and the cost of validating the whole small corpus per query. State the actual clean-environment verification status. Finish with the real repository URL and recording link only once those exist.

## Recording acceptance

- Actual screen recording lasts 3–5 minutes and plays with readable output/audio.
- Commands and answers are real; saved evidence, cached inputs and time cuts are identified.
- Repository link works and recording contains no secrets or unrelated personal content.
- Record the video path/link, duration and review outcome in DELIVERY_CHECKLIST.md and PROJECT_LOG.md.
