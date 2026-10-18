"""Independent saved-output integrity/coverage audit; not a factual accuracy score."""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from lxml import html

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsrag.extraction import normalized
from newsrag.models import ArticleRecord
from newsrag.storage import RawStore, atomic_json, sha256, utc_now, writer_lock


def audit(root):
    state = json.loads((root / 'extraction/manifest.json').read_text(encoding='utf-8'))
    if not state.get('complete_scan'):
        raise ValueError('Extraction manifest scan is incomplete; do not index it')
    raw = RawStore(root)
    failures, rows = [], []
    categories, warnings = Counter(), Counter()
    for ident, entry in state['records'].items():
        try:
            path = root / entry['path']
            contents = path.read_bytes()
            if sha256(contents) != entry['sha256']:
                raise ValueError('Record checksum mismatch')
            record = ArticleRecord.model_validate_json(contents)
            source = raw.state['articles'][ident]
            if not raw.verified(source['url'])[0] or record.provenance['raw_sha256'] != source['sha256']:
                raise ValueError('Raw source changed/invalid')
            tree = html.fromstring((root / source['raw_path']).read_bytes(), parser=html.HTMLParser(encoding='utf-8'))
            title = tree.xpath('//h1[contains(@class,"post-title")]')[0].text_content().strip()
            date = datetime.fromisoformat(tree.xpath('//*[@itemprop="datePublished"]/@title')[0]).astimezone(timezone.utc)
            authors = list(dict.fromkeys(x.strip() for x in tree.xpath('//*[@itemprop="author"]//*[@itemprop="name"]/text()') if x.strip()))
            if (record.title, record.published_at, record.author) != (title, date, authors):
                raise ValueError('Title/date/byline differ from saved publisher metadata')
            nodes = tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," post-body ")]')
            spans = [normalized(t) for t in nodes[0].xpath('.//text()[not(ancestor::script) and not(ancestor::style) and not(ancestor::noscript) and not(ancestor::iframe) and not(ancestor::form)]') if len(normalized(t)) > 40]
            missing = sum(s not in normalized(record.body) for s in spans)
            if missing:
                raise ValueError(f'{missing} publisher text spans missing')
            categories[record.category] += 1
            warnings.update(record.warnings)
            rows.append({'id': ident, 'url': record.url, 'words': len(record.body.split()),
                         'reference_spans': len(spans), 'missing_spans': missing,
                         'summary_sentences': len(record.provenance['summary_sentences']),
                         'funding': record.funding is not None})
        except (ValueError, KeyError, IndexError, OSError) as error:
            failures.append({'id': ident, 'error': str(error)})
    return {'checked_at': utc_now(), 'accepted': len(state['records']), 'verified': len(rows),
            'failures': failures, 'categories': dict(categories), 'warnings': dict(warnings),
            'reference_spans': sum(r['reference_spans'] for r in rows),
            'passed': len(rows) >= 50 and not failures, 'details': rows,
            'scope': 'Schema, hashes, summary evidence, and long body-span coverage; factual accuracy requires separate manual review.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    args = parser.parse_args()
    with writer_lock(args.data_dir):
        result = audit(args.data_dir)
        atomic_json(args.data_dir / 'extraction/audit.json', result)
    print(json.dumps({k:v for k,v in result.items() if k != 'details'}, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
