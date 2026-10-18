"""Local MiniLM encoder with explicit pooling, limits and asset identity."""
import json
from importlib.metadata import version
from pathlib import Path

import numpy as np

from newsrag.storage import sha256

MODEL_ID = 'sentence-transformers/all-MiniLM-L6-v2'
MODEL_REVISION = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'


class LocalEmbedder:
    dimension = 384
    max_tokens = 256

    def __init__(self, folder: Path):
        import torch
        from transformers import AutoModel, AutoTokenizer
        saved = json.loads((folder / 'identity.json').read_text(encoding='utf-8'))
        if saved['model'] != MODEL_ID or saved['revision'] != MODEL_REVISION or not saved['files']:
            raise ValueError('Unexpected embedding model identity')
        for name, digest in saved['files'].items():
            if Path(name).name != name or sha256((folder / name).read_bytes()) != digest:
                raise ValueError(f'Embedding model asset checksum mismatch: {name}')
        torch.set_num_threads(4)
        self.tokenizer = AutoTokenizer.from_pretrained(folder, local_files_only=True)
        self.model = AutoModel.from_pretrained(folder, local_files_only=True, use_safetensors=True).eval()
        self.identity = {**saved, 'pooling': 'attention_mask_mean_l2_v1',
                         'dimension': self.dimension, 'max_tokens': self.max_tokens,
                         'transformers': version('transformers'), 'torch': version('torch'),
                         'tokenizers': version('tokenizers')}

    def encode(self, texts):
        import torch
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        if any(not text.strip() for text in texts):
            raise ValueError('Cannot embed empty text')
        vectors = []
        for start in range(0, len(texts), 32):
            batch = self.tokenizer(texts[start:start + 32], padding=True, truncation=False, return_tensors='pt')
            if batch['input_ids'].shape[1] > self.max_tokens:
                raise ValueError('Embedding input exceeds 256 tokens; split it explicitly')
            with torch.inference_mode():
                output = self.model(**batch).last_hidden_state
                mask = batch['attention_mask'].unsqueeze(-1).to(output.dtype)
                pooled = (output * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                vectors.append(torch.nn.functional.normalize(pooled, p=2, dim=1).cpu().numpy())
        return np.concatenate(vectors).astype(np.float32)
