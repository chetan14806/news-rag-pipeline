"""Build and verify a local source submission archive, excluding runtime data/secrets."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = [p for p in ROOT.iterdir() if p.is_file() and
             (p.suffix in {'.py', '.md'} or p.name in {'.env.example', '.gitignore', '.gitattributes', 'requirements.txt'})]
    for folder in ('newsrag', 'tests', 'tools', 'samples', 'results'):
        files.extend(p for p in (ROOT / folder).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts
                     and p.suffix in {'.py', '.md', '.json', '.txt', '.html'}
                     and p.name != 'submission_package_verification.json')
    sensitive = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)')
    hashes = {}
    for path in files:
        content = path.read_bytes()
        if sensitive.search(content):
            raise ValueError(f'Potential credential requires review: {path.relative_to(ROOT)}')
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(content).hexdigest()
    required = {'scrape.py', 'extract.py', 'index.py', 'query.py', 'README.md',
                '.env.example', 'requirements.txt', 'results/sample_queries.md', 'samples/manifest.json'}
    if not required <= hashes.keys():
        raise ValueError('Required submission files missing')
    if sum(n.startswith('samples/raw/') and n.endswith('.html') for n in hashes) != 5:
        raise ValueError('Exactly five raw sample fixtures required')
    if sum(n.startswith('samples/records/') and n.endswith('.json') for n in hashes) != 5:
        raise ValueError('Exactly five structured sample fixtures required')
    output = ROOT / 'dist/news-rag-pipeline-submission.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(hashes):
            archive.write(ROOT / name, name)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(hashes):
            raise ValueError('Archive integrity/file list mismatch')
        for name, expected in hashes.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError(f'Archive checksum mismatch: {name}')
    report = {'passed': True, 'archive': str(output.relative_to(ROOT)), 'files': len(hashes),
              'bytes': output.stat().st_size, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'scope': 'Local source package; no remote publication or demo video. Pattern scan is not a guarantee that every possible secret format is recognized.',
              'excluded': ['full corpus', 'models', 'virtual environments', 'temporary workspaces', 'assignment PDF', 'Git internals'],
              'file_hashes': hashes}
    (ROOT / 'results/submission_package_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'file_hashes'}, indent=2))


if __name__ == '__main__':
    main()
