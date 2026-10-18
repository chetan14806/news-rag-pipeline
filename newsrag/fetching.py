"""Same-source HTTP with explicit redirects, robots checks and bounded retries."""
import math
import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from urllib.parse import urljoin

from protego import Protego

from newsrag.source import ORIGIN, USER_AGENT, permitted_endpoint
from newsrag.storage import append_json, atomic_bytes, atomic_json, sha256, utc_now


class FetchError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class ServerPause(FetchError):
    """Stop the batch rather than violate a long server cooldown."""


@dataclass
class Response:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes
    redirects: list[dict] = field(default_factory=list)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Transport:
    def __init__(self, timeout: float, max_bytes: int):
        self.opener = urllib.request.build_opener(NoRedirect())
        self.timeout, self.max_bytes = timeout, max_bytes

    def __call__(self, url: str) -> Response:
        request = urllib.request.Request(url, headers={
            'User-Agent': USER_AGENT, 'Accept-Encoding': 'identity',
            'Accept': 'text/html,application/xhtml+xml,application/rss+xml,application/xml,text/plain;q=0.9'})
        try:
            stream = self.opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            # Error/redirect responses also need closure, audit, and retry handling.
            stream = error
        with stream:
            declared = stream.headers.get('Content-Length')
            if declared and declared.isdigit() and int(declared) > self.max_bytes:
                raise FetchError('Declared response size exceeds configured byte limit', stream.code)
            body = stream.read(self.max_bytes + 1)
            if len(body) > self.max_bytes:
                raise FetchError('Response exceeds configured byte limit', stream.code)
            if declared and declared.isdigit() and len(body) != int(declared):
                raise HTTPException('Incomplete response body: Content-Length mismatch')
            return Response(url, stream.code, {k.lower(): v for k, v in stream.headers.items()}, body)


