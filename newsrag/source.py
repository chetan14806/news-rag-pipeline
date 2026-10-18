"""IndianWeb2 discovery and conservative URL identity rules."""
import re
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl, urlsplit, urlunsplit

ORIGIN = 'https://www.indianweb2.com'
FEED_URL = ORIGIN + '/feeds/posts/default?alt=rss&max-results=100'
USER_AGENT = 'ZylabsNewsRAG/0.1 (educational news research; sequential, rate-limited)'
ARTICLE_PATH = re.compile(r'^/20\d{2}/(?:0[1-9]|1[0-2])/[a-zA-Z0-9_-]+\.html$')
INCLUDED_LABELS = {'business', 'technology', 'startups', 'startup funding'}
EXCLUDED_LABELS = {'business tips', 'book', 'books'}


def source_url(url: str) -> str:
    """Reject external hosts, credentials, ports, and non-HTTPS URLs."""
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc.lower() != 'www.indianweb2.com':
        raise ValueError('URL must use HTTPS on www.indianweb2.com without credentials/port')
    return urlunsplit(('https', parts.netloc.lower(), parts.path or '/', parts.query, ''))


def article_url(url: str) -> str:
    parts = urlsplit(source_url(url))
    if not ARTICLE_PATH.fullmatch(parts.path):
        raise ValueError('Not a dated IndianWeb2 HTML article path')
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower().startswith('utm_') or key.lower() in {'fbclid', 'gclid'}:
            continue
        if key == 'm' and value == '1':
            continue  # Blogger's documented mobile representation shares the article ID.
        raise ValueError('Unknown article query parameter; refusing to guess identity')
    return urlunsplit(('https', parts.netloc, parts.path, '', ''))


def permitted_endpoint(url: str, kind: str) -> str:
    normalized = source_url(url)
    parts = urlsplit(normalized)
    if kind == 'article':
        # Redirect targets must already be canonical-shaped; no hidden alias fetches.
        if article_url(normalized) != normalized:
            raise ValueError('Article request/redirect must use its normalized URL')
    elif kind == 'feed':
        if parts.path != '/feeds/posts/default' or any(k not in {'alt', 'max-results'} for k, _ in parse_qsl(parts.query)):
            raise ValueError('Unexpected discovery endpoint')
    elif kind == 'robots':
        if parts.path != '/robots.txt' or parts.query:
            raise ValueError('Unexpected robots endpoint')
    else:
        raise ValueError('Unknown endpoint kind')
    return normalized


def discover(raw: bytes) -> tuple[list[dict], list[dict]]:
    """Parse RSS titles/labels/URLs only. Never extract article content here."""
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Discovery XML must not declare entities or a DTD')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise ValueError(f'Malformed RSS XML: {error}') from error
    if root.tag != 'rss' or root.find('channel') is None:
        raise ValueError('Expected an RSS channel')
    candidates, rejected, seen = [], [], set()
    for item in root.findall('./channel/item'):
        original = (item.findtext('link') or '').strip()
        title = (item.findtext('title') or '').strip()
        labels = [c.text.strip() for c in item.findall('category') if c.text and c.text.strip()]
        record = {'discovered_url': original, 'title': title, 'labels': labels,
                  'feed_published_at': item.findtext('pubDate')}
        try:
            url = article_url(original)
        except ValueError as error:
            rejected.append({**record, 'reason': str(error)})
            continue
        normalized_labels = {s.strip(' .').casefold() for s in labels}
        if not normalized_labels & INCLUDED_LABELS:
            rejected.append({**record, 'reason': 'Outside configured technology/business/startup labels'})
        elif normalized_labels & EXCLUDED_LABELS:
            rejected.append({**record, 'reason': 'Advice/book content excluded from news scope'})
        elif url in seen:
            rejected.append({**record, 'reason': 'Duplicate normalized article URL'})
        else:
            candidates.append({**record, 'url': url})
            seen.add(url)
    if not candidates:
        raise ValueError('RSS contains no in-scope article candidates')
    return candidates, rejected
