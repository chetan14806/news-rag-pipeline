"""Run discovery and raw collection without extracting article contents."""
from pathlib import Path

from newsrag.fetching import FetchError, ServerPause, SiteClient
from newsrag.source import FEED_URL, USER_AGENT, discover
from newsrag.storage import RawStore, append_json, article_id, atomic_bytes, atomic_json, sha256, utc_now, writer_lock


def collect(root: Path, *, limit=80, delay=6.0, timeout=25.0, attempts=3,
            discover_only=False, refresh=False, client_factory=SiteClient, progress=print) -> dict:
    run_id = utc_now().replace(':', '').replace('.', '').replace('+', '-')
    summary = {'schema_version': 1, 'run_id': run_id, 'started_at': utc_now(),
               'source': 'IndianWeb2', 'feed_url': FEED_URL, 'user_agent': USER_AGENT,
               'target': limit, 'downloaded': 0, 'skipped_verified': 0, 'repaired': 0,
               'failed': 0, 'ready': 0, 'status': 'starting', 'refresh': refresh,
               'discover_only': discover_only}
    with writer_lock(root):
        client = client_factory(root, run_id, delay=delay, timeout=timeout, attempts=attempts)
        try:
            store = RawStore(root)
            progress('Checking fresh robots policy...', flush=True)
            summary['robots'] = client.load_robots()
            progress(f'Discovering RSS links; request spacing >= {client.delay:g}s...', flush=True)
            feed = client.get(FEED_URL, 'feed')
            if feed.headers.get('content-type', '').split(';')[0].strip().lower() not in {
                'application/rss+xml', 'application/xml', 'text/xml'}:
                raise FetchError('Discovery response is not XML/RSS')
            feed_path = f'discovery/feed-{run_id}.xml'
            atomic_bytes(root / feed_path, feed.body)
            candidates, excluded = discover(feed.body)
            discovery = {'schema_version': 1, 'run_id': run_id, 'fetched_at': utc_now(),
                         'feed_url': FEED_URL, 'final_url': feed.url, 'raw_path': feed_path,
                         'sha256': sha256(feed.body), 'candidates': candidates, 'excluded': excluded}
            atomic_json(root / 'discovery' / f'candidates-{run_id}.json', discovery)
            atomic_json(root / 'discovery' / 'latest.json', discovery)
            summary.update(candidates=len(candidates), excluded=len(excluded), discovery_path=f'discovery/candidates-{run_id}.json')
            progress(f'Found {len(candidates)} eligible URLs; recorded {len(excluded)} exclusions.', flush=True)
            if discover_only:
                summary['status'] = 'discovered'
            else:
                ready_destinations = set()
                for candidate in candidates:
                    if summary['ready'] >= limit:
                        break
                    url = candidate['url']
                    valid, integrity = store.verified(url)
                    if valid and not refresh:
                        summary['skipped_verified'] += 1
                        ready_destinations.add(store.lookup(url)['final_url'])
                        summary['ready'] = len(ready_destinations)
                        progress(f"[{summary['ready']}/{limit}] skip verified {url}", flush=True)
                        continue
                    try:
                        response = client.get(url, 'article')
                        mime = response.headers.get('content-type', '').split(';')[0].strip().lower()
                        if mime not in {'text/html', 'application/xhtml+xml'} or not response.body.strip():
                            raise FetchError('Article response is empty or not HTML', response.status)
                        # Content inspection/cleaning intentionally belongs to extract.py.
                        provenance = {**candidate, 'feed_url': FEED_URL, 'feed_snapshot': feed_path,
                                      'feed_fetched_at': discovery['fetched_at']}
                        entry = store.save(url, response, provenance, run_id, refresh=refresh)
                        summary['downloaded'] += 1
                        ready_destinations.add(entry['final_url'])
                        summary['ready'] = len(ready_destinations)
                        if integrity in {'missing_raw_file', 'checksum_mismatch'}:
                            summary['repaired'] += 1
                        append_json(root / 'logs' / 'articles.jsonl', {
                            'run_id': run_id, 'at': utc_now(), 'url': url, 'id': entry['id'],
                            'outcome': 'saved', 'prior_integrity': integrity, 'sha256': entry['sha256']})
                        progress(f"[{summary['ready']}/{limit}] saved {entry['bytes']} bytes {url}", flush=True)
                    except FetchError as error:
                        summary['failed'] += 1
                        append_json(root / 'logs' / 'failures.jsonl', {
                            'run_id': run_id, 'at': utc_now(), 'id': article_id(url), 'url': url,
                            'http_status': error.status, 'error': str(error), 'prior_integrity': integrity})
                        progress(f'Failed {url}: {error}', flush=True)
                        if isinstance(error, ServerPause):
                            raise
                summary['manifest_articles'] = len(store.state['articles'])
                summary['status'] = 'complete' if summary['ready'] >= limit else 'shortfall'
        except KeyboardInterrupt:
            summary.update(status='interrupted', error='Interrupted; completed artifacts retained')
        except ServerPause as error:
            summary.update(status='server_pause', error=str(error))
        except (FetchError, ValueError, KeyError, TypeError, OSError) as error:
            summary.update(status='failed', error=str(error))
        finally:
            summary.update(finished_at=utc_now(), requests=client.request_count)
            atomic_json(root / 'runs' / f'{run_id}.json', summary)
            atomic_json(root / 'runs' / 'latest.json', summary)
    return summary
