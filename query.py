"""Answer supported natural-language news questions from the persisted corpus."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from newsrag.query_engine import QueryEngine, render_answer


def aware_time(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError('Use an ISO timestamp with timezone, e.g. 2026-10-17T12:00:00Z')
    return parsed


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('question')
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--index-dir', type=Path)
    parser.add_argument('--as-of', type=aware_time)
    parser.add_argument('--since', type=aware_time)
    parser.add_argument('--before', type=aware_time)
    parser.add_argument('--intent', choices=['ai','funding','company','location','layoffs','investors','revenue','unsupported'])
    parser.add_argument('--company')
    parser.add_argument('--location')
    parser.add_argument('--title')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        result = QueryEngine(args.data_dir, args.index_dir).answer(args.question, as_of=args.as_of,
                    since=args.since, before=args.before, intent=args.intent, company=args.company, location=args.location, title=args.title)
    except (ValueError, RuntimeError, OSError) as error:
        print(f'Query failed: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_answer(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
