"""Inspect retrieved evidence chunks; this is not the final answer-generation CLI."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsrag.indexing import search


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('question')
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--index-dir', type=Path)
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--category')
    parser.add_argument('--article-id', action='append', dest='article_ids')
    args = parser.parse_args()
    print(json.dumps(search(args.data_dir, args.question, index_dir=args.index_dir,
                            top_k=args.top_k, category=args.category, article_ids=args.article_ids),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