class SiteClient:
    def __init__(self, root, run_id: str, delay=6.0, timeout=25.0, attempts=3,
                 max_bytes=8 * 1024 * 1024, transport=None, clock=time.monotonic,
                 sleep=time.sleep, wall_clock=None):
        self.root, self.run_id = root, run_id
        self.delay, self.attempts = max(6.0, delay), attempts
        self.clock, self.sleep = clock, sleep
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self.transport = transport or Transport(timeout, max_bytes)
        self.next_request = 0.0
        self.robots = None
        self.robots_snapshot = None
        self.request_count = 0
        self.cooldown_checked = False

    def restore_cooldown(self):
        """Check durable source-wide cooldown before even robots/feed requests."""
        if self.cooldown_checked:
            return
        path = self.root / 'policies' / 'cooldown.json'
        if path.exists():
            state = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(state, dict) or state.get('origin') != ORIGIN:
                raise ValueError('Invalid source cooldown state; refusing network requests')
            resume = datetime.fromisoformat(state['resume_after'])
            if resume.tzinfo is None:
                raise ValueError('Cooldown timestamp must include a timezone')
            if resume > self.wall_clock():
                raise ServerPause(f"Source cooldown active until {resume.isoformat()}; batch paused", state.get('http_status'))
        self.cooldown_checked = True

    def persist_cooldown(self, seconds, status=None):
        if seconds > 0:
            atomic_json(self.root / 'policies' / 'cooldown.json', {
                'origin': ORIGIN, 'resume_after': (self.wall_clock() + timedelta(seconds=seconds)).isoformat(),
                'http_status': status, 'run_id': self.run_id})

    def wait(self):
        remaining = self.next_request - self.clock()
        if remaining > 0:
            self.sleep(remaining)
        self.next_request = self.clock() + self.delay

    def audit(self, **entry):
        append_json(self.root / 'logs' / 'requests.jsonl',
                    {'run_id': self.run_id, 'at': utc_now(), **entry})

    def retry_delay(self, header: str | None, attempt: int) -> float:
        backoff = 2.0 ** attempt
        if header:
            try:
                seconds = float(header)
                if not math.isfinite(seconds):
                    raise ValueError('nonfinite Retry-After')
            except ValueError:
                try:
                    stamp = parsedate_to_datetime(header)
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=timezone.utc)
                    seconds = (stamp - self.wall_clock()).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    seconds = 0
            if seconds > 60:
                self.persist_cooldown(seconds)
                self.next_request = max(self.next_request, self.clock() + seconds)
                raise ServerPause(f'Server requests {seconds:.0f}s cooldown; batch paused, retry later', 429)
            self.persist_cooldown(seconds)
            backoff = max(backoff, seconds)
        return backoff

    def _request(self, url: str) -> Response:
        self.restore_cooldown()
        for attempt in range(1, self.attempts + 1):
            self.wait()
            self.request_count += 1
            started_at, started_clock = utc_now(), self.clock()
            try:
                response = self.transport(url)
            except FetchError as error:
                self.audit(url=url, attempt=attempt, status=error.status,
                           error=str(error), outcome='invalid_response', started_at=started_at,
                           elapsed_seconds=self.clock() - started_clock)
                raise
            except (urllib.error.URLError, TimeoutError, socket.timeout, HTTPException, ConnectionError, OSError) as error:
                self.audit(url=url, attempt=attempt, error=str(error), outcome='network_error',
                           started_at=started_at, elapsed_seconds=self.clock() - started_clock)
                if attempt == self.attempts:
                    raise FetchError(f'Network failure after {attempt} attempts: {error}') from error
                self.next_request = max(self.next_request, self.clock() + 2.0 ** attempt)
                continue
            self.audit(url=url, attempt=attempt, status=response.status,
                       bytes=len(response.body), outcome='response', started_at=started_at,
                       elapsed_seconds=self.clock() - started_clock)
            if response.status in {408, 429, 500, 502, 503, 504}:
                # Apply server cooldown even on the last attempt, before another URL.
                try:
                    pause = self.retry_delay(response.headers.get('retry-after'), attempt)
                except ServerPause as error:
                    error.status = response.status
                    raise
                self.next_request = max(self.next_request, self.clock() + pause)
                if attempt < self.attempts:
                    continue
                if response.status in {429, 503}:
                    self.persist_cooldown(pause, response.status)
                    raise ServerPause(f'HTTP {response.status} persists after {attempt} attempts; batch paused', response.status)
            return response
        raise FetchError('Retry loop exhausted')

    def get(self, url: str, kind: str) -> Response:
        redirects = []
        for _ in range(6):
            try:
                url = permitted_endpoint(url, kind)
            except ValueError as error:
                raise FetchError(str(error)) from error
            if kind != 'robots':
                if self.robots is None or not self.robots.can_fetch(url, USER_AGENT):
                    raise FetchError('robots.txt disallows this request')
            response = self._request(url)
            if response.status in {301, 302, 303, 307, 308}:
                try:
                    target = urljoin(url, response.headers.get('location', ''))
                except ValueError as error:
                    raise FetchError('Malformed redirect target', response.status) from error
                if not response.headers.get('location') or target == url:
                    raise FetchError('Missing/cyclic redirect target', response.status)
                redirects.append({'url': url, 'status': response.status, 'target': target})
                url = target
                continue  # Target scope and robots are checked before its request.
            response.redirects = redirects
            if response.status != 200:
                raise FetchError(f'HTTP {response.status}', response.status)
            if response.headers.get('content-encoding', 'identity').lower() not in {'', 'identity'}:
                raise FetchError('Server ignored identity encoding; refusing an encoded HTML artifact')
            response.url = url
            return response
        raise FetchError('Too many redirects')

    def load_robots(self):
        # Missing or inaccessible policy is deliberately not interpreted as consent.
        response = self.get(ORIGIN + '/robots.txt', 'robots')
        mime = response.headers.get('content-type', '').split(';')[0].strip().lower()
        text = response.body.decode('utf-8-sig', errors='replace')
        if mime != 'text/plain' or not any(line.strip().lower().startswith('user-agent:') for line in text.splitlines()):
            raise FetchError('robots.txt is not a recognizable plain-text policy')
        self.robots = Protego.parse(text)
        extra = self.robots.crawl_delay(USER_AGENT) or 0
        rate = self.robots.request_rate(USER_AGENT)
        if rate:
            if rate.start_time is not None or rate.end_time is not None:
                raise FetchError('Time-window Request-rate needs manual scheduling; no crawl started')
            extra = max(extra, rate.seconds / rate.requests)
        if self.robots.visit_time(USER_AGENT) is not None:
            raise FetchError('Visit-time policy needs manual scheduling; no crawl started')
        self.delay = max(self.delay, extra)
        self.next_request = max(self.next_request, self.clock() + self.delay)
        relative = f'policies/robots-{self.run_id}.txt'
        atomic_bytes(self.root / relative, response.body)
        self.robots_snapshot = {'url': response.url, 'checked_at': utc_now(), 'raw_path': relative,
                                'sha256': sha256(response.body), 'user_agent': USER_AGENT,
                                'effective_delay_seconds': self.delay}
        atomic_json(self.root / 'policies' / f'robots-{self.run_id}.json', self.robots_snapshot)
        return self.robots_snapshot
