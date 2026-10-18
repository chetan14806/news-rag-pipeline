"""Replay the saved-input pipeline in the separately prepared isolated environment."""
import json
import argparse
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'tmp/submission-check/project'
PYTHON = WORK.parent / '.venv/Scripts/python.exe'
REPORT = ROOT / 'results/clean_environment_verification.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=WORK)
    parser.add_argument('--python', type=Path, default=PYTHON)
    parser.add_argument('--prefix', default='clean_environment')
    args = parser.parse_args()
    work, python = args.workspace.resolve(), args.python.resolve()
    report_path = ROOT / f'results/{args.prefix}_verification.json'
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'passed': False,
              'scope': ('Separately installed isolated venv on the same Windows host; saved original HTML and verified model assets reused. This run does not reinstall dependencies or perform a new publisher scrape.'
                        if work == WORK.resolve() else 'Development environment refresh after extractor revision; saved original HTML and models reused. No new publisher scrape.'),
              'workspace': str(work), 'python': str(python), 'steps': []}
    steps = [
        ('dependencies', ['-m', 'pip', 'check']),
        ('tests', ['-m', 'unittest', 'discover', '-s', 'tests', '-v']),
        ('extraction', ['extract.py']),
        ('extraction_audit', ['tools/audit_extraction.py']),
        ('index', ['index.py']),
        ('index_audit', ['tools/audit_index.py', '--rerun']),
        ('queries', ['tools/evaluate_queries.py']),
    ]
    env = dict(os.environ, PYTHONUTF8='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    for name, step_args in steps:
        print(f'Starting {name}', flush=True)
        started = time.monotonic()
        log = ROOT / f'results/{args.prefix}_{name}.txt'
        with log.open('w', encoding='utf-8') as output:
            result = subprocess.run([str(python), *step_args], cwd=work, env=env,
                                    stdout=output, stderr=subprocess.STDOUT)
        report['steps'].append({'name': name, 'arguments': step_args, 'exit_code': result.returncode,
                                'seconds': round(time.monotonic()-started, 2), 'log': log.name})
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f'{name}: exit {result.returncode}', flush=True)
        if result.returncode:
            return result.returncode
    report['passed'] = True
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
