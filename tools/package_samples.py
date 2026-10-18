"""Prepare and verify five byte-identical assignment sample pairs locally."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsrag.models import ArticleRecord
from newsrag.storage import atomic_bytes, atomic_json, sha256, writer_lock


def main():
    root = Path('data')
    with writer_lock(root):
        ids = json.loads((root / 'samples/manifest.json').read_text())['ids']
        assert len(ids) == len(set(ids)) == 5
        raw = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        extraction = json.loads((root / 'extraction/manifest.json').read_text(encoding='utf-8'))
        assert extraction['complete_scan']
        rows = []
        for ident in ids:
            entry, item = raw['articles'][ident], extraction['records'][ident]
            original = (root / entry['raw_path']).read_bytes()
            content = (root / item['path']).read_bytes()
            record = ArticleRecord.model_validate_json(content)
            assert record.id == ident and sha256(original) == entry['sha256'] and sha256(content) == item['sha256']
            atomic_bytes(Path('samples') / entry['raw_path'], original)
            atomic_bytes(Path('samples') / item['path'], content)
            rows.append({'id': ident, 'title': record.title, 'url': record.url,
                         'raw_sha256': sha256(original), 'record_sha256': sha256(content),
                         'raw_bytes': len(original), 'record_bytes': len(content)})
        raw['articles'] = {ident: raw['articles'][ident] for ident in ids}
        extraction['records'] = {ident: extraction['records'][ident] for ident in ids}
        atomic_json(Path('samples/manifest.json'), raw)
        atomic_json(Path('samples/extraction-manifest.json'), extraction)
        atomic_json(Path('results/submission_sample_verification.json'),
                    {'passed': True, 'pairs': rows, 'count': 5, 'bytes': sum(r['raw_bytes']+r['record_bytes'] for r in rows)})
    print('Verified and packaged five original HTML/full-schema JSON pairs in samples/.')


if __name__ == '__main__':
    main()
