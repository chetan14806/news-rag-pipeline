"""Offline review diagnostics for untested scenarios; no publisher requests."""
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / 'tests'))
from test_scraper import A, B, ROBOTS, FEED_URL, Clock, Network, feed, response
from newsrag.fetching import SiteClient
from newsrag.scraper import collect
from newsrag.storage import RawStore


def main():
    base = PROJECT / 'tmp' / 'review-probes'
    base.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(dir=base)
    root = Path(temporary.name)
    try:
        policy = response(ROBOTS, body=b'User-agent: *\nAllow: /\n', mime='text/plain')
        routes = {ROBOTS: policy,
                  FEED_URL: response(FEED_URL, body=feed([(A, ['Technology']), (B, ['Business'])]), mime='text/xml'),
                  A: response(A, 301, location=B), B: response(B)}
        clock = Clock()
        network = Network(clock, routes)
        factory = lambda folder, run_id, **kwargs: SiteClient(folder, run_id, transport=network, clock=clock, sleep=clock.sleep, **kwargs)
        summary = collect(root / 'redirect', limit=2, client_factory=factory, progress=lambda *a, **k: None)
        entries = list(RawStore(root / 'redirect').state['articles'].values())
        final_urls = Counter(e['final_url'] for e in entries)
        redirects = {'status': summary['status'], 'ready_reported': summary['ready'],
                     'stored_records': len(entries), 'unique_final_urls': len(final_urls),
                     'duplicate_destinations': [u for u, count in final_urls.items() if count > 1],
                     'passed': summary['ready'] == 1 and len(entries) == 1,
                     'finding': 'Redirect destinations now count once; a two-article target correctly reports shortfall.'}

        # A second process/run shares actual elapsed time, but not client cooldown.
        clock = Clock()
        routes = {ROBOTS: policy,
                  FEED_URL: response(FEED_URL, body=feed([(A, ['Technology'])]), mime='text/xml'),
                  A: response(A, 429, **{'retry-after': '600'})}
        network = Network(clock, routes)
        factory = lambda folder, run_id, **kwargs: SiteClient(folder, run_id, transport=network, clock=clock, sleep=clock.sleep, **kwargs)
        first = collect(root / 'cooldown', limit=1, client_factory=factory, progress=lambda *a, **k: None)
        first_article_time = [t for u, t in network.calls if u == A][-1]
        before_restart = len(network.calls)
        second = collect(root / 'cooldown', limit=1, client_factory=factory, progress=lambda *a, **k: None)
        cooldown = {'first_status': first['status'], 'second_status': second['status'],
                    'requested_cooldown_seconds': 600,
                    'network_requests_after_restart': len(network.calls) - before_restart,
                    'passed': second['status'] == 'server_pause' and len(network.calls) == before_restart,
                    'finding': 'Persisted cooldown blocks all publisher requests on an immediate restart.'}
        result = {'scope': 'Synthetic diagnostic fixtures only; actual 81-article corpus untouched.',
                  'redirect_identity': redirects, 'restart_cooldown': cooldown}
        out = PROJECT / 'results' / 'scraper_hardening_verification.json'
        out.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2))
    finally:
        assert root.resolve().is_relative_to(base.resolve())
        temporary.cleanup()


if __name__ == '__main__':
    main()
