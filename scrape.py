"""CLI for the independently runnable raw news collection stage."""
import argparse
import json
import math
from pathlib import Path

from newsrag.scraper import collect


def positive_int(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError('Must be at least 1')
    return value


def positive_float(text):
    value = float(text)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError('Must be a finite positive number')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--limit', type=positive_int, default=80, help='Target ready pages, including verified prior saves (default: 80)')
    parser.add_argument('--delay', type=positive_float, default=6.0, help='Seconds between starts; a 6-second floor and robots limits always apply')
    parser.add_argument('--timeout', type=positive_float, default=25.0, help='Socket timeout seconds (default: 25)')
    parser.add_argument('--attempts', type=positive_int, choices=range(1, 6), default=3, help='Bounded attempts per URL (1–5)')
    parser.add_argument('--discover-only', action='store_true', help='Save robots/feed/candidates, fetch no articles')
    parser.add_argument('--refresh', action='store_true', help='Explicitly re-fetch even verified pages; ordinary reruns skip them')
    args = parser.parse_args()
    try:
        result = collect(args.data_dir.resolve(), limit=args.limit, delay=args.delay,
                         timeout=args.timeout, attempts=args.attempts,
                         discover_only=args.discover_only, refresh=args.refresh)
    except (RuntimeError, OSError) as error:
        parser.exit(1, f'Scraper could not start: {error}\n')
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)
    if result['status'] == 'interrupted':
        return 130
    return 0 if result['status'] in {'complete', 'discovered'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
