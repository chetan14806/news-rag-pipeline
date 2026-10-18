# Persistent indexing checkpoint

1. [x] Review extraction handoff and choose local embedding/storage contracts.
2. [x] Install and pin embedding assets and vector database; verify local loading.
3. [x] Implement bounded source-preserving chunks and metadata.
4. [x] Implement validated input loading, persistence, replacement and interrupted-run recovery.
5. [x] Test lifecycle failures and filters using real Chroma with synthetic embeddings.
6. [x] Run a five-article real-model pilot, then all accepted records.
7. [x] Verify real paraphrase retrieval, process restart, offline rerun and replacement behavior.
8. [x] Record measured results, limits, commands and learning notes.

Completed: 81 articles / 484 chunks / 384 dimensions; 48 total tests pass. All ten development probes retrieve the intended article within the first five distinct articles among ten returned chunks (nine first, one second). Offline rerun skips all 81 without embedding/vector changes. Fresh-process results and distances match exactly. Isolated real-model shorter replacement removes six obsolete chunks. No network attempts during audits. Evidence and limitations: results/indexing_verification.md. Next: grounded query planning/answers and the eight actual assignment query evaluations.

## Contracts

- Model: sentence-transformers/all-MiniLM-L6-v2, revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41. Transformers masked mean pooling and L2 normalization, 384 dimensions; same encoder for documents and questions. No remote inference or article upload.
- Inputs: complete extraction manifest only. Validate record schema/checksum/identity/fingerprint and original raw checksum on every index/search operation. Unaccepted records are removed on synchronization; corrupt accepted inputs fail closed.
- Chunk body only, preserving exact character spans. Prefer paragraph/sentence endings, target maximum 200 wordpieces plus special tokens, about 30 wordpieces overlap. Never silently truncate; encoder rejects inputs over 256 total tokens. Title is stored as metadata, not silently added beyond the token budget.
- Chroma cosine collection persists locally. Store article identity, order, offsets, title, URL, UTC date/epoch, category and record hash as scalar metadata. Rich entities/funding remain in validated records; callers can constrain vector search with eligible article IDs. Exact complete lists must not rely on vector top-k.
- Fingerprint model assets/library versions/pooling/chunking and Chroma configuration. Incompatible configuration refuses existing storage; use a separate --index-dir for a deliberate rebuild.
- One shared project lock for indexing and search. Mark index incomplete before mutations. Prepare each replacement's vectors before upsert, remove obsolete tail chunks, then publish current manifest only after verification. This is a recoverable multi-step operation, not a database transaction. Search refuses incomplete/stale manifests. A rerun repairs interrupted writes and removes unaccepted/orphan chunks.
- Skip only when expected IDs, documents, metadata and saved vector digest agree. No embedding work or vector writes for a verified unchanged article. Operational run reports may update.
- Five-article pilots use a separate index directory. Full-index search verifies the declared selection and input hashes; pilot scope is explicit.

Primary references: [model and pooling](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), [Chroma Python client](https://docs.trychroma.com/reference/python), [collection configuration](https://docs.trychroma.com/docs/collections/configure).
