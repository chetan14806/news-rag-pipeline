"""Import the five included fixtures into a new data directory for a small local demo."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsrag.models import ArticleRecord
from newsrag.storage import atomic_bytes, atomic_json, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data-sample'))
    args = parser.parse_args()
    if args.data_dir.exists():
        raise ValueError('Choose a new data directory; existing data will not be overwritten')
    source = Path(__file__).resolve().parents[1] / 'samples'
    raw = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    extracted = json.loads((source / 'extraction-manifest.json').read_text(encoding='utf-8'))
    payloads = {}
    for ident, entry in raw['articles'].items():
        item = extracted['records'][ident]
        if entry['raw_path'] != f'raw/{ident}.html' or item['path'] != f'records/{ident}.json':
            raise ValueError('Unexpected sample path')
        html, record = (source / entry['raw_path']).read_bytes(), (source / item['path']).read_bytes()
        parsed = ArticleRecord.model_validate_json(record)
        if sha256(html) != entry['sha256'] or sha256(record) != item['sha256'] or parsed.id != ident:
            raise ValueError('Sample identity/checksum failed')
        payloads[entry['raw_path']], payloads[item['path']] = html, record
    args.data_dir.mkdir(parents=True)
    for relative, data in payloads.items():
        atomic_bytes(args.data_dir / relative, data)
    atomic_json(args.data_dir / 'manifest.json', raw)
    atomic_json(args.data_dir / 'extraction/manifest.json', extracted)
    print(f'Imported {len(raw["articles"])} fixtures into {args.data_dir}; this is not the 50+ article evaluation corpus.')


if __name__ == '__main__':
    main()
