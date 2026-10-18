"""Behavioral tests with fake network/time and real temporary disk artifacts."""
import copy
import json
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from newsrag.fetching import FetchError, Response, ServerPause, SiteClient, Transport
from newsrag.scraper import collect
from newsrag.source import FEED_URL, ORIGIN, USER_AGENT, article_url, discover
from newsrag.storage import RawStore, article_id, writer_lock

ROBOTS = ORIGIN + '/robots.txt'
A = ORIGIN + '/2026/10/a.html'
B = ORIGIN + '/2026/10/b.html'
C = ORIGIN + '/2026/10/c.html'
HTML = b'<!doctype html><html><body> untouched\r\n\t original &amp; bytes \xc2\xa3 </body></html>'


def response(url, status=200, body=HTML, mime='text/html', **headers):
    return Response(url, status, {'content-type': mime, **headers}, body)


def feed(items):
    content = ''.join(f'<item><title>Title</title><link>{escape(url)}</link>' + ''.join(f'<category>{escape(label)}</category>' for label in labels) + '</item>' for url, labels in items)
    return ('<rss><channel>' + content + '</channel></rss>').encode()


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Network:
    def __init__(self, clock, routes):
        self.clock, self.routes, self.calls = clock, routes, []

    def __call__(self, url):
        self.calls.append((url, self.clock()))
        value = self.routes[url]
        if isinstance(value, list):
            value = value.pop(0)
        if isinstance(value, BaseException):
            raise value
        return copy.deepcopy(value)


