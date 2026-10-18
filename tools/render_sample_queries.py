"""Render saved actual answers; apply review judgments only to matching output hashes."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsrag.indexing import digest
from newsrag.query_engine import render_answer
from newsrag.storage import atomic_bytes


def answer_digest(answer):
    return digest({key: answer[key] for key in ('plan','answer','items','sources')})


def write_report(result):
    review_path=Path('results/query_source_review.json')
    reviews=json.loads(review_path.read_text(encoding='utf-8'))['reviews'] if review_path.exists() else []
    lookup={r['answer_digest']:r['judgment'] for r in reviews}
    doc=['# Actual sample query results','',f"Frozen evaluation reference: **{result['evaluation_as_of']}**. Ordinary CLI queries use the current UTC instant unless --as-of is supplied.",
         '', 'Answers below are actual engine outputs using local embeddings/Chroma and deterministic extractive/structured answers, with network connections blocked. No generative LLM is configured.',
         '', 'Judgments are agent source/output review, not independent human annotation; a changed answer loses its previous judgment until reviewed again.', '']
    for i,answer in enumerate(result['samples']):
        judgment=lookup.get(answer_digest(answer),'Pending source/output review; automated checks alone do not establish semantic correctness.')
        doc.extend([f"## {i+1}. {answer['question']}",'',render_answer(answer),'',f'**Correctness judgment:** {judgment}',''])
    atomic_bytes(Path('results/sample_queries.md'),('\n'.join(doc)+'\n').encode('utf-8'))


if __name__=='__main__':
    write_report(json.loads(Path('results/query_evaluation.json').read_text(encoding='utf-8')))
