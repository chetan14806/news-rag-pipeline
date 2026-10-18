"""Compare a completed isolated replay with the accepted development snapshot."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'tmp/submission-check/project'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report_path = ROOT / 'results/clean_environment_verification.json'
    report = read(report_path)
    if not report['passed']:
        raise ValueError('Complete the replay successfully before finalizing')
    prep = read(ROOT / 'results/clean_environment_preparation.json')
    code_same = all(digest(WORK / name) == value == digest(ROOT / name)
                    for name, value in prep['code_hashes'].items())
    original = read(ROOT / 'data/extraction/manifest.json')['records']
    replay = read(WORK / 'data/extraction/manifest.json')['records']
    matching = [key for key in original.keys() & replay.keys()
                if digest(ROOT / 'data' / original[key]['path']) == digest(WORK / 'data' / replay[key]['path'])]
    base_answers = read(ROOT / 'results/query_evaluation.json')['samples']
    answers = read(WORK / 'results/query_evaluation.json')
    fields = ('plan', 'answer', 'items', 'sources')
    review_hashes = {row['answer_digest'] for row in read(ROOT / 'results/query_source_review.json')['reviews']}
    reviewed = all(hashlib.sha256(json.dumps({key: answer[key] for key in fields},
                   sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest() in review_hashes
                   for answer in answers['samples'])
    answers_same = len(base_answers) == len(answers['samples']) == 8 and all(
        all(a.get(k) == b.get(k) for k in fields) for a, b in zip(base_answers, answers['samples']))
    extra = {}
    for name in ('audit_scrape', 'check_raw_inputs'):
        log = ROOT / f'results/clean_environment_{name}.txt'
        with log.open('w', encoding='utf-8') as output:
            process = subprocess.run([str(WORK.parent / '.venv/Scripts/python.exe'), f'tools/{name}.py'],
                                     cwd=WORK, stdout=output, stderr=subprocess.STDOUT)
        extra[name] = process.returncode
    index = read(WORK / 'results/index_audit.json')
    extraction = read(WORK / 'data/extraction/audit.json')
    with (ROOT / 'results/clean_environment_query_cli.json').open('w', encoding='utf-8') as output, \
         (ROOT / 'results/clean_environment_query_cli_stderr.txt').open('w', encoding='utf-8') as errors:
        cli = subprocess.run([str(WORK.parent / '.venv/Scripts/python.exe'), 'query.py',
                              'List all articles that mention Bengaluru.', '--as-of',
                              '2026-10-17T12:00:00+00:00', '--json'],
                             cwd=WORK, stdout=output, stderr=errors)
    cli_matches = cli.returncode == 0 and read(ROOT / 'results/clean_environment_query_cli.json')['items'] == answers['samples'][3]['items']
    report['final_checks'] = {
        'prepared_source_hashes_match_current_and_replayed_code': code_same,
        'original_records': len(original), 'replayed_records': len(replay),
        'byte_identical_records': len(matching), 'records_match': len(matching) == len(original) == len(replay) == 81,
        'eight_sample_answers_match': answers_same, 'extraction_audit_passed': extraction['passed'],
        'eight_original_source_review_hashes_match': reviewed and len(answers['samples']) == 8,
        'chunks': index['chunks'], 'retrieval_hits_at_5': index['retrieval_hits_at_5'],
        'retrieval_probes': index['retrieval_probes'], 'index_network_attempts': index['network_attempts'],
        'query_evaluation_passed': answers['passed'], 'query_network_attempts': answers['checks']['network_attempts'],
        'raw_audit_exit_codes': extra,
        'query_cli_exit_code': cli.returncode, 'query_cli_items_match': cli_matches,
    }
    checks = report['final_checks']
    report['passed'] = all(checks[k] for k in ('prepared_source_hashes_match_current_and_replayed_code',
        'records_match', 'eight_sample_answers_match', 'eight_original_source_review_hashes_match',
        'extraction_audit_passed', 'query_evaluation_passed', 'query_cli_items_match')) and not any(extra.values())
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(checks, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
