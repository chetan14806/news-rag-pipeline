"""Evaluate declared manual development labels, never a population accuracy claim."""
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsrag.storage import atomic_json, utc_now


def main():
    labels = json.loads(Path('results/extraction_manual_labels.json').read_text(encoding='utf-8'))
    manifest = json.loads(Path('data/extraction/manifest.json').read_text(encoding='utf-8'))
    records = [json.loads((Path('data') / e['path']).read_text(encoding='utf-8')) for e in manifest['records'].values()]
    def find(slug):
        matches = [r for r in records if slug in r['url']]
        if len(matches) != 1:
            raise ValueError(f'Expected one reviewed record for {slug}')
        return matches[0]
    checks = []
    for gold in labels['funding']:
        record = find(gold['slug'])
        actual = record['funding'] or {}
        for field in ['company', 'amount', 'currency', 'round', 'status', 'investors'] + (['kind'] if 'kind' in gold else []):
            value, expected = actual.get(field), gold[field]
            if field == 'amount':
                passed = (value is None and expected is None) or (value is not None and expected is not None and Decimal(value) == Decimal(expected))
            elif field == 'investors':
                passed = set(value or []) == set(expected) if gold.get('investors_exact', True) else set(expected).issubset(value or [])
            else:
                passed = str(value).casefold() == str(expected).casefold()
            checks.append({'id': record['id'], 'field': field, 'passed': passed, 'actual': value, 'expected': expected})
    for slug in labels['nonfunding']:
        record = find(slug)
        checks.append({'id': record['id'], 'field': 'funding_null', 'passed': record['funding'] is None})
    predicted = false = 0
    entity_rows = []
    for gold in labels['entity_review'] + labels.get('entity_review_additional', []):
        record = find(gold['slug'])
        total = sum(len(record[f]) for f in ['companies', 'people', 'locations'])
        wrong = sum(value in record[field] for field, values in gold['false_positives'].items() for value in values)
        predicted += total
        false += wrong
        missing = {field:[v for v in values if v.casefold() not in {x.casefold() for x in record[field]}]
                   for field,values in gold['known_missing'].items()}
        entity_rows.append({'id': record['id'], 'predicted_display_strings': total, 'identified_false_positives': wrong,
                            'known_missing': {f:v for f,v in missing.items() if v}})
    result = {'checked_at': utc_now(), 'reviewed_articles': len(labels['funding'])+len(labels['nonfunding']), 'funding_and_null_checks': len(checks),
              'passed_checks': sum(c['passed'] for c in checks), 'failures': [c for c in checks if not c['passed']],
              'entity_sample_articles': len(entity_rows), 'entity_predicted_strings': predicted,
              'entity_identified_false_positives': false, 'entity_review_precision': (predicted-false)/predicted,
              'entity_rows': entity_rows, 'checks': checks, 'scope': labels['scope'],
              'limitation': 'Entity recall not exhaustively labeled; aliases count as display strings. Review exposed real quality gaps; do not treat schema acceptance or this development sample as verified whole-corpus accuracy.'}
    atomic_json(Path('results/extraction_label_evaluation.json'), result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'checks', 'entity_rows'}}, indent=2))
    return 0 if not result['failures'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
