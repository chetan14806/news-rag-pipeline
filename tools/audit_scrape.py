"""Offline raw-corpus integrity and discovery audit; not article extraction."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsrag.source import article_url
from newsrag.storage import RawStore, atomic_json, utc_now, writer_lock


def audit(root: Path) -> dict:
    store = RawStore(root)
    entries = list(store.state['articles'].values())
    invalid = []
    for entry in entries:
        valid, reason = store.verified(entry['url'])
        if not valid:
            invalid.append({'id': entry['id'], 'reason': reason})
        if article_url(entry['url']) != entry['url']:
            invalid.append({'id': entry['id'], 'reason': 'non-normalized article URL'})
    finals = Counter(e['final_url'] for e in entries)
    duplicate_final_urls = [url for url, count in finals.items() if count > 1]
    referenced = {e['raw_path'] for e in entries}
    orphan_files = [p.relative_to(root).as_posix() for p in (root / 'raw').glob('*.html') if p.relative_to(root).as_posix() not in referenced]
    labels = Counter(label for e in entries for label in e['discovery']['labels'])
    result = {'checked_at': utc_now(), 'manifest_articles': len(entries),
              'verified_articles': len(entries) - len({e['id'] for e in invalid}),
              'total_raw_bytes': sum(e['bytes'] for e in entries),
              'invalid': invalid, 'duplicate_final_urls': duplicate_final_urls,
              'orphan_raw_files': orphan_files, 'labels': dict(labels.most_common()),
              'note': 'Raw transport/storage integrity only; not full extraction or event/category accuracy.'}
    result['passed'] = bool(entries) and not invalid and not duplicate_final_urls and not orphan_files
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    args = parser.parse_args()
    root = args.data_dir.resolve()
    try:
        with writer_lock(root):
            result = audit(root)
            atomic_json(root / 'integrity-audit.json', result)
    except RuntimeError as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'labels'}, ensure_ascii=True, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
