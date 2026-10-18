"""Real-model replacement probe on an isolated, deliberately edited source copy."""
import json
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ['HF_HUB_OFFLINE'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsrag.embeddings import LocalEmbedder
from newsrag.indexing import run_index, checked_index, search
from newsrag.storage import atomic_json, sha256, utc_now, writer_lock


def main():
    source = Path('data')
    ident = '1e81e4d564d516ba349aa25c2db52164881160111270bbafed26502c28fbb136'
    base = Path('tmp/index-replacement').resolve()
    base.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(dir=base)).resolve()
    assert root.is_relative_to(base)
    raw_state = json.loads((source / 'manifest.json').read_text())
    raw_state['articles'] = {ident: raw_state['articles'][ident]}
    accepted = json.loads((source / 'extraction/manifest.json').read_text())
    accepted['records'] = {ident: accepted['records'][ident]}
    atomic_json(root / 'manifest.json', raw_state)
    atomic_json(root / 'extraction/manifest.json', accepted)
    for relative in (raw_state['articles'][ident]['raw_path'], accepted['records'][ident]['path']):
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, root / relative)
    source_hash = sha256((source / f'records/{ident}.json').read_bytes())
    attempts = []
    def block(sock, address):
        attempts.append(str(address))
        raise OSError('Network disabled for replacement probe')
    with patch.object(socket.socket, 'connect', block), patch.object(socket.socket, 'connect_ex', block):
        embedder = LocalEmbedder(source / 'models/embeddings')
        first = run_index(root, embedder=embedder, progress=lambda _: None)
        record_path = root / f'records/{ident}.json'
        record = json.loads(record_path.read_text(encoding='utf-8'))
        end = max(record['body'].index(s) + len(s) for s in record['provenance']['summary_sentences'])
        record['body'] = record['body'][:max(end, 200)]
        # Deliberately edited fixture only; production raw and accepted records are untouched.
        atomic_json(record_path, record)
        accepted['records'][ident]['sha256'] = sha256(record_path.read_bytes())
        atomic_json(root / 'extraction/manifest.json', accepted)
        rejected_stale = False
        try:
            search(root, 'precision manufacturing', embedder=embedder)
        except ValueError as error:
            rejected_stale = 'stale' in str(error)
        replacement = run_index(root, embedder=embedder, progress=lambda _: None)
        with writer_lock(root):
            _, state = checked_index(root, root / 'index', embedder)
        hits = search(root, 'precision manufacturing', embedder=embedder)
        accepted['records'] = {}
        atomic_json(root / 'extraction/manifest.json', accepted)
        removed = run_index(root, embedder=embedder, progress=lambda _: None)
    source_unchanged = source_hash == sha256((source / f'records/{ident}.json').read_bytes())
    passed = (rejected_stale and replacement['chunks'] < first['chunks'] and
              replacement['removed_chunks'] == first['chunks'] - replacement['chunks'] and
              bool(hits) and removed['chunks'] == 0 and source_unchanged and not attempts)
    result = {'checked_at': utc_now(), 'fixture_directory': str(root),
              'scope': 'Real model and Chroma, isolated deliberately shortened extracted-record fixture; not a publisher refresh.',
              'initial': first, 'replacement': replacement, 'removal': removed,
              'stale_search_rejected': rejected_stale, 'replacement_integrity_passed': state['complete'],
              'source_record_unchanged': source_unchanged, 'network_attempts': attempts, 'passed': passed}
    atomic_json(Path('results/index_replacement_verification.json'), result)
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
