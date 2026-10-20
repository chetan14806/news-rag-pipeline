"""Measure real local semantic routing and grounded execution on saved questions.

Uses one integrity-checked corpus/index snapshot, not mocked scores or cached
answers. Refusal rate and intent accuracy are separate; abstention is not success
at understanding a supported operation. No fixed score is asserted as universal.
"""
import argparse
import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsrag.embeddings import LocalEmbedder
from newsrag.indexing import checked_index, load_inputs, validate_vectors
from newsrag.query_engine import QueryEngine, answer_records
from newsrag.semantic_router import EXAMPLES, SemanticRouter
from newsrag.storage import writer_lock


def evaluate(root, dataset, as_of):
    engine = QueryEngine(root)
    engine.embedder = LocalEmbedder(root / 'models/embeddings')
    engine.router = SemanticRouter(engine.embedder)
    collection, state = checked_index(root, root / 'index', engine.embedder)
    records, _ = load_inputs(root)
    if state['config']['selection'] is not None:
        raise ValueError('Evaluation requires a full corpus index')

    def retrieve(text, ids, count):
        if not ids:
            return []
        vectors = validate_vectors(engine.embedder.encode([text]), 1, engine.embedder.dimension)
        found = collection.query(query_embeddings=vectors.tolist(), n_results=min(count, state['chunks']),
                                 where={'article_id': {'$in': ids}}, include=['documents', 'metadatas', 'distances'])
        return [{'chunk_id': ident, 'text': found['documents'][0][i],
                 'metadata': found['metadatas'][0][i], 'cosine_distance': found['distances'][0][i]}
                for i, ident in enumerate(found['ids'][0])]

    rows = []
    training = {q.casefold() for group in EXAMPLES.values() for q in group}
    for label, questions in dataset.items():
        for question in questions:
            if question.casefold() in training:
                raise ValueError('An evaluation question is also a training example')
            expected = 'unsupported' if label == 'abstain' else label
            plan, routing = engine._make_plan(question, records, as_of=as_of)
            answer = answer_records(plan, records, retrieve)
            for item in answer['items']:
                record = records[item['article_id']]
                assert item['url'] == record.url
                for evidence in item['evidence']:
                    assert record.body[evidence['start']:evidence['end']] == evidence['text']
            refused = answer['status'] in {'unsupported', 'clarification_required'}
            rows.append({'question': question, 'expected': expected, 'plan': answer['plan'],
                         'routing': routing, 'status': answer['status'],
                         'item_ids': [item['article_id'] for item in answer['items']],
                         'correct_intent': plan.intent == expected,
                         'safe_operation_or_abstention': refused or (expected != 'unsupported' and plan.intent == expected)})
    return {'total': len(rows), 'correct_intent': sum(row['correct_intent'] for row in rows),
            'safe_operation_or_abstention': sum(row['safe_operation_or_abstention'] for row in rows),
            'records': len(records), 'chunks': state['chunks'], 'as_of': as_of.isoformat(), 'results': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--questions', type=Path, default=Path(__file__).resolve().parents[1] / 'tests/data/semantic_final_acceptance.json')
    parser.add_argument('--split', default='questions', choices=('questions', 'development', 'heldout'))
    parser.add_argument('--as-of', type=datetime.fromisoformat, default=datetime.now(timezone.utc))
    parser.add_argument('--output', type=Path, default=Path('results/semantic_evaluation.json'))
    args = parser.parse_args()
    if args.as_of.tzinfo is None:
        parser.error('--as-of must have a timezone')
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    data = json.loads(args.questions.read_text(encoding='utf-8'))
    attempts = []

    def block(*unused_args, **unused_kwargs):
        attempts.append('blocked connection')
        raise OSError('Semantic evaluation is offline')

    with patch.object(socket.socket, 'connect', block), patch.object(socket.socket, 'connect_ex', block), writer_lock(args.data_dir):
        report = evaluate(args.data_dir, data[args.split], args.as_of)
    report.update(network_attempts=attempts, scope=data.get('scope'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}))


if __name__ == '__main__':
    main()
