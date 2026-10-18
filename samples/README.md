# Five sample pairs

`raw/<id>.html` contains the original response bytes. `records/<id>.json` contains its matching extracted record, including URL, title, author, publication time, body, summary, entities, category, funding and provenance.

The five pairs cover ServiceNow AI governance, Circle startup funding, ThinkMetal manufacturing/funding, GE Aerospace sourcing, and US visa-policy reporting. IDs, original fetch metadata and SHA-256 hashes link each pair through `manifest.json` and `extraction-manifest.json`. Git attributes disable newline conversion for HTML and record JSON so their bytes survive checkout.

These are inspection fixtures from the original source pilot; the 81-article development corpus is not committed. To build a current 50+ article collection, use the README's scrape/extract/index commands. Fresh news and current-time query results can differ from the saved sample answers.

Article content remains third-party material; see [attribution and source terms](../THIRD_PARTY_NOTICES.md).
