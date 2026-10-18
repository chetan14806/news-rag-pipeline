"""Extract complete article records from saved, verified HTML without network IO."""
import argparse
import json
import sys
from pathlib import Path

from newsrag.extraction_runner import run_extraction


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--limit', type=int)
    parser.add_argument('--id', action='append', dest='ids', help='Full manifest ID; repeatable')
    parser.add_argument('--force', action='store_true', help='Re-extract matching records even if fingerprint unchanged')
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    try:
        result = run_extraction(args.data_dir.resolve(), limit=args.limit, ids=args.ids, force=args.force,
                                progress=lambda message: print(message, flush=True))
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'complete' and result['processed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
