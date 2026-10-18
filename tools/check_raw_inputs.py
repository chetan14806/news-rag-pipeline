"""Offline HTML structure check for extraction handoff; never modifies originals."""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from lxml import html

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsrag.source import article_url
from newsrag.storage import RawStore, atomic_json, utc_now, writer_lock


def check(root: Path) -> dict:
    store = RawStore(root)
    rows = []
    for entry in store.state['articles'].values():
        issues = []
        valid, reason = store.verified(entry['url'])
        if not valid:
            rows.append({'id': entry['id'], 'url': entry['url'], 'issues': [reason]})
            continue
        tree = html.fromstring((root / entry['raw_path']).read_bytes())
        titles = tree.xpath('//h1[contains(@class,"post-title")]')
        bodies = tree.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " post-body ")]')
        dates = tree.xpath('//*[@itemprop="datePublished"]/@title')
        authors = tree.xpath('//*[@itemprop="author"]//*[@itemprop="name"]/text()')
        canonicals = tree.xpath('//link[@rel="canonical"]/@href')
        title = titles[0].text_content().strip() if titles else ''
        if not title:
            issues.append('missing_title')
        text = ''
        if bodies:
            text = re.sub(r'\s+', ' ', ' '.join(bodies[0].xpath('.//text()[not(ancestor::script) and not(ancestor::style)]'))).strip()
        if len(text) < 200:
            issues.append('missing_or_very_short_article_body')
        if not any(name.strip() for name in authors):
            issues.append('missing_author_byline')
        published_at = None
        try:
            published_at = datetime.fromisoformat(dates[0])
            if published_at.tzinfo is None:
                issues.append('publication_time_has_no_timezone')
        except (ValueError, IndexError):
            issues.append('missing_or_invalid_publication_time')
        try:
            if article_url(canonicals[0]) != entry['final_url']:
                issues.append('canonical_differs_from_final_url')
        except (ValueError, IndexError):
            issues.append('missing_or_out_of_scope_canonical')
        rows.append({'id': entry['id'], 'url': entry['url'], 'title': title,
                     'body_characters': len(text), 'published_at_source': dates[0] if dates else None,
                     'authors': [s.strip() for s in authors if s.strip()], 'issues': issues})
    return {'checked_at': utc_now(), 'articles': len(rows),
            'structurally_ready': sum(not row['issues'] for row in rows),
            'flagged': [row for row in rows if row['issues']], 'details': rows,
            'note': 'Structural HTML/metadata readiness only, not full body extraction accuracy, entity validation, fact-checking or final schema acceptance.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    args = parser.parse_args()
    root = args.data_dir.resolve()
    try:
        with writer_lock(root):
            result = check(root)
            atomic_json(root / 'input-readiness.json', result)
    except RuntimeError as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'details'}, ensure_ascii=True, indent=2))
    return 0 if result['articles'] and not result['flagged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
