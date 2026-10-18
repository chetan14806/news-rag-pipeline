"""Evaluate a local type-aware NER alternative before adopting it in extraction."""
import json
import os
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
os.environ['HF_HOME'] = str(PROJECT / 'data/models/huggingface')
os.environ['HF_HUB_DISABLE_XET'] = '1'
sys.path.insert(0, str(PROJECT))


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    from gliner import GLiNER
    from huggingface_hub import HfApi
    import torch
    torch.set_num_threads(4)
    model_id = 'urchade/gliner_small-v2.1'
    revision = HfApi().model_info(model_id, token=False).sha
    print(f'Loading local model {model_id}@{revision}', flush=True)
    model = GLiNER.from_pretrained(model_id, revision=revision, map_location='cpu', token=False)
    print('Model loaded', flush=True)
    manifest = json.loads((PROJECT / 'data/extraction/manifest.json').read_text(encoding='utf-8'))
    rows = []
    labels = ['company', 'organization', 'person', 'location', 'product']
    for entry in manifest['records'].values():
        record = json.loads((PROJECT / 'data' / entry['path']).read_text(encoding='utf-8'))
        if not any(s in record['url'] for s in ['toy-giant-funskool', 'servicenow-launches', 'circle-raises']):
            continue
        start = time.monotonic()
        import re
        words = list(re.finditer(r'\S+', record['body']))
        entities = []
        # Short overlapping windows avoid model max_len truncation on news bodies.
        for offset in range(0, len(words), 75):
            left = words[offset].start()
            right = words[min(offset+90, len(words))-1].end()
            text = record['body'][left:right]
            for entity in model.predict_entities(text, labels, threshold=0.6):
                entities.append({**entity, 'start': left+entity['start'], 'end': left+entity['end']})
        unique = {(e['label'],e['text']) for e in entities}
        rows.append({'id':record['id'], 'url':record['url'], 'elapsed_seconds':time.monotonic()-start,
                     'entities': [list(e) for e in sorted(unique)]})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    result = {'model':model_id, 'revision':revision, 'threshold':0.6, 'labels':labels, 'rows':rows}
    path = PROJECT / 'data/extraction/entity-model-pilot.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
