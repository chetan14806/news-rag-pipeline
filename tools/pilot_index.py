"""Build the five-source-pilot index before processing the full corpus."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from newsrag.indexing import run_index
from newsrag.storage import atomic_json

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    root = Path('data')
    ids = json.loads((root / 'samples/manifest.json').read_text())['ids']
    result = run_index(root, index_dir=root / 'index-pilot', ids=ids,
                       progress=lambda message: print(message, flush=True))
    atomic_json(Path('results/index_pilot.json'), result)
    print(json.dumps(result, indent=2))
