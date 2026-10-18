"""Atomic artifacts and one-writer, integrity-checked raw-page storage."""
import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def article_id(url: str) -> str:
    return sha256(url.encode('utf-8'))


def atomic_bytes(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, value: dict) -> None:
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def append_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')
        stream.flush()


@contextmanager
def writer_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    path = root / '.scrape.lock'
    try:
        stream = path.open('x', encoding='utf-8')
    except FileExistsError as error:
        raise RuntimeError(f'Scraper lock exists: {path}. Check its PID; remove only if that process is no longer running.') from error
    try:
        with stream:
            json.dump({'pid': os.getpid(), 'started_at': utc_now()}, stream)
        yield
    finally:
        path.unlink(missing_ok=True)


class RawStore:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / 'manifest.json'
        self.state = {'schema_version': 1, 'source': 'IndianWeb2', 'articles': {}}
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(self.state, dict) or self.state.get('schema_version') != 1 or self.state.get('source') != 'IndianWeb2' or not isinstance(self.state.get('articles'), dict):
                raise ValueError('Unrecognized/corrupt manifest; refusing to overwrite it')
            for ident, entry in self.state['articles'].items():
                if ident != article_id(entry['url']) or entry['raw_path'] != f'raw/{ident}.html' or entry['http_status'] != 200:
                    raise ValueError('Manifest contains invalid article identity/path/status')

    def verified(self, url: str) -> tuple[bool, str]:
        entry = self.lookup(url)
        if entry is None:
            return False, 'new'
        path = self.root / entry['raw_path']
        if not path.is_file():
            return False, 'missing_raw_file'
        body = path.read_bytes()
        if len(body) != entry['bytes'] or sha256(body) != entry['sha256']:
            return False, 'checksum_mismatch'
        return True, 'verified_existing'

    def lookup(self, url: str):
        """Resolve saved request URLs, final destinations and known redirect aliases."""
        for entry in self.state['articles'].values():
            if url in {entry['url'], entry['final_url']} or url in entry.get('alias_provenance', {}):
                return entry
        return None

    def save(self, url: str, response, discovery: dict, run_id: str, *, refresh=False) -> dict:
        existing = self.lookup(response.url) or self.lookup(url)
        if existing and existing['url'] != url and not refresh and self.verified(existing['url'])[0]:
            # Keep the verified original and its stable ID; record the new route.
            existing.setdefault('alias_provenance', {})[url] = {
                'discovery': discovery, 'redirects': response.redirects,
                'observed_at': utc_now(), 'run_id': run_id}
            self.state['updated_at'] = utc_now()
            atomic_json(self.path, self.state)
            return existing
        identity_url = existing['url'] if existing else url
        ident = article_id(identity_url)
        relative = f'raw/{ident}.html'
        entry = {'id': ident, 'url': identity_url, 'final_url': response.url,
                 'fetched_at': utc_now(), 'http_status': response.status,
                 'content_type': response.headers.get('content-type', ''),
                 'content_encoding': response.headers.get('content-encoding', 'identity'),
                 'etag': response.headers.get('etag'), 'last_modified': response.headers.get('last-modified'),
                 'bytes': len(response.body), 'sha256': sha256(response.body), 'raw_path': relative,
                 'redirects': response.redirects, 'discovery': discovery, 'run_id': run_id}
        if existing and existing.get('alias_provenance'):
            entry['alias_provenance'] = existing['alias_provenance']
        if identity_url != url:
            entry.setdefault('alias_provenance', {})[url] = {
                'discovery': discovery, 'redirects': response.redirects,
                'observed_at': utc_now(), 'run_id': run_id}
            entry['discovery'] = existing['discovery']
        atomic_bytes(self.root / relative, response.body)
        self.state['articles'][ident] = entry
        self.state['updated_at'] = utc_now()
        atomic_json(self.path, self.state)
        return entry
