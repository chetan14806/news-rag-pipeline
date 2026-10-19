"""Grounded extractive answers: complete record operations plus real vector retrieval."""
import re
from collections import defaultdict
from pathlib import Path

from newsrag.embeddings import LocalEmbedder
from newsrag.indexing import checked_index, load_inputs, validate_vectors
from newsrag.query_planner import LAYOFF_TERMS, normalize, plan_query
from newsrag.storage import atomic_json, utc_now, writer_lock

ALIASES = {'bengaluru': ['Bengaluru', 'Bangalore'], 'bangalore': ['Bengaluru', 'Bangalore'],
           'ge aerospace': ['GE Aerospace'], 'servicenow': ['ServiceNow'],
           'openai': ['OpenAI', 'Open AI']}
AI = re.compile(r'\bAI\b|artificial intelligence|machine learning|generative AI', re.I)
LAYOFF = LAYOFF_TERMS


def mentions(text, name):
    variants = ALIASES.get(normalize(name), [name])
    return any(re.search(r'(?<!\w)' + re.escape(v).replace(r'\ ', r'\s+') + r'(?!\w)', text, re.I) for v in variants)


def evidence(record, passage):
    start = record.body.find(passage)
    if start < 0:
        raise ValueError('Answer evidence is not in the accepted article body')
    return {'article_id': record.id, 'url': record.url, 'start': start,
            'end': start + len(passage), 'text': passage}


def passages(body, pattern):
    # Keep entire source lines for tables/period/subject context; no sentence rewriting.
    return [line.strip() for line in body.splitlines() if line.strip() and pattern.search(line)]


def revenue_passages(body):
    lines = body.splitlines()
    found = []
    metric = re.compile(r'(?:₹|\$|€|£|\bUSD\b|\bINR\b|\bRs\.?|crore|billion|million|percent|%|times|\b\d+X\b)', re.I)
    for i, line in enumerate(lines):
        matches = list(re.finditer(r'\brevenues?\b|\bturnover\b', line, re.I))
        if not matches:
            continue
        if line.lstrip().startswith('|'):
            end = i + 1
            while end < len(lines) and lines[end].lstrip().startswith('|'):
                end += 1
            block = '\n'.join(lines[i:end])
            if re.search(r'\d', block):
                found.append(block)
        elif any(metric.search(line[max(0, m.start()-90):m.end()+120]) for m in matches):
            found.append(line.strip())
    return found


def base_item(record, quotes):
    return {'article_id': record.id, 'title': record.title, 'url': record.url,
            'published_at': record.published_at.isoformat(),
            'evidence': [evidence(record, quote) for quote in dict.fromkeys(quotes)]}


def period_records(records, plan):
    return [r for r in records.values() if r.published_at <= plan.as_of and
            (plan.since is None or r.published_at >= plan.since) and
            (plan.before is None or r.published_at < plan.before)]


def layoff_context(text, published_at):
    lower = text.casefold()
    negated = re.search(r'\b(?:no|not|without)\b.{0,40}' + LAYOFF.pattern, lower)
    if negated or re.search(r'no layoffs|not a downsizing|not.*lay(?:ing)? off|not eligible|\bif\b|could|may |might|rumou?r|denied|denies', lower):
        return 'negated_conditional_or_speculative'
    years = {int(y) for y in re.findall(r'\b20\d{2}\b', text)}
    if years and any(y < published_at.year for y in years):
        return 'historical_context'
    action = re.search(r'(?:announc\w*|will|plans? to|has|have)\b.{0,90}' + LAYOFF.pattern, lower)
    if action and re.search(r'\btoday\b|\bthis month\b', lower):
        return 'current_article_event'
    return 'timing_or_event_unconfirmed'


def organization_key(name):
    text = normalize(name)
    return re.sub(r'(?:\s+(?:private|pvt|limited|ltd|incorporated|inc|llc|corporation|corp))+$', '', text)


def stage_key(name):
    text = re.sub(r'\b(?:round|funding)\b', '', normalize(name or '')).strip()
    text = re.sub(r'pre\s*seed', 'pre seed', text)
    text = re.sub(r'series\s*([a-z])\b', r'series \1', text)
    return text if re.fullmatch(r'pre seed|seed|series [a-z]|bridge', text) else ''


