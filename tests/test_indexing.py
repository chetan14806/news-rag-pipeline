"""Lifecycle tests use real Chroma, synthetic records and explicitly fake vectors."""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from newsrag.chunking import chunk_body
from newsrag.fetching import Response
from newsrag.indexing import (run_index, search, open_collection, index_config, checked_index,
                              load_inputs)
from newsrag.storage import RawStore, atomic_json, sha256


class TinyTokenizer:
    def __call__(self, text, **kwargs):
        spans = [(m.start(), m.end()) for m in re.finditer(r'\S+', text)]
        return {'input_ids': list(range(len(spans))), 'offset_mapping': spans}


class FakeEmbedder:
    dimension = 4
    identity = {'test_only': 'synthetic_vectors_v1', 'dimension': 4}
    tokenizer = TinyTokenizer()

    def __init__(self):
        self.calls = 0

    def encode(self, texts):
        self.calls += 1
        vectors = np.array([[1 + t.lower().count('funding'), 1 + t.lower().count('robot'),
                             1 + t.lower().count('school'), 1] for t in texts], dtype=np.float32)
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


class IndexingTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(__file__).resolve().parents[1] / 'tmp/index-tests'
        self.base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=self.base)
        self.root = Path(self.temp.name)
        self.embedder = FakeEmbedder()

    def tearDown(self):
        # Chroma caches native handles globally; stop test clients before Windows cleanup.
        from chromadb.api.shared_system_client import SharedSystemClient
        for key, system in list(SharedSystemClient._identifier_to_system.items()):
            if str(self.root) in str(key):
                system.stop()
                del SharedSystemClient._identifier_to_system[key]
        assert self.root.resolve().is_relative_to(self.base.resolve())
        self.temp.cleanup()

    def save(self, name='alpha', repeats=40, category='funding'):
        url = f'https://www.indianweb2.com/2026/10/{name}.html'
        body = ('Funding supports robot development in Bengaluru. '
                'The school will use these machines for practical lessons. ' * repeats)
        entry = RawStore(self.root).save(url, Response(url, 200, {}, body.encode()), {}, 'test', refresh=True)
        ident = entry['id']
        record = {'id': ident, 'url': url, 'title': name, 'author': [],
                  'published_at': '2026-10-15T00:00:00+00:00', 'body': body,
                  'summary': 'Funding supports robot development in Bengaluru. The school will use these machines for practical lessons.',
                  'companies': [], 'people': [], 'locations': ['Bengaluru'], 'category': category,
                  'funding': None, 'warnings': [],
                  'provenance': {'raw_sha256': entry['sha256'], 'fingerprint': 'test-' + entry['sha256'],
                                 'summary_sentences': ['Funding supports robot development in Bengaluru.',
                                                      'The school will use these machines for practical lessons.']}}
        path = self.root / f'records/{ident}.json'
        atomic_json(path, record)
        mp = self.root / 'extraction/manifest.json'
        manifest = json.loads(mp.read_text()) if mp.exists() else {'records': {}}
        manifest['complete_scan'] = True
        manifest['records'][ident] = {'path': f'records/{ident}.json', 'sha256': sha256(path.read_bytes()),
                                     'fingerprint': record['provenance']['fingerprint']}
        atomic_json(mp, manifest)
        return ident

    def run_index(self, **kwargs):
        return run_index(self.root, embedder=self.embedder, progress=lambda _: None, **kwargs)

    def search(self, **kwargs):
        return search(self.root, 'robot funding', embedder=self.embedder, **kwargs)

    def test_new_raw_page_invalidates_extraction_coverage(self):
        self.save()
        path = self.root / 'extraction/manifest.json'
        state = json.loads(path.read_text())
        state['raw_inputs'] = {k: v['sha256'] for k, v in RawStore(self.root).state['articles'].items()}
        atomic_json(path, state)
        self.run_index()
        url = 'https://www.indianweb2.com/2026/10/new-raw.html'
        RawStore(self.root).save(url, Response(url, 200, {}, b'new raw page'), {}, 'test')
        with self.assertRaisesRegex(ValueError, 'Raw collection changed'):
            self.search()

    def test_chunk_bounds_offsets_coverage_and_overlap(self):
        body = '\n'.join(' '.join(f'word{i}' for i in range(253)) + '.' for _ in range(3))
        rows = chunk_body(body, TinyTokenizer())
        covered = set()
        for row in rows:
            self.assertEqual(row['text'], body[row['start']:row['end']])
            self.assertLessEqual(row['tokens'], 200)
            covered.update(range(row['start'], row['end']))
        self.assertEqual(len(covered), len(body))
        self.assertTrue(all(a['end'] > b['start'] for a, b in zip(rows, rows[1:])))

    def test_persistence_rerun_and_shorter_replacement(self):
        ident = self.save()
        first = self.run_index()
        self.assertGreater(first['chunks'], 1)
        before = self.search()
        calls = self.embedder.calls
        rerun = self.run_index()
        self.assertEqual((rerun['written_articles'], rerun['skipped_articles']), (0, 1))
        self.assertEqual(self.embedder.calls, calls)
        self.assertEqual(before, self.search())
        self.save(repeats=3)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.search()
        changed = self.run_index()
        self.assertEqual(changed['chunks'], 1)
        self.assertEqual(changed['removed_chunks'], first['chunks'] - 1)
        self.assertTrue(all(r['metadata']['article_id'] == ident for r in self.search()))

    def test_filters_and_explicit_empty_selection(self):
        one = self.save()
        self.save('beta', category='technology')
        self.run_index()
        self.assertTrue(all(r['metadata']['article_id'] == one for r in self.search(article_ids=[one])))
        self.assertEqual(self.search(article_ids=[]), [])
        self.assertEqual(self.search(category='AI'), [])
        self.assertEqual(self.search(published_before=0), [])
        self.assertTrue(all(r['metadata']['category'] == 'technology'
                            for r in self.search(category='technology', published_from=0)))

    def test_unaccepted_article_removal_and_orphan_repair(self):
        self.save()
        self.save('beta')
        self.run_index()
        mp = self.root / 'extraction/manifest.json'
        state = json.loads(mp.read_text())
        state['records'] = {}
        atomic_json(mp, state)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.search()
        result = self.run_index()
        self.assertEqual(result['chunks'], 0)
        self.assertGreater(result['removed_chunks'], 0)
        self.assertEqual(self.search(), [])

    def test_invalid_raw_record_and_incomplete_manifest_fail_closed(self):
        ident = self.save()
        self.run_index()
        path = self.root / f'raw/{ident}.html'
        original = path.read_bytes()
        path.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'Stale or invalid'):
            self.search()
        path.write_bytes(original)
        mp = self.root / 'extraction/manifest.json'
        state = json.loads(mp.read_text())
        state['complete_scan'] = False
        atomic_json(mp, state)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.run_index()
        state['complete_scan'] = True
        atomic_json(mp, state)
        rp = self.root / f'records/{ident}.json'
        rp.write_bytes(rp.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.search()

    def test_incompatible_model_and_selection_rejected(self):
        ident = self.save()
        self.run_index()
        with self.assertRaisesRegex(ValueError, 'configuration changed'):
            self.run_index(ids=[ident])
        self.embedder.identity = {'test_only': 'changed'}
        with self.assertRaisesRegex(ValueError, 'configuration'):
            self.run_index()
        with self.assertRaisesRegex(ValueError, 'configuration'):
            self.search()

    def test_interrupted_upsert_blocks_search_then_repairs(self):
        self.save()
        self.run_index()
        self.save(repeats=3)
        from chromadb.api.models.Collection import Collection
        original = Collection.upsert
        def crash_after_write(collection, *args, **kwargs):
            original(collection, *args, **kwargs)
            raise RuntimeError('simulated interruption after vector write')
        with patch.object(Collection, 'upsert', crash_after_write):
            with self.assertRaisesRegex(RuntimeError, 'simulated'):
                self.run_index()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.search()
        repaired = self.run_index()
        self.assertEqual(repaired['chunks'], 1)
        self.assertTrue(self.search())

    def test_tampered_vector_and_extra_chunk_repaired(self):
        self.save()
        self.run_index()
        collection = open_collection(self.root / 'index', index_config(self.embedder, None), create=False)
        row = collection.get(include=['documents', 'metadatas'])
        collection.update(ids=[row['ids'][0]], embeddings=[[1., 0., 0., 0.]])
        with self.assertRaisesRegex(ValueError, 'vectors changed'):
            self.search()
        result = self.run_index()
        self.assertEqual(result['written_articles'], 1)
        collection.upsert(ids=['orphan'], documents=['orphan'], metadatas=[{'article_id': 'unknown'}],
                          embeddings=[[1., 0., 0., 0.]])
        with self.assertRaisesRegex(ValueError, 'extra/missing'):
            self.search()
        self.assertEqual(self.run_index()['removed_chunks'], 1)

    def test_bad_embedding_keeps_old_vectors_but_marks_unready(self):
        self.save()
        self.run_index()
        collection = open_collection(self.root / 'index', index_config(self.embedder, None), create=False)
        old_ids = collection.get(include=[])['ids']
        self.save(repeats=3)
        with patch.object(self.embedder, 'encode', return_value=[[float('nan')] * 4]):
            with self.assertRaisesRegex(ValueError, 'Invalid embedding'):
                self.run_index()
        self.assertEqual(collection.get(include=[])['ids'], old_ids)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.search()
        self.run_index()
        self.assertTrue(self.search())


if __name__ == '__main__':
    unittest.main()
