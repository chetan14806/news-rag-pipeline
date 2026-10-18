"""Synchronize accepted article records into a persistent local semantic index."""
import argparse
import json
import sys
from pathlib import Path

from newsrag.indexing import run_index


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--index-dir', type=Path)
    parser.add_argument('--id', action='append', dest='ids')
    args = parser.parse_args()
    try:
        result = run_index(args.data_dir, index_dir=args.index_dir, ids=args.ids,
                           progress=lambda message: print(message, flush=True))
    except (ValueError, OSError, RuntimeError) as error:
        print(f'Indexing failed: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
