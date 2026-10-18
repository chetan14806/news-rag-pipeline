"""Measure no-write extraction rerun and preserve five local sample pairs."""
import json
import os
import sys
import socket
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['HF_HUB_OFFLINE'] = '1'
from newsrag.extraction_runner import run_extraction
from newsrag.storage import RawStore, atomic_bytes, atomic_json, sha256, writer_lock


def snapshot(root):
    state = json.loads((root / 'extraction/manifest.json').read_text(encoding='utf-8'))
    return {ident: {'sha256': sha256((root / entry['path']).read_bytes()),
                    'mtime_ns': (root / entry['path']).stat().st_mtime_ns}
            for ident, entry in state['records'].items()}


def main():
    root = Path('data')
    with writer_lock(root):
        before = snapshot(root)
    network_attempts = []
    def block_network(sock, address):
        network_attempts.append(str(address))
        raise OSError('Network is disabled during offline rerun verification')
    with patch.object(socket.socket, 'connect', block_network), patch.object(socket.socket, 'connect_ex', block_network):
        summary = run_extraction(root, progress=lambda *args: None)
    with writer_lock(root):
        after = snapshot(root)
        result = {'summary': summary, 'records_identical': before == after,
                  'network_attempts': network_attempts,
                  'before_count': len(before), 'after_count': len(after),
                  'passed': before == after and not network_attempts and summary['written'] == 0 and summary['failed'] == 0 and summary['skipped'] >= 50}
        atomic_json(Path('results/extraction_rerun_verification.json'), result)
        # Reuse the five published fixtures; the development research folder is
        # deliberately excluded from the submission archive.
        sample_ids = set(json.loads(Path('samples/manifest.json').read_text(encoding='utf-8'))['articles'])
        if len(sample_ids) != 5 or not sample_ids <= after.keys():
            raise ValueError('All five packaged sample IDs must be currently accepted')
        store = RawStore(root)
        copied = []
        for entry in store.state['articles'].values():
            if entry['id'] in sample_ids:
                ident = entry['id']
                if ident not in after:
                    raise ValueError('Pilot sample is not currently accepted')
                atomic_bytes(root / f'samples/{ident}.html', (root / entry['raw_path']).read_bytes())
                atomic_bytes(root / f'samples/{ident}.json', (root / f'records/{ident}.json').read_bytes())
                copied.append(ident)
        atomic_json(root / 'samples/manifest.json', {'ids': copied, 'count': len(copied),
                    'note': 'Local full-schema sample pairs only; public redistribution has not been authorized/reviewed.'})
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
