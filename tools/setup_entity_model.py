"""One-time public model download; subsequent extraction loads local assets only."""
import os
import argparse
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
os.environ['HF_HOME'] = str(PROJECT / 'data/models/huggingface')
os.environ['HF_HUB_DISABLE_XET'] = '1'
sys.path.insert(0, str(PROJECT))
from newsrag.local_entities import MODEL_ID, MODEL_REVISION
from newsrag.storage import atomic_json, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=PROJECT / 'data')
    args = parser.parse_args()
    os.environ['HF_HOME'] = str(args.data_dir.resolve() / 'models/huggingface')
    from gliner import GLiNER
    import torch
    torch.set_num_threads(4)
    target = args.data_dir.resolve() / 'models/entities'
    model = GLiNER.from_pretrained(MODEL_ID, revision=MODEL_REVISION, token=False, map_location='cpu')
    model.save_pretrained(target, safe_serialization=True)
    assets = {p.name:sha256(p.read_bytes()) for p in sorted(target.iterdir()) if p.is_file() and p.name != 'identity.json'}
    atomic_json(target / 'identity.json', {'model':MODEL_ID, 'revision':MODEL_REVISION, 'files':assets})
    print(f'Entity model saved locally: {target}', flush=True)


if __name__ == '__main__':
    main()