def repeated_investors(records):
    eligible = [r for r in records if r.funding and r.funding.kind == 'venture' and
                r.funding.status == 'reported' and r.funding.company]
    by_company = defaultdict(list)
    for record in eligible:
        by_company[organization_key(record.funding.company)].append(record)
    rounds = defaultdict(list)
    uncertain = []
    for company, group in by_company.items():
        stages = [stage_key(r.funding.round) for r in group]
        reliable = all(stages)
        if len(group) > 1 and (not reliable or len(set(stages)) < len(group)):
            uncertain.append({'company': group[0].funding.company,
                              'article_ids': [r.id for r in group],
                              'reason': 'Same-company reports may duplicate a round; conservatively collapsed by known stage or company.'})
        for record, stage in zip(group, stages):
            rounds[(company, stage if reliable else 'unknown')].append(record)
    investors = defaultdict(dict)
    display = {}
    for key, group in rounds.items():
        for record in group:
            for name in record.funding.investors:
                canonical = organization_key(name)
                display.setdefault(canonical, name)
                investors[canonical].setdefault(key, {})[record.id] = record
    rows = []
    for name, found in sorted(investors.items()):
        if len(found) > 1:
            sources = {r.id: r for group in found.values() for r in group.values()}
            rows.append({'investor': display[name], 'conservative_distinct_round_count': len(found),
                         'rounds': [{'company_key': key[0], 'stage_key': key[1], 'article_ids': list(group)}
                                    for key, group in found.items()],
                         'sources': [base_item(r, r.funding.evidence) for r in sources.values()]})
    return rows, uncertain, len(eligible), len(investors)


