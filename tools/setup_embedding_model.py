"""Download a fixed public embedding model once; indexing itself is offline."""
import argparse
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from newsrag.embeddings import MODEL_ID, MODEL_REVISION
from newsrag.storage import atomic_json, sha256, writer_lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=PROJECT / 'data')
    args = parser.parse_args()
    os.environ['HF_HOME'] = str(args.data_dir.resolve() / 'models/huggingface')
    os.environ['HF_HUB_DISABLE_XET'] = '1'
    from transformers import AutoModel, AutoTokenizer
    with writer_lock(args.data_dir):
        folder = args.data_dir / 'models/embeddings'
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, token=False)
        model = AutoModel.from_pretrained(MODEL_ID, revision=MODEL_REVISION, token=False, use_safetensors=True)
        model.save_pretrained(folder, safe_serialization=True)
        tokenizer.save_pretrained(folder)
        assets = {p.name: sha256(p.read_bytes()) for p in sorted(folder.iterdir())
                  if p.is_file() and p.name != 'identity.json'}
        atomic_json(folder / 'identity.json', {'model': MODEL_ID, 'revision': MODEL_REVISION, 'files': assets})
    print(f'Embedding assets saved: {folder}')


if __name__ == '__main__':
    main()
