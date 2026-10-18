"""Offline index integrity, chunk coverage and declared real retrieval probes."""
import argparse
import json
import os
import socket
import sys
from pathlib import Path
from unittest.mock import patch

os.environ['HF_HUB_OFFLINE'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsrag.embeddings import LocalEmbedder
from newsrag.indexing import checked_index, load_inputs, search, digest, run_index
from newsrag.chunking import chunk_body
from newsrag.storage import atomic_json, writer_lock, utc_now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index-dir', type=Path, default=Path('data/index'))
    parser.add_argument('--output', type=Path, default=Path('results/index_audit.json'))
    parser.add_argument('--rerun', action='store_true')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    root = Path('data')
    attempts = []
    def block(sock, address):
        attempts.append(str(address))
        raise OSError('Network disabled for index verification')
    with patch.object(socket.socket, 'connect', block), patch.object(socket.socket, 'connect_ex', block):
        embedder = LocalEmbedder(root / 'models/embeddings')
        with writer_lock(root):
            collection, state = checked_index(root, args.index_dir, embedder)
            records, _ = load_inputs(root, state['config']['selection'])
            coverage = []
            for ident, record in records.items():
                chunks = chunk_body(record.body, embedder.tokenizer)
                end = 0
                for chunk in chunks:
                    if chunk['start'] > end or chunk['text'] != record.body[chunk['start']:chunk['end']]:
                        raise ValueError('Source chunk gap or mismatch')
                    if len(embedder.tokenizer(chunk['text'])['input_ids']) > embedder.max_tokens:
                        raise ValueError('Chunk exceeds encoder budget')
                    end = max(end, chunk['end'])
                if end != len(record.body):
                    raise ValueError('Missing body tail')
                coverage.append({'article_id': ident, 'chunks': len(chunks),
                                 'max_total_tokens': max(len(embedder.tokenizer(c['text'])['input_ids']) for c in chunks),
                                 'body_characters': len(record.body), 'full_character_coverage': True})
            before = digest(state['articles'])
        rerun = None
        if args.rerun:
            with patch.object(embedder, 'encode', side_effect=AssertionError('Unchanged rerun must not embed')):
                rerun = run_index(root, index_dir=args.index_dir, ids=state['config']['selection'],
                                  embedder=embedder, progress=lambda _: None)
            after = json.loads((args.index_dir / 'manifest.json').read_text())
            if digest(after['articles']) != before or rerun['written_articles'] or rerun['removed_chunks']:
                raise ValueError('Unchanged rerun changed vector state')
        cases = json.loads(Path('results/index_retrieval_cases.json').read_text())['cases']
        results = []
        for case in cases:
            hits = search(root, case['question'], index_dir=args.index_dir, top_k=10, embedder=embedder)
            unique = list(dict.fromkeys(h['metadata']['article_id'] for h in hits))
            expected = case['expected_article_id']
            rank = unique.index(expected) + 1 if expected in unique else None
            results.append({**case, 'rank_among_retrieved_distinct_articles': rank,
                            'hit_in_first_5_distinct_articles': rank is not None and rank <= 5,
                            'hits': hits})
            print(f"Retrieval probe {len(results)}/{len(cases)}: expected article rank {rank}", flush=True)
        empty = search(root, 'funding', index_dir=args.index_dir, article_ids=[], embedder=embedder)
        funding = search(root, 'startup financing', index_dir=args.index_dir, category='funding', embedder=embedder)
        if empty or any(h['metadata']['category'] != 'funding' for h in funding):
            raise ValueError('Metadata/empty-ID filter violation')
    result = {'checked_at': utc_now(), 'index_dir': str(args.index_dir), 'articles': len(records),
              'chunks': state['chunks'], 'dimensions': embedder.dimension,
              'state_digest': before, 'network_attempts': attempts, 'rerun': rerun,
              'retrieval_hits_at_5': sum(r['hit_in_first_5_distinct_articles'] for r in results),
              'retrieval_probes': len(results), 'coverage': coverage, 'retrieval': results,
              'integrity_passed': not attempts, 'filter_checks_passed': True,
              'retrieval_checks_passed': bool(results) and all(r['hit_in_first_5_distinct_articles'] for r in results)}
    result['passed'] = all(result[key] for key in ('integrity_passed', 'filter_checks_passed', 'retrieval_checks_passed'))
    atomic_json(args.output, result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('coverage','retrieval')}, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