def answer_records(plan, records, retrieve):
    available = sorted(period_records(records, plan), key=lambda r: (r.published_at, r.id), reverse=True)
    result = {'question': plan.question, 'plan': plan.model_dump(mode='json'),
              'method': 'deterministic structured operations and extractive evidence; no generative LLM',
              'scope': 'Only the validated collected corpus; publisher claims are not independently verified.',
              'status': 'answered', 'answer': '', 'items': [], 'sources': [], 'limitations': [],
              'corpus_records': len(records), 'publication_window_records': len(available)}
    if plan.location and plan.intent != 'location':
        available = [r for r in available if mentions(r.body, plan.location)]
    if plan.company and plan.intent != 'company':
        available = [r for r in available if mentions(r.body, plan.company)]
    result['eligible_records_after_explicit_entity_filters'] = len(available)
    items, lines = [], []
    if plan.clarification:
        result.update(status='clarification_required', answer=plan.clarification)
        return result
    if plan.intent == 'unsupported':
        result.update(status='unsupported', answer='I cannot answer that from this stored news collection. This interface supports AI stories, funding, company announcements, location mentions, layoffs, repeated investors and article-specific revenue. It does not fetch live information.')
        return result
    if plan.intent == 'location':
        if not plan.location:
            result.update(status='clarification_required', answer='Specify the location, for example --location Bengaluru.')
            return result
        for record in available:
            quotes = [line.strip() for line in record.body.splitlines() if line.strip() and mentions(line, plan.location)]
            if quotes:
                items.append(base_item(record, quotes[:1]))
        lines.append(f'{len(items)} articles mention {plan.location} in their body within the publication window. All accepted records were checked; this is not a top-k list.')
        result['limitations'].append('Matches explicit body mentions and configured spelling aliases; no inferred headquarters or geographic identity.')
    elif plan.intent == 'funding':
        pending = []
        for record in available:
            fund = record.funding
            if not fund or fund.kind != 'venture':
                continue
            item = {**base_item(record, fund.evidence), 'funding': fund.model_dump(mode='json')}
            (items if fund.status == 'reported' else pending).append(item)
        lines.append(f'{len(items)} articles published in the window report startup venture funding. Publication date is not proof that the transaction happened in this window.')
        result['pending_financing'] = pending
        if pending:
            lines.append(f'{len(pending)} additional announcement(s) are closing/committed and are not counted as completed raises.')
        result['limitations'].append('Based on extracted venture announcements; debt, bonds and strategic investments excluded. Unknown amounts remain unknown. Named investors may be incomplete.')
    elif plan.intent == 'investors':
        rows, uncertain, examined, names = repeated_investors(available)
        result.update(investors=rows, ambiguous_round_groups=uncertain,
                      funding_articles_examined=examined, distinct_named_investors=names)
        lines.append(f'{len(rows)} named investors are supported in more than one conservatively distinct reported venture round.')
        for row in rows:
            lines.append(f"{row['investor']}: at least {row['conservative_distinct_round_count']} distinct rounds.")
            items.extend(row['sources'])
        if not rows:
            # Retain the complete input roster so the negative aggregation is auditable.
            items = [base_item(r, r.funding.evidence) for r in available if r.funding and
                     r.funding.kind == 'venture' and r.funding.status == 'reported']
            lines.append(f'Checked {examined} eligible funding reports and {names} named investors. No repeat is established in these extracted participants; this is not a claim that no investor repeated in reality.')
        result['limitations'].append('Distinct funds are not merged just because they share a parent. Unknown same-company round identity is collapsed, potentially undercounting. Closing, debt/support and historical mentions are excluded. Investor extraction is incomplete.')
    elif plan.intent == 'layoffs':
        current = 0
        for record in available:
            quotes = passages(record.body, LAYOFF)
            if not quotes:
                continue
            labels = [layoff_context(q, record.published_at) for q in quotes]
            current += int('current_article_event' in labels)
            items.append({**base_item(record, quotes), 'mention_classifications': labels})
        lines.append(f'{len(items)} articles published in the window mention layoffs or related terms; {current} contain an explicit current-article event with relative timing.')
        if not current:
            lines.append('The reviewed passages do not establish a new layoff event in the requested publication window. Historical, negated, conditional or unresolved-time mentions are shown separately below; this does not prove no layoffs occurred.')
        result['limitations'].append('Conservative event/timing rules; publication month alone does not date a layoff. Relative today/this-month evidence is anchored to article publication, not the query date.')
    elif plan.intent == 'revenue':
        if not plan.title:
            result.update(status='clarification_required', answer='Provide the exact article title in double quotes or with --title.')
            return result
        matched = [r for r in available if normalize(r.title) == normalize(plan.title)]
        if not matched:
            matched = [r for r in available if normalize(plan.title) in normalize(r.title)]
        if len(matched) != 1:
            result.update(status='clarification_required', answer=f'Article title matched {len(matched)} records. Provide a unique full title.',
                          candidates=[{'id': r.id, 'title': r.title, 'url': r.url} for r in matched])
            return result
        record = matched[0]
        result['retrieval'] = retrieve(plan.question, [record.id], 5)
        quantitative = revenue_passages(record.body)
        if quantitative:
            items = [base_item(record, [record.provenance['summary_sentences'][0]] + quantitative)]
            lines.append('The selected article gives these revenue-related passages verbatim. Keep the stated subject, period and forecast/growth qualifiers; these are not automatically the headline company’s realized revenue.')
            result['limitations'].append('Extractive revenue evidence, not a normalized financial metric. Tables may require adjacent row/header context; profit and valuation are not substituted for revenue.')
        else:
            result.update(status='insufficient_evidence')
            lines.append('I could not establish a numerical revenue figure in the selected article. Profit, valuation, funding and market size are not substitutes.')
            result['sources'] = [{'article_id': record.id, 'title': record.title, 'url': record.url}]
    elif plan.intent in ('ai', 'company'):
        if plan.intent == 'company' and not plan.company:
            result.update(status='clarification_required', answer='Specify the company, for example --company ServiceNow.')
            return result
        if plan.intent == 'company':
            candidates = [r for r in available if mentions(r.body, plan.company)]
            # Explicit mentions are necessary; NER predictions alone do not establish membership.
            primary = [r for r in candidates if mentions(r.title, plan.company) or
                       (mentions(r.body[:800], plan.company) and re.search(r'announc|launch|introduc|unveil', r.body[:800], re.I))]
            candidates = primary
        else:
            candidates = [r for r in available if AI.search(r.title) or r.category == 'AI']
        hits = retrieve(plan.question, [r.id for r in candidates], 50)
        result['retrieval'] = hits
        order = list(dict.fromkeys(h['metadata']['article_id'] for h in hits))
        selected = [records[i] for i in order[:5]]
        for record in selected:
            quotes = record.provenance['summary_sentences'][:2]
            items.append(base_item(record, quotes))
        lines.append(f"Selected {len(items)} {'AI stories' if plan.intent == 'ai' else 'company-related announcements'} from {len(candidates)} eligible articles using semantic search. This is a relevance-ranked selection, not an exhaustive list.")
        result['limitations'].append('Extractive overview from source lead sentences. Company matches can describe third-party news about the company, not only statements issued by it. AI eligibility uses explicit title terms/category; synonyms or incidental AI mentions may be missed.')
    if not items and result['status'] == 'answered':
        result['status'] = 'no_matches'
    unique_sources = {s['article_id']: s for s in result['sources']}
    for item in items:
        unique_sources[item['article_id']] = {k: item[k] for k in ('article_id', 'title', 'url')}
        lines.append(f"\n- [{item['title']}]({item['url']}) — published {item['published_at']}")
        if 'funding' in item:
            fund = item['funding']
            lines.append(f"  Company: {fund['company'] or 'unknown'}; amount: {fund['amount_text'] or 'undisclosed/unknown'}; round: {fund['round'] or 'unspecified'}; named investors: {', '.join(fund['investors']) or 'unknown'}; status: {fund['status']}.")
        elif 'mention_classifications' in item:
            for quote, label in zip(item['evidence'], item['mention_classifications']):
                lines.append(f"  {label}: {quote['text']}")
        elif plan.intent not in ('location', 'investors'):
            lines.extend(f"  Source excerpt: {quote['text']}" for quote in item['evidence'])
    for pending in result.get('pending_financing', []):
        unique_sources[pending['article_id']] = {k: pending[k] for k in ('article_id', 'title', 'url')}
        lines.append(f"\nPending, excluded from completed raises: [{pending['title']}]({pending['url']}) — {pending['funding']['status']}.")
    result.update(items=items, sources=list(unique_sources.values()), answer='\n'.join(lines))
    return result


