"""Persistent Chroma synchronization and guarded semantic retrieval."""
import json
from importlib.metadata import version
from pathlib import Path

import numpy as np

from newsrag.chunking import CHUNK_CONFIG, chunk_body
from newsrag.embeddings import LocalEmbedder
from newsrag.models import ArticleRecord
from newsrag.storage import RawStore, atomic_json, append_json, sha256, utc_now, writer_lock

COLLECTION = 'news_chunks'


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode())


def load_inputs(root, ids=None):
    manifest = json.loads((root / 'extraction/manifest.json').read_text(encoding='utf-8'))
    if manifest.get('complete_scan') is not True:
        raise ValueError('Extraction scan is incomplete; finish extraction first')
    store = RawStore(root)
    selected = set(ids) if ids is not None else set(manifest['records'])
    if selected - set(manifest['records']):
        raise ValueError('Requested IDs are not currently accepted')
    records, hashes = {}, {}
    for ident in sorted(selected):
        item = manifest['records'][ident]
        if item['path'] != f'records/{ident}.json':
            raise ValueError('Unexpected accepted record path')
        content = (root / item['path']).read_bytes()
        if sha256(content) != item['sha256']:
            raise ValueError(f'Accepted record checksum mismatch: {ident}')
        record = ArticleRecord.model_validate_json(content)
        entry = store.state['articles'].get(ident)
        if (not entry or record.id != ident or record.url != entry['final_url'] or
                record.provenance.get('fingerprint') != item['fingerprint'] or
                record.provenance.get('raw_sha256') != entry['sha256'] or
                not store.verified(entry['url'])[0]):
            raise ValueError(f'Stale or invalid original/extraction identity: {ident}')
        records[ident], hashes[ident] = record, item['sha256']
    return records, hashes


def index_config(embedder, ids):
    return {'version': 1, 'embedding': embedder.identity, 'chunking': CHUNK_CONFIG,
            'chromadb': version('chromadb'), 'metric': 'cosine',
            'selection': sorted(set(ids)) if ids is not None else None}


def open_collection(folder, config, *, create):
    import chromadb
    from chromadb.config import Settings
    client = chromadb.PersistentClient(path=str(folder / 'chroma'), settings=Settings(anonymized_telemetry=False))
    if create:
        collection = client.get_or_create_collection(COLLECTION, embedding_function=None,
                        metadata={'config_sha256': digest(config)},
                        configuration={'hnsw': {'space': 'cosine'}})
    else:
        collection = client.get_collection(COLLECTION, embedding_function=None)
    if collection.metadata.get('config_sha256') != digest(config):
        raise ValueError('Stored collection configuration differs; use a new --index-dir')
    return collection


def expected_chunks(record, record_hash, tokenizer):
    chunks = chunk_body(record.body, tokenizer)
    rows = []
    for order, chunk in enumerate(chunks):
        rows.append({'id': f'{record.id}:{order:05d}', 'document': chunk['text'],
                     'metadata': {'article_id': record.id, 'chunk_order': order,
                                  'start': chunk['start'], 'end': chunk['end'], 'tokens': chunk['tokens'],
                                  'title': record.title, 'url': record.url,
                                  'published_at': record.published_at.isoformat(),
                                  'published_epoch': int(record.published_at.timestamp()),
                                  'category': record.category, 'record_sha256': record_hash}})
    return rows


def validate_vectors(vectors, count, dimension):
    values = np.asarray(vectors, dtype=np.float32)
    if (values.shape != (count, dimension) or not np.isfinite(values).all() or
            not np.allclose(np.linalg.norm(values, axis=1), 1, atol=0.001)):
        raise ValueError('Invalid embedding dimensions, values or normalization')
    return values


def verify_rows(collection, rows, dimension):
    actual = collection.get(where={'article_id': rows[0]['metadata']['article_id']},
                            include=['documents', 'metadatas', 'embeddings'])
    if set(actual['ids']) != {r['id'] for r in rows}:
        raise ValueError('Missing or obsolete article chunks')
    positions = {ident: i for i, ident in enumerate(actual['ids'])}
    values = []
    for row in rows:
        i = positions[row['id']]
        if actual['documents'][i] != row['document'] or actual['metadatas'][i] != row['metadata']:
            raise ValueError('Stored chunk text/metadata differs from accepted input')
        values.append(actual['embeddings'][i])
    vectors = validate_vectors(values, len(rows), dimension)
    return sha256(vectors.astype('<f4').tobytes())


