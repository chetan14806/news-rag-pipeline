"""Offline five-page feasibility check. Outputs are NOT full assignment records."""
import hashlib
import argparse
import json
import re
from html import unescape
from datetime import datetime, timezone
from pathlib import Path

import trafilatura
from lxml import etree, html
from pydantic import AwareDatetime, BaseModel, Field, HttpUrl


class PilotRecord(BaseModel):
    id: str
    url: HttpUrl
    title: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
    published_at: AwareDatetime
    published_at_original: str
    body: str = Field(min_length=100)
    raw_sha256: str
    raw_file: str
    extractor: str
    scope: str = 'Metadata/body feasibility only; entities, summary, category, funding not implemented.'


def normalize(text):
    # Inline links change whitespace around punctuation; compare word sequences.
    return ' '.join(re.findall(r'\w+', unescape(text).casefold()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', choices=['technode', 'indianweb2'], default='technode')
    args = parser.parse_args()
    source = Path('research/source_probe')
    dest = Path('research/pilot') / args.site
    for name in ('raw', 'records'):
        (dest / name).mkdir(parents=True, exist_ok=True)
    manifest = [json.loads(line) for line in (source / 'manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    # Deduplicate successful article fetches, not all probe endpoints.
    pattern = r'https://technode.com/2026/\d\d/\d\d/' if args.site == 'technode' else r'https://www.indianweb2.com/2026/\d\d/'
    pages = {e['url']: e for e in manifest if e.get('status') == 200 and re.match(pattern, e['url'])}
    results = []
    for url, entry in pages.items():
        raw = Path(entry['saved_path']).read_bytes()
        tree = html.fromstring(raw)
        canonical = tree.xpath('//link[@rel="canonical"]/@href')
        if canonical != [url]:
            raise ValueError(f'Unexpected canonical URL: {canonical}')
        article = None
        graph = []
        for script in tree.xpath('//script[@type="application/ld+json"]/text()'):
            value = json.loads(script)
            graph.extend(value.get('@graph', [value]) if isinstance(value, dict) else value)
        for node in graph:
            types = node.get('@type', [])
            if isinstance(types, str):
                types = [types]
            if 'Article' in types or 'NewsArticle' in types:
                article = node
                break
        if args.site == 'technode':
            if article is None:
                raise ValueError('Article metadata not found')
            authors = tree.xpath('//meta[@name="author"]/@content')
            published = article['datePublished']
            title = article['headline']
        else:
            # Blogger publishes useful metadata as microdata, not Article JSON-LD.
            authors = [normalize_name.strip() for normalize_name in tree.xpath('//*[@itemprop="author"]//*[@itemprop="name"]/text()') if normalize_name.strip()]
            published = tree.xpath('//*[@itemprop="datePublished"]/@title')[0]
            title = tree.xpath('//h1[contains(@class,"post-title")]')[0].text_content().strip()
        article_date = datetime.fromisoformat(published).astimezone(timezone.utc)
        body = trafilatura.extract(raw, url=url, include_comments=False, include_tables=False)
        if not body:
            raise ValueError('Body extraction failed')
        ident = hashlib.sha256(url.encode()).hexdigest()[:16]
        raw_file = dest / 'raw' / f'{ident}.html'
        raw_file.write_bytes(raw)
        record = PilotRecord(id=ident, url=url, title=unescape(title), authors=authors,
                             published_at=article_date, published_at_original=published,
                             body=body, raw_sha256=hashlib.sha256(raw).hexdigest(),
                             raw_file=raw_file.as_posix(), extractor=f'trafilatura {trafilatura.__version__}')
        (dest / 'records' / f'{ident}.json').write_text(record.model_dump_json(indent=2), encoding='utf-8')
        # Compare paragraph coverage to the site's article container for manual QA.
        container_class = 'entry-content' if args.site == 'technode' else 'post-body'
        containers = tree.xpath(f'//div[contains(concat(" ", normalize-space(@class), " "), " {container_class} ")]')
        site_paragraphs = [normalize(' '.join(p.itertext())) for c in containers for p in c.xpath('.//p')]
        reference_basis = 'HTML paragraphs'
        if not site_paragraphs:
            reference_basis = 'long text spans (Blogger uses line breaks instead of paragraphs)'
            site_paragraphs = [normalize(t) for c in containers for t in c.xpath('.//text()[not(ancestor::script) and not(ancestor::style)]')]
        site_paragraphs = [p for p in site_paragraphs if len(p) > 40]
        if not site_paragraphs:
            raise ValueError('No reference body blocks available for coverage comparison')
        normalized_body = normalize(body)
        missing = [p for p in site_paragraphs if p not in normalized_body]
        primary_missing = len(missing)
        if missing and args.site == 'indianweb2':
            # The generic extractor drops some newsworthy availability statements.
            # Restrict a fallback to the known article container, retaining all text.
            clean = html.fromstring(html.tostring(containers[0]))
            for element in clean.xpath('.//script|.//style|.//noscript|.//iframe|.//form'):
                element.drop_tree()
            for element in clean.iter():
                if element.tag in {'br', 'div', 'p', 'li', 'h2', 'h3', 'blockquote'}:
                    element.tail = '\n' + (element.tail or '')
            fallback = '\n'.join(re.sub(r'\s+', ' ', line).strip() for line in clean.text_content().splitlines() if line.strip())
            record = PilotRecord(**{**record.model_dump(), 'body': fallback,
                                    'extractor': 'IndianWeb2 post-body fallback (lxml); generic extraction lost body spans'})
            body = record.body
            missing = [p for p in site_paragraphs if p not in normalize(body)]
            (dest / 'records' / f'{ident}.json').write_text(record.model_dump_json(indent=2), encoding='utf-8')
        result = {'id': ident, 'url': url, 'title': record.title, 'authors': authors,
                  'published_at': article_date.isoformat(), 'words': len(body.split()),
                  'extractor': record.extractor, 'generic_missing_blocks': primary_missing,
                  'reference_basis': reference_basis,
                  'site_body_blocks': len(site_paragraphs), 'missing_site_body_blocks': missing,
                  'raw_bytes_identical': raw_file.read_bytes() == raw}
        results.append(result)
        print(json.dumps(result, ensure_ascii=False))
        print(body + '\n')
    if len(results) != 5:
        raise ValueError(f'Expected five saved article pages, got {len(results)}')
    (dest / 'verification.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    feed_file = '6fb3ac6404563097.bin' if args.site == 'technode' else '8cc3b6cd4aafd0ec.bin'
    feed = etree.fromstring((source / feed_file).read_bytes())
    candidates = [{'title': i.findtext('title'), 'url': i.findtext('link'), 'published': i.findtext('pubDate')}
                  for i in feed.findall('.//item')]
    (dest / 'feed_candidates.json').write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