class ScraperTests(unittest.TestCase):
    def setUp(self):
        self.test_root = Path(__file__).resolve().parents[1] / 'tmp' / 'scraper-tests'
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=self.test_root)
        self.root = Path(self.temp.name)

    def tearDown(self):
        assert self.root.resolve().is_relative_to(self.test_root.resolve())
        self.temp.cleanup()

    def client(self, routes, **kwargs):
        clock = Clock()
        network = Network(clock, routes)
        client = SiteClient(self.root, 'test', transport=network, clock=clock, sleep=clock.sleep, **kwargs)
        return client, network

    def policy(self, text='User-agent: *\nDisallow: /search\nAllow: /\n'):
        return response(ROBOTS, body=text.encode(), mime='text/plain')

    def test_discovery_scope_aliases_dedup_and_unsafe_urls(self):
        candidates, excluded = discover(feed([
            (A + '?utm_source=test', ['Technology']), (A + '?m=1', ['Technology']),
            (B, ['Business', 'Business Tips']), (C, ['Travel']),
            ('https://other.example/2026/10/a.html', ['Business']),
            (B + '?unknown=x', ['Business'])]))
        self.assertEqual([c['url'] for c in candidates], [A])
        self.assertEqual(len(excluded), 5)
        for url in [ORIGIN + '/search?q=ai', 'http://www.indianweb2.com/2026/10/a.html', 'https://user@www.indianweb2.com/2026/10/a.html']:
            with self.assertRaises(ValueError):
                article_url(url)

    def test_bad_xml_and_no_candidates_fail_visibly(self):
        for raw in [b'<rss>', b'<!DOCTYPE rss><rss/>', feed([(A, ['Travel'])])]:
            with self.assertRaises(ValueError):
                discover(raw)

    def test_robots_longest_match_and_crawl_delay(self):
        client, network = self.client({ROBOTS: self.policy('User-agent: *\nAllow: /\nDisallow: /2026/*\nAllow: /2026/10/a.html$\nCrawl-delay: 9\n'), A: response(A)})
        client.load_robots()
        client.get(A, 'article')
        with self.assertRaises(FetchError):
            client.get(B, 'article')
        self.assertEqual(network.calls, [(ROBOTS, 0), (A, 9)])

    def test_unknown_or_invalid_robots_fails_closed(self):
        for robots in [response(ROBOTS, 403), response(ROBOTS, 404), response(ROBOTS, body=b'<html>challenge</html>')]:
            client, network = self.client({ROBOTS: robots})
            with self.assertRaises(FetchError):
                client.load_robots()
            with self.assertRaises(FetchError):
                client.get(A, 'article')
            self.assertTrue(all(url == ROBOTS for url, _ in network.calls))

    def test_request_rate_is_applied_and_visit_window_aborts(self):
        client, network = self.client({ROBOTS: self.policy('User-agent: *\nRequest-rate: 1/12\nAllow: /\n'), A: response(A)})
        client.load_robots()
        client.get(A, 'article')
        self.assertEqual(network.calls[-1][1], 12)
        client, _ = self.client({ROBOTS: self.policy('User-agent: *\nVisit-time: 0300-0400\nAllow: /\n')})
        with self.assertRaises(FetchError):
            client.load_robots()

    def test_redirect_target_checked_before_network(self):
        for target in [ORIGIN + '/search?q=ai', 'https://other.example/a', ORIGIN + '/2026/10/b.html', 'https://[']:
            client, network = self.client({ROBOTS: self.policy('User-agent: *\nDisallow: /search\nDisallow: /2026/10/b.html\n'), A: response(A, 302, location=target)})
            client.load_robots()
            with self.assertRaises(FetchError):
                client.get(A, 'article')
            self.assertEqual([url for url, _ in network.calls], [ROBOTS, A])

    def test_valid_redirect_is_paced_and_recorded(self):
        client, network = self.client({ROBOTS: self.policy(), A: response(A, 301, location=B), B: response(B)})
        client.load_robots()
        result = client.get(A, 'article')
        self.assertEqual(result.url, B)
        self.assertEqual(result.redirects, [{'url': A, 'status': 301, 'target': B}])
        self.assertEqual([t for _, t in network.calls], [0, 6, 12])

    def test_transient_retry_and_retry_after_pace_other_urls(self):
        client, network = self.client({ROBOTS: self.policy(), A: [response(A, 429, **{'retry-after': '15'}), response(A)], B: response(B)})
        client.load_robots()
        client.get(A, 'article')
        client.get(B, 'article')
        self.assertEqual([t for _, t in network.calls], [0, 6, 21, 27])

    def test_timeout_retries_are_bounded_and_backoff_grows(self):
        client, network = self.client({ROBOTS: self.policy(), A: [TimeoutError('slow')] * 4}, attempts=4)
        client.load_robots()
        with self.assertRaises(FetchError):
            client.get(A, 'article')
        self.assertEqual([t for url, t in network.calls if url == A], [6, 12, 18, 26])

    def test_denial_is_not_retried_and_long_cooldown_pauses(self):
        for status in [401, 403, 404]:
            client, network = self.client({ROBOTS: self.policy(), A: response(A, status)})
            client.load_robots()
            with self.assertRaises(FetchError):
                client.get(A, 'article')
            self.assertEqual(len(network.calls), 2)
        client, network = self.client({ROBOTS: self.policy(), A: response(A, 503, **{'retry-after': '600'})})
        client.load_robots()
        with self.assertRaises(ServerPause) as caught:
            client.get(A, 'article')
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(len(network.calls), 2)

    def test_http_date_retry_header_and_minimum_delay(self):
        client, _ = self.client({}, delay=0.1, wall_clock=lambda: datetime(2026, 10, 17, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(client.delay, 6)
        self.assertEqual(client.retry_delay('Sat, 17 Oct 2026 00:00:20 GMT', 1), 20)
        self.assertEqual(client.retry_delay('garbage', 2), 4)

    def test_persistent_rate_limit_stops_without_moving_to_other_urls(self):
        client, network = self.client({ROBOTS: self.policy(), A: response(A, 429)})
        client.load_robots()
        with self.assertRaises(ServerPause):
            client.get(A, 'article')
        self.assertEqual(len([u for u, _ in network.calls if u == A]), 3)

    def test_transport_detects_partial_and_oversized_bodies(self):
        from http.client import HTTPException
        from email.message import Message
        for declared, body, expected in [('99', b'short', HTTPException), ('999', b'', FetchError), (None, b'x' * 101, FetchError)]:
            stream = MagicMock()
            stream.headers = Message()
            if declared:
                stream.headers['Content-Length'] = declared
            stream.code = 200
            stream.read.return_value = body
            transport = Transport(25, 100)
            transport.opener = Mock()
            transport.opener.open.return_value = stream
            with self.assertRaises(expected):
                transport(A)

    def factory(self, routes, calls):
        def build(root, run_id, **kwargs):
            clock = Clock()
            network = Network(clock, routes)
            calls.append(network)
            return SiteClient(root, run_id, transport=network, clock=clock, sleep=clock.sleep, **kwargs)
        return build

    def test_raw_bytes_rerun_and_corruption_repair(self):
        routes = {ROBOTS: self.policy(), FEED_URL: response(FEED_URL, body=feed([(A, ['Technology']), (B, ['Business'])]), mime='application/rss+xml'), A: response(A), B: response(B)}
        calls = []
        run = lambda: collect(self.root, limit=2, client_factory=self.factory(routes, calls), progress=lambda *a, **k: None)
        first = run()
        self.assertEqual((first['status'], first['downloaded']), ('complete', 2))
        store = RawStore(self.root)
        path = self.root / store.state['articles'][article_id(A)]['raw_path']
        self.assertEqual(path.read_bytes(), HTML)
        before = copy.deepcopy(store.state)
        second = run()
        self.assertEqual((second['downloaded'], second['skipped_verified'], second['requests']), (0, 2, 2))
        self.assertEqual(RawStore(self.root).state, before)
        path.write_bytes(b'corruption')
        third = run()
        self.assertEqual((third['downloaded'], third['repaired'], third['skipped_verified']), (1, 1, 1))
        self.assertEqual(path.read_bytes(), HTML)
        path.unlink()
        fourth = run()
        self.assertEqual(fourth['repaired'], 1)
        self.assertEqual(len(RawStore(self.root).state['articles']), 2)

    def test_failure_isolation_and_shortfall_exit_status(self):
        calls = []
        routes = {ROBOTS: self.policy(), FEED_URL: response(FEED_URL, body=feed([(A, ['Technology']), (B, ['Business'])]), mime='text/xml'), A: response(A, 404), B: response(B)}
        result = collect(self.root, limit=2, client_factory=self.factory(routes, calls), progress=lambda *a, **k: None)
        self.assertEqual((result['status'], result['failed'], result['ready']), ('shortfall', 1, 1))
        failures = [json.loads(s) for s in (self.root / 'logs/failures.jsonl').read_text().splitlines()]
        self.assertEqual(failures[0]['http_status'], 404)
        self.assertTrue(RawStore(self.root).verified(B)[0])

    def test_discovery_only_and_invalid_article_mime(self):
        calls = []
        routes = {ROBOTS: self.policy(), FEED_URL: response(FEED_URL, body=feed([(A, ['Technology'])]), mime='text/xml'), A: response(A, mime='application/json')}
        result = collect(self.root, discover_only=True, client_factory=self.factory(routes, calls), progress=lambda *a, **k: None)
        self.assertEqual((result['status'], result['requests']), ('discovered', 2))
        result = collect(self.root, limit=1, client_factory=self.factory(routes, calls), progress=lambda *a, **k: None)
        self.assertEqual((result['status'], result['failed']), ('shortfall', 1))
        self.assertFalse((self.root / 'manifest.json').exists())

    def test_lock_and_corrupt_manifest_cannot_overwrite_existing_state(self):
        with writer_lock(self.root):
            with self.assertRaises(RuntimeError):
                with writer_lock(self.root):
                    pass
        self.assertFalse((self.root / '.scrape.lock').exists())
        path = self.root / 'manifest.json'
        for bad_state in ['{broken', '[]']:
            path.write_text(bad_state)
            calls = []
            result = collect(self.root, client_factory=self.factory({}, calls), progress=lambda *a, **k: None)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['requests'], 0)
            self.assertEqual(path.read_text(), bad_state)

    def test_failed_refresh_preserves_previous_success(self):
        routes = {ROBOTS: self.policy(), FEED_URL: response(FEED_URL, body=feed([(A, ['Technology'])]), mime='text/xml'), A: response(A)}
        calls = []
        factory = self.factory(routes, calls)
        collect(self.root, limit=1, client_factory=factory, progress=lambda *a, **k: None)
        before = copy.deepcopy(RawStore(self.root).state)
        routes[A] = response(A, 404)
        result = collect(self.root, limit=1, refresh=True, client_factory=factory, progress=lambda *a, **k: None)
        self.assertEqual((result['status'], result['failed']), ('shortfall', 1))
        self.assertEqual(RawStore(self.root).state, before)
        self.assertTrue(RawStore(self.root).verified(A)[0])

    def test_interruption_preserves_completed_pages_and_unlocks(self):
        calls = []
        routes = {ROBOTS: self.policy(), FEED_URL: response(FEED_URL, body=feed([(A, ['Technology']), (B, ['Business'])]), mime='text/xml'), A: response(A), B: KeyboardInterrupt()}
        result = collect(self.root, limit=2, client_factory=self.factory(routes, calls), progress=lambda *a, **k: None)
        self.assertEqual((result['status'], result['ready']), ('interrupted', 1))
        self.assertTrue(RawStore(self.root).verified(A)[0])
        self.assertFalse((self.root / '.scrape.lock').exists())

    def test_redirect_alias_counts_unique_destination_in_both_feed_orders(self):
        for number, items in enumerate([[(A, ['Technology']), (B, ['Business'])],
                                        [(B, ['Business']), (A, ['Technology'])]]):
            root = self.root / str(number)
            routes = {ROBOTS: self.policy(), FEED_URL: response(FEED_URL, body=feed(items), mime='text/xml'),
                      A: response(A, 301, location=B), B: response(B)}
            calls = []
            run = lambda: collect(root, limit=2, client_factory=self.factory(routes, calls), progress=lambda *a, **k: None)
            first = run()
            self.assertEqual((first['status'], first['ready'], first['manifest_articles']), ('shortfall', 1, 1))
            store = RawStore(root)
            self.assertTrue(store.verified(A)[0])
            self.assertTrue(store.verified(B)[0])
            only = next(iter(store.state['articles'].values()))
            self.assertEqual((root / only['raw_path']).read_bytes(), HTML)
            if number == 1:
                self.assertEqual(only['alias_provenance'][A]['redirects'][0]['target'], B)
            before = copy.deepcopy(store.state)
            second = run()
            self.assertEqual((second['ready'], second['downloaded'], second['requests']), (1, 0, 2))
            self.assertEqual(RawStore(root).state, before)

    def test_redirect_alias_does_not_prevent_filling_target_with_other_article(self):
        routes = {ROBOTS: self.policy(), FEED_URL: response(FEED_URL, body=feed([
            (A, ['Technology']), (B, ['Business']), (C, ['Technology'])]), mime='text/xml'),
            A: response(A, 301, location=B), B: response(B), C: response(C)}
        result = collect(self.root, limit=2, client_factory=self.factory(routes, []), progress=lambda *a, **k: None)
        self.assertEqual((result['status'], result['ready'], result['manifest_articles']), ('complete', 2, 2))

    def test_alias_refresh_and_missing_raw_repair_preserve_identity(self):
        store = RawStore(self.root)
        original = store.save(B, response(B), {'labels': ['Business']}, 'first')
        redirected = response(B, body=b'refreshed content')
        redirected.redirects = [{'url': A, 'status': 301, 'target': B}]
        refreshed = store.save(A, redirected, {'labels': ['Technology']}, 'refresh', refresh=True)
        self.assertEqual(refreshed['id'], original['id'])
        self.assertEqual((self.root / refreshed['raw_path']).read_bytes(), b'refreshed content')
        (self.root / refreshed['raw_path']).unlink()
        repaired = store.save(A, redirected, {'labels': ['Technology']}, 'repair')
        self.assertEqual(repaired['id'], original['id'])
        reloaded = RawStore(self.root)
        self.assertTrue(reloaded.verified(A)[0])
        self.assertTrue(reloaded.verified(B)[0])
        self.assertEqual(len(reloaded.state['articles']), 1)

    def test_retry_after_survives_restart_then_expires(self):
        for index, header in enumerate(['600', 'Sat, 17 Oct 2026 00:10:06 GMT', '20']):
            root = self.root / str(index)
            clock = Clock()
            wall = lambda: datetime(2026, 10, 17, tzinfo=timezone.utc) + timedelta(seconds=clock())
            network = Network(clock, {ROBOTS: self.policy(), A: response(A, 429, **{'retry-after': header})})
            def client():
                return SiteClient(root, 'cooldown', attempts=1, transport=network, clock=clock,
                                  sleep=clock.sleep, wall_clock=wall)
            first = client()
            first.load_robots()
            with self.assertRaises(ServerPause):
                first.get(A, 'article')
            calls_before = len(network.calls)
            with self.assertRaises(ServerPause):
                client().load_robots()
            self.assertEqual(len(network.calls), calls_before)
            persisted = json.loads((root / 'policies/cooldown.json').read_text())
            clock.sleep((datetime.fromisoformat(persisted['resume_after']) - wall()).total_seconds())
            resumed = client()
            resumed.load_robots()
            network.routes[A] = response(A)
            self.assertEqual(resumed.get(A, 'article').status, 200)

    def test_corrupt_cooldown_fails_before_network(self):
        folder = self.root / 'policies'
        folder.mkdir()
        for raw in ['{broken', '[]', '{"origin":"https://other.example"}',
                    json.dumps({'origin': ORIGIN, 'resume_after': '2026-10-17T00:00:00'})]:
            (folder / 'cooldown.json').write_text(raw)
            client, network = self.client({})
            with self.assertRaises((ValueError, KeyError)):
                client.load_robots()
            self.assertEqual(network.calls, [])


if __name__ == '__main__':
    unittest.main()
