"""Persistent extraction orchestration; current manifest is the index handoff."""
import json
from pathlib import Path

from newsrag.extraction import extract_article, fingerprint, load_nlp
from newsrag.models import ArticleRecord
from newsrag.storage import RawStore, append_json, atomic_json, sha256, utc_now, writer_lock


def run_extraction(root: Path, *, limit=None, ids=None, force=False, nlp=None, progress=print):
    run_id = utc_now().replace(':', '').replace('.', '').replace('+', '-')
    summary = {'run_id': run_id, 'started_at': utc_now(), 'processed': 0, 'written': 0,
               'skipped': 0, 'failed': 0, 'warnings': 0}
    with writer_lock(root):
        store = RawStore(root)
        nlp = nlp or load_nlp(root / 'models/entities')
        manifest_path = root / 'extraction' / 'manifest.json'
        previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'records': {}}
        # Rebuild current eligibility from raw inputs on every run; never trust globbed records.
        current = {}
        selected = set(ids or [])
        entries = list(store.state['articles'].values())
        unknown = selected - {e['id'] for e in entries}
        if unknown:
            raise ValueError(f'Unknown manifest IDs: {sorted(unknown)}')
        for position, entry in enumerate(entries):
            ident = entry['id']
            relative = f'records/{ident}.json'
            path = root / relative
            expected = fingerprint(entry, nlp)
            valid, reason = store.verified(entry['url'])
            cached = None
            if valid and path.exists():
                try:
                    prior = previous.get('records', {}).get(ident)
                    if not prior or prior.get('sha256') != sha256(path.read_bytes()):
                        raise ValueError('Cached record is uncommitted or its checksum changed')
                    cached = ArticleRecord.model_validate_json(path.read_text(encoding='utf-8'))
                    if cached.id != ident or cached.url != entry['final_url'] or cached.provenance['fingerprint'] != expected or cached.provenance['raw_sha256'] != entry['sha256']:
                        cached = None
                except (ValueError, KeyError, TypeError):
                    cached = None
            should_process = (not selected or ident in selected) and (limit is None or summary['processed'] < limit)
            if not should_process:
                if cached:
                    current[ident] = {'path': relative, 'fingerprint': expected, 'sha256': sha256(path.read_bytes())}
                continue
            summary['processed'] += 1
            try:
                if not valid:
                    raise ValueError(f'Raw input integrity failure: {reason}')
                if cached and not force:
                    record = cached
                    summary['skipped'] += 1
                else:
                    record = extract_article((root / entry['raw_path']).read_bytes(), entry, nlp)
                    atomic_json(path, record.model_dump(mode='json'))
                    summary['written'] += 1
                current[ident] = {'path': relative, 'fingerprint': expected, 'sha256': sha256(path.read_bytes())}
                summary['warnings'] += len(record.warnings)
                progress(f"[{summary['processed']}] {ident[:10]} {record.category}: {record.title}")
            except (ValueError, KeyError, TypeError, OSError) as error:
                summary['failed'] += 1
                append_json(root / 'extraction' / 'errors.jsonl', {
                    'run_id': run_id, 'at': utc_now(), 'id': ident, 'url': entry['url'],
                    'raw_sha256': entry['sha256'], 'error': str(error), 'status': 'quarantined'})
                progress(f"Quarantined {ident[:10]}: {error}")
            # Publish acceptance after each result so a changed failure cannot stay current.
            atomic_json(manifest_path, {'schema_version': 1, 'updated_at': utc_now(), 'records': current,
                                        'complete_scan': False, 'run_id': run_id})
        summary.update(accepted=len(current), finished_at=utc_now(),
                       status='complete' if not summary['failed'] else 'partial_failure')
        atomic_json(manifest_path, {'schema_version': 1, 'updated_at': utc_now(), 'records': current,
                                    'complete_scan': True, 'run_id': run_id})
        atomic_json(root / 'extraction' / 'runs' / f'{run_id}.json', summary)
        atomic_json(root / 'extraction' / 'latest.json', summary)
    return summary
