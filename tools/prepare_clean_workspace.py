"""Copy code, saved raw inputs and checked model assets into an isolated replay workspace."""
import json
import shutil
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from newsrag.storage import atomic_json, sha256, utc_now


def main():
    target = PROJECT / 'tmp/submission-check/project'
    if target.exists():
        raise ValueError('Verification workspace already exists; choose/archive a separate run explicitly')
    target.mkdir(parents=True)
    for name in ('newsrag', 'tests', 'tools', 'samples'):
        shutil.copytree(PROJECT / name, target / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('scrape.py','extract.py','index.py','query.py','requirements.txt','README.md','.env.example'):
        shutil.copyfile(PROJECT/name,target/name)
    (target/'results').mkdir()
    for name in ('index_retrieval_cases.json','extraction_manual_labels.json','query_source_review.json'):
        shutil.copyfile(PROJECT/'results'/name,target/'results'/name)
    (target/'data').mkdir()
    shutil.copyfile(PROJECT/'data/manifest.json',target/'data/manifest.json')
    shutil.copytree(PROJECT/'data/raw',target/'data/raw')
    for name in ('entities','embeddings'):
        shutil.copytree(PROJECT/'data/models'/name,target/'data/models'/name)
    code_files = {str(p.relative_to(target)).replace('\\','/'):sha256(p.read_bytes())
                  for p in target.rglob('*.py')}
    result={'prepared_at':utc_now(),'workspace':str(target),'python':str(target.parent/'.venv/Scripts/python.exe'),
            'code_hashes':code_files,'copied_inputs':'81 saved raw originals and manifest; locally checked model assets',
            'not_copied':['extracted records','vector index','query outputs','development site-packages'],
            'scope':'Same Windows host, fresh isolated dependency environment and copied source; not a different computer or OS.'}
    atomic_json(PROJECT/'results/clean_environment_preparation.json',result)
    print(json.dumps(result | {'code_hashes': f'{len(code_files)} Python files'},indent=2))


if __name__=='__main__':
    main()
