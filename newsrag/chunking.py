"""Token-budgeted exact body spans with preferred sentence/paragraph endings."""
import re

CHUNK_CONFIG = {'version': 1, 'max_wordpieces': 200, 'overlap_wordpieces': 30,
                'boundary_min_fraction': 0.6, 'input': 'body_only'}


def chunk_body(body, tokenizer, max_wordpieces=200, overlap_wordpieces=30):
    if not 0 <= overlap_wordpieces < max_wordpieces or max_wordpieces < 2:
        raise ValueError('Invalid chunk/overlap budget')
    # Full-body tokenization is for offsets only; only bounded slices reach the encoder.
    offsets = tokenizer(body, add_special_tokens=False, return_offsets_mapping=True, verbose=False)['offset_mapping']
    if not offsets:
        raise ValueError('Body has no tokens')
    boundaries = {m.end() for m in re.finditer(r'[.!?][\"\u201d\u2019]?\s+|\n+', body)}
    chunks = []
    start = 0
    while start < len(offsets):
        end = min(start + max_wordpieces, len(offsets))
        if end < len(offsets):
            choices = [i for i in range(start + int(max_wordpieces * 0.6), end + 1)
                       if any(offsets[i - 1][1] <= b <= offsets[i][0] for b in boundaries)]
            if choices:
                end = choices[-1]
        left = 0 if start == 0 else offsets[start][0]
        right = len(body) if end == len(offsets) else offsets[end][0]
        # Retokenization at a wordpiece cut can differ; shrink until the actual text fits.
        while len(tokenizer(body[left:right], add_special_tokens=False)['input_ids']) > max_wordpieces:
            end -= 1
            if end <= start:
                raise ValueError('Cannot make progress within token budget')
            right = offsets[end][0]
        text = body[left:right]
        count = len(tokenizer(text, add_special_tokens=False)['input_ids'])
        chunks.append({'text': text, 'start': left, 'end': right, 'tokens': count})
        if end == len(offsets):
            break
        start = max(start + 1, end - overlap_wordpieces)
    return chunks
