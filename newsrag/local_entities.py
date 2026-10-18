"""Type-aware local NER with bounded overlapping windows and source offsets."""
import json
import re
from importlib.metadata import version
from pathlib import Path

from newsrag.entity_rules import refine
from newsrag.storage import sha256

MODEL_ID = 'urchade/gliner_small-v2.1'
MODEL_REVISION = '4e091416cf7c3481db542c2a3d26156916f3a47f'
LABELS = ['company', 'organization', 'person', 'location', 'product']
THRESHOLD = 0.6


def clean_name(value, field):
    value = re.sub(r'Founded$', '', value)
    if field == 'people':
        value = re.sub(r'^(?:(?:Mr|Mrs|Ms|Dr|Prof|Sh)\.?\s+|Attorney General\s+)+', '', value)
        parts = value.split()
        if not 2 <= len(parts) <= 5 or any(not p[0].isupper() and p not in {'de','van','von','al','bin','da','dos'} for p in parts):
            return None
    if field == 'companies' and re.search(r'\b(?:firms|industry bodies|professionals|financial institutions)\b|^Fortune \d+ companies$', value, re.I):
        return None
    return value


def windows(text, tokenizer, count_words):
    words = list(re.finditer(r'\S+', text))
    left = 0
    while left < len(words):
        right = min(left+90, len(words))
        while True:
            start, end = words[left].start(), words[right-1].end()
            chunk = text[start:end]
            if len(tokenizer.encode(chunk, add_special_tokens=False)) <= 240 and count_words(chunk) <= 300:
                break
            right = left + (right-left)//2
            if right <= left:
                raise ValueError('A source token exceeds the entity-model window budget')
        yield start, chunk
        if right == len(words):
            break
        left = max(left+1, right-15)


class LocalEntities:
    def __init__(self, folder: Path):
        metadata_path = folder / 'identity.json'
        if not metadata_path.exists():
            raise RuntimeError('Entity model missing: run python tools/setup_entity_model.py once')
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata['model'] != MODEL_ID or metadata['revision'] != MODEL_REVISION:
            raise ValueError('Unexpected entity model identity; rerun model setup')
        for name, expected in metadata['files'].items():
            if Path(name).name != name or sha256((folder / name).read_bytes()) != expected:
                raise ValueError('Entity model asset checksum mismatch')
        import torch
        from gliner import GLiNER
        torch.set_num_threads(4)
        self.model = GLiNER.from_pretrained(str(folder), local_files_only=True, map_location='cpu')
        self.identity = {**metadata, 'gliner':version('gliner'), 'transformers':version('transformers'), 'torch':version('torch'),
                         'threshold':THRESHOLD, 'labels':LABELS, 'window_subtokens':240, 'window_overlap_words':15}

    def predict(self, body, primary_company=None):
        processor = self.model.data_processor
        chunks = list(windows(body, processor.transformer_tokenizer,
                              lambda text: len(list(processor.words_splitter(text)))))
        values = {'companies': [], 'people': [], 'locations': []}
        evidence = []
        for offset in range(0, len(chunks), 8):
            batch = chunks[offset:offset+8]
            results = self.model.inference([text for _,text in batch], LABELS, threshold=THRESHOLD, batch_size=8)
            for (start, text), entities in zip(batch, results, strict=True):
                for entity in entities:
                    field = {'company':'companies', 'organization':'companies', 'person':'people', 'location':'locations'}.get(entity['label'])
                    if not field:
                        continue
                    raw = entity['text']
                    value = re.sub(r'^(?:the)\s+', '', raw.strip(), flags=re.I)
                    value = re.sub(r'[’\']s$', '', value)
                    value = clean_name(value, field)
                    if not value:
                        continue
                    if not re.search(r'[A-Z]', value) or '\n' in value or 'http' in value:
                        continue
                    if field == 'locations':
                        value = re.sub(r'-based$|^pan-', '', value, flags=re.I)
                        if any(not part[0].isupper() and part not in {'of','the','and'} for part in value.split()):
                            continue
                        if value.casefold() in {'bangalore','bengaluru'}:
                            value = 'Bengaluru'
                    if field == 'companies':
                        value = re.sub(r'^\d{2,}(?=[A-Z])', '', value)
                        if value.casefold() in {'enterprises','regulators','cros','cisos','ceos','financial institutions'}:
                            continue
                        context = body[max(0,start+entity['start']-12):start+entity['start']]
                        if re.search(r'(?:NYSE|NASDAQ|TSX)\s*:\s*$', context):
                            continue
                    values[field].append(value)
                    evidence.append({'field':field, 'value':value, 'text':raw,
                                     'start':start+entity['start'], 'end':start+entity['end'],
                                     'label':entity['label'], 'score':float(entity['score'])})
        if primary_company:
            match = re.search(re.escape(primary_company), body, re.I)
            if match:
                values['companies'].append(match.group())
                evidence.append({'field':'companies', 'value':match.group(), 'text':match.group(),
                                 'start':match.start(), 'end':match.end(), 'label':'headline_subject'})
        for match in re.finditer(r'\b(?:Bengaluru|Bangalore)\b', body, re.I):
            values['locations'].append('Bengaluru')
            evidence.append({'field':'locations', 'value':'Bengaluru', 'text':match.group(),
                             'start':match.start(), 'end':match.end(), 'label':'explicit_alias'})
        return refine(values, evidence, body)
