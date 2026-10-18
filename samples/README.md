# Five assignment sample pairs

`raw/<id>.html` contains original response bytes; `records/<id>.json` contains its matching full-schema extracted record. IDs and hashes link them through `manifest.json` and `extraction-manifest.json`. Git attributes disable newline conversion for these ten files so hashes survive checkout.

The samples cover ServiceNow AI governance, Circle startup funding, ThinkMetal manufacturing/funding, GE Aerospace sourcing, and US visa-policy reporting. They are the original source pilot selection, not hand-written answers. Canonical URLs, bylines, publication/fetch times and extraction/model provenance remain in the files.

These five fixtures are for inspection/a small offline replay; the measured development corpus has 81 articles and is deliberately not committed. Rebuild a current 50+ corpus with the documented scrape/extract/index commands. Fresh news and current-time query results may differ from the frozen evaluation.

Optional sample replay: `python tools/import_samples.py --data-dir data-sample` imports validated pairs into a new directory. Install models there using the setup scripts' `--data-dir data-sample`, then index/query with the same flag. This does not satisfy the full-corpus size requirement by itself. See THIRD_PARTY_NOTICES.md for attribution and the recorded source reuse limitation.