def run_index(root: Path, *, index_dir=None, ids=None, embedder=None, progress=print):
    root = Path(root)
    folder = Path(index_dir) if index_dir else root / 'index'
    summary = {'run_id': utc_now().replace(':', '').replace('.', '').replace('+', '-'),
               'started_at': utc_now(), 'written_articles': 0, 'skipped_articles': 0,
               'embedded_chunks': 0, 'removed_chunks': 0}
    with writer_lock(root):
        records, hashes = load_inputs(root, ids)
        embedder = embedder or LocalEmbedder(root / 'models/embeddings')
        config = index_config(embedder, ids)
        path = folder / 'manifest.json'
        previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if previous and previous.get('config') != config:
            raise ValueError('Index configuration changed; build into a new --index-dir')
        collection = open_collection(folder, config, create=True)
        state = {'config': config, 'complete': False, 'inputs': hashes,
                 'articles': dict(previous.get('articles', {})), 'run_id': summary['run_id']}
        atomic_json(path, state)
        try:
            desired_ids = set()
            for ident, record in records.items():
                rows = expected_chunks(record, hashes[ident], embedder.tokenizer)
                desired_ids.update(row['id'] for row in rows)
                old = previous.get('articles', {}).get(ident)
                valid = False
                if old and old['record_sha256'] == hashes[ident]:
                    try:
                        valid = verify_rows(collection, rows, embedder.dimension) == old['vectors_sha256']
                    except ValueError:
                        pass
                if valid:
                    summary['skipped_articles'] += 1
                else:
                    # Compute and validate every replacement vector before mutating this article.
                    vectors = validate_vectors(embedder.encode([r['document'] for r in rows]),
                                               len(rows), embedder.dimension)
                    old_ids = set(collection.get(where={'article_id': ident}, include=[])['ids'])
                    for start in range(0, len(rows), 128):
                        batch = rows[start:start + 128]
                        collection.upsert(ids=[r['id'] for r in batch],
                                          documents=[r['document'] for r in batch],
                                          metadatas=[r['metadata'] for r in batch],
                                          embeddings=vectors[start:start + 128].tolist())
                    obsolete = old_ids - {r['id'] for r in rows}
                    if obsolete:
                        collection.delete(ids=sorted(obsolete))
                        summary['removed_chunks'] += len(obsolete)
                    vector_hash = verify_rows(collection, rows, embedder.dimension)
                    state['articles'][ident] = {'record_sha256': hashes[ident],
                                               'chunks': len(rows), 'vectors_sha256': vector_hash}
                    summary['written_articles'] += 1
                    summary['embedded_chunks'] += len(rows)
                atomic_json(path, state)
                progress(f"[{summary['written_articles'] + summary['skipped_articles']}/{len(records)}] {record.title}")
            orphan_ids = set(collection.get(include=[])['ids']) - desired_ids
            for start in range(0, len(orphan_ids), 128):
                collection.delete(ids=sorted(orphan_ids)[start:start + 128])
            summary['removed_chunks'] += len(orphan_ids)
            state['articles'] = {ident: state['articles'][ident] for ident in records}
            if collection.count() != len(desired_ids):
                raise ValueError('Final index count differs from expected chunks')
            state.update(complete=True, chunks=len(desired_ids), updated_at=utc_now())
            atomic_json(path, state)
            summary.update(status='complete', articles=len(records), chunks=len(desired_ids))
        except Exception as error:
            summary.update(status='failed', error=str(error))
            append_json(folder / 'errors.jsonl', summary)
            raise
        finally:
            summary['finished_at'] = utc_now()
            atomic_json(folder / 'runs' / f"{summary['run_id']}.json", summary)
            atomic_json(folder / 'latest.json', summary)
    return summary


def checked_index(root, folder, embedder):
    state = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if not state.get('complete'):
        raise ValueError('Index is incomplete; rerun index.py to repair it')
    config = index_config(embedder, state['config']['selection'])
    if state['config'] != config:
        raise ValueError('Embedding/chunking configuration mismatch')
    records, hashes = load_inputs(root, state['config']['selection'])
    if hashes != state['inputs']:
        raise ValueError('Index is stale; run index.py after extraction changes')
    collection = open_collection(folder, config, create=False)
    count = 0
    for ident, record in records.items():
        rows = expected_chunks(record, hashes[ident], embedder.tokenizer)
        if verify_rows(collection, rows, embedder.dimension) != state['articles'][ident]['vectors_sha256']:
            raise ValueError('Stored vectors changed; rerun index.py to repair')
        count += len(rows)
    if collection.count() != count or state['chunks'] != count:
        raise ValueError('Unexpected extra/missing chunks; rerun index.py')
    return collection, state


def search(root, question, *, index_dir=None, top_k=5, article_ids=None,
           category=None, published_from=None, published_before=None, embedder=None):
    if not question.strip() or not 1 <= top_k <= 100:
        raise ValueError('Provide nonempty text and top_k between 1 and 100')
    root = Path(root)
    folder = Path(index_dir) if index_dir else root / 'index'
    with writer_lock(root):
        embedder = embedder or LocalEmbedder(root / 'models/embeddings')
        collection, state = checked_index(root, folder, embedder)
        clauses = []
        if article_ids is not None:
            eligible = sorted(set(article_ids) & set(state['inputs']))
            if not eligible:
                return []
            clauses.append({'article_id': {'$in': eligible}})
        if category is not None:
            clauses.append({'category': category})
        if published_from is not None:
            clauses.append({'published_epoch': {'$gte': published_from}})
        if published_before is not None:
            clauses.append({'published_epoch': {'$lt': published_before}})
        where = {'$and': clauses} if len(clauses) > 1 else clauses[0] if clauses else None
        if not state['chunks']:
            return []
        vector = validate_vectors(embedder.encode([question]), 1, embedder.dimension)
        result = collection.query(query_embeddings=vector.tolist(), n_results=min(top_k, state['chunks']),
                                  where=where, include=['documents', 'metadatas', 'distances'])
        return [{'chunk_id': ident, 'text': result['documents'][0][i],
                 'metadata': result['metadatas'][0][i], 'cosine_distance': result['distances'][0][i]}
                for i, ident in enumerate(result['ids'][0])]
