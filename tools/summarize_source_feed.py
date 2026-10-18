"""Offline keyword screening; counts are candidates, not validated extractions."""
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from lxml import etree, html


def main():
    feed = Path('research/source_probe/8cc3b6cd4aafd0ec.bin')
    root = etree.fromstring(feed.read_bytes())
    reference = datetime(2026, 10, 17, 6, 42, 36, tzinfo=timezone.utc)
    items = root.findall('.//item')
    report = {'source': 'IndianWeb2', 'feed_url': 'https://www.indianweb2.com/feeds/posts/default?alt=rss&max-results=100',
              'reference_time': reference.isoformat(), 'items': len(items),
              'unique_urls': len({i.findtext('link') for i in items}),
              'oldest': min(parsedate_to_datetime(i.findtext('pubDate')) for i in items).isoformat(),
              'newest': max(parsedate_to_datetime(i.findtext('pubDate')) for i in items).isoformat(),
              'keyword_screening': {},
              'limitations': 'Title plus RSS description keyword screening only. Categories, funding events, layoffs and entities still need article-level validation; a match is not proof of the event.'}
    for label, pattern in {'funding': r'raises|funding|raised', 'ai': r'\bAI\b',
                           'bengaluru': r'\b(?:bengaluru|bangalore)\b', 'revenue': r'revenue',
                           'layoffs': r'layoff|lays off|job cuts'}.items():
        matches = []
        for item in items:
            text = (item.findtext('title') or '') + ' ' + html.fromstring('<div>' + (item.findtext('description') or '') + '</div>').text_content()
            if re.search(pattern, text, re.I):
                matches.append(item)
        report['keyword_screening'][label] = {'matches': len(matches),
            'published_last_7_days': sum(reference - timedelta(days=7) <= parsedate_to_datetime(i.findtext('pubDate')) <= reference for i in matches),
            'examples': [{'title': i.findtext('title'), 'url': i.findtext('link')} for i in matches[:4]]}
    Path('research/indianweb2_feed_coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