class QueryEngine:
    def __init__(self, root=Path('data'), index_dir=None):
        self.root = Path(root)
        self.folder = Path(index_dir) if index_dir else self.root / 'index'
        self.embedder = None

    def answer(self, question, **options):
        plan = plan_query(question, **options)
        with writer_lock(self.root):
            self.embedder = self.embedder or LocalEmbedder(self.root / 'models/embeddings')
            collection, state = checked_index(self.root, self.folder, self.embedder)
            if state['config']['selection'] is not None:
                raise ValueError('Query answers require the full corpus index, not a pilot selection')
            records, _ = load_inputs(self.root)
            def retrieve(text, ids, count):
                if not ids:
                    return []
                vectors = validate_vectors(self.embedder.encode([text]), 1, self.embedder.dimension)
                found = collection.query(query_embeddings=vectors.tolist(), n_results=min(count, state['chunks']),
                                         where={'article_id': {'$in': ids}}, include=['documents', 'metadatas', 'distances'])
                return [{'chunk_id': ident, 'text': found['documents'][0][i],
                         'metadata': found['metadatas'][0][i], 'cosine_distance': found['distances'][0][i]}
                        for i, ident in enumerate(found['ids'][0])]
            result = answer_records(plan, records, retrieve)
            result['index_state_run'] = state['run_id']
            result['answered_at'] = utc_now()
            run_id = result['answered_at'].replace(':', '').replace('.', '').replace('+', '-')
            atomic_json(self.root / 'queries/runs' / f'{run_id}.json', result)
            atomic_json(self.root / 'queries/latest.json', result)
            return result


def render_answer(result):
    plan = result['plan']
    intro = f"Corpus only. Reference time: {plan['as_of']}. {plan['time_policy']}."
    if plan['since']:
        intro += f"\nPublication window: {plan['since']} through {plan['as_of']} (inclusive)."
    if plan['before']:
        intro += f"\nAdditional exclusive publication upper bound: {plan['before']}."
    if plan['company'] or plan['location']:
        intro += f"\nEntity filters: company={plan['company'] or 'any'}, location={plan['location'] or 'any'}."
    limits = '\n'.join('- ' + line for line in result['limitations'])
    sources = '\n'.join(f"- [{s['title']}]({s['url']})" for s in result['sources'])
    return intro + '\n\n' + result['answer'] + ('\n\nLimits:\n' + limits if limits else '') + ('\n\nSources:\n' + sources if sources else '')
