"""Offline, source-scoped extraction with auditable model/rule predictions."""
import copy
import re
from datetime import datetime, timezone
from decimal import Decimal

import spacy
import trafilatura
from lxml import html
from spacy.language import Language

from newsrag.models import ArticleRecord, Funding
from newsrag.entity_rules import refine
from newsrag.source import article_url
from newsrag.storage import sha256

EXTRACTION_VERSION = '2.0.5'
MODEL = 'en_core_web_md'

# NER's ORG includes products, technologies and roles. These generic terms are
# not companies/institutions; keep the unfiltered spans in provenance for audit.
NON_ORGANIZATIONS = {
    'ai', 'ip', 'gpu', 'mcp', 'cmdb', 'grc', 'saas', 'mou', 'mro', 'vp', 'nyse',
    'compliance', 'operational resilience', 'digital technology', 'technology centre',
    'healthtech', 'metaverse', 'managing partner', 'venture capital funds', 'vc fund',
    'aif vc fund', 'performance based logistics', 'political & regulatory', 'risks & challenges',
}


@Language.component('news_paragraph_boundaries')
def paragraph_boundaries(doc):
    for index, token in enumerate(doc[:-1]):
        if '\n' in token.text or '\n' in token.whitespace_:
            following = index + 1
            while following < len(doc) and doc[following].is_space:
                following += 1
            if following < len(doc):
                doc[following].is_sent_start = True
    return doc


def normalized(text):
    return ' '.join(re.findall(r'\w+', text.casefold()))


def load_nlp(model_folder=None):
    try:
        nlp = spacy.load(MODEL, disable=['lemmatizer'])
    except OSError as error:
        raise RuntimeError(f'Missing NLP model: run python -m spacy download {MODEL}') from error
    nlp.add_pipe('news_paragraph_boundaries', before='parser')
    if model_folder is not None:
        from newsrag.local_entities import LocalEntities
        nlp.entity_predictor = LocalEntities(model_folder)
        nlp.meta['entity_backend'] = nlp.entity_predictor.identity
    return nlp


def fingerprint(entry, nlp):
    import json
    identity = json.dumps(nlp.meta.get('entity_backend', 'spacy'), sort_keys=True)
    return sha256(f"{entry['sha256']}|{EXTRACTION_VERSION}|{spacy.__version__}|{nlp.meta['name']}|{nlp.meta['version']}|{trafilatura.__version__}|{identity}".encode())


def clean_body(container):
    clean = copy.deepcopy(container)
    for element in clean.xpath('.//script|.//style|.//noscript|.//iframe|.//form'):
        element.drop_tree()
    for element in clean.iter():
        if element.tag in {'td', 'th'}:
            # Keep table columns distinct in the fallback's plain-text output.
            element.tail = ' | ' + (element.tail or '')
        elif element.tag == 'tr':
            element.text = '\n| ' + (element.text or '')
            element.tail = '\n' + (element.tail or '')
        elif element.tag in {'br', 'div', 'p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote'}:
            # text_content() adds no separators: preserve both sides of a block,
            # including headings and nested divs next to unwrapped body text.
            element.text = '\n' + (element.text or '')
            element.tail = '\n' + (element.tail or '')
    return '\n'.join(re.sub(r'\s+', ' ', line).strip() for line in clean.text_content().splitlines() if line.strip())


def metadata_body(raw, entry):
    tree = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8'))
    title_nodes = tree.xpath('//h1[contains(concat(" ",normalize-space(@class)," ")," post-title ")]')
    title = title_nodes[0].text_content().strip() if title_nodes else ''
    if not title:
        raise ValueError('Missing article title')
    canonical = tree.xpath('//link[@rel="canonical"]/@href')
    if len(canonical) != 1 or article_url(canonical[0]) != entry['final_url']:
        raise ValueError('Missing/ambiguous canonical or canonical/final URL mismatch')
    dates = tree.xpath('//*[@itemprop="datePublished"]/@title')
    if len(set(dates)) != 1:
        raise ValueError('Missing/ambiguous publication date')
    stamp = datetime.fromisoformat(dates[0])
    if stamp.tzinfo is None:
        raise ValueError('Publication timezone missing; fetch time is not a substitute')
    authors = list(dict.fromkeys(s.strip() for s in tree.xpath('//*[@itemprop="author"]//*[@itemprop="name"]/text()') if s.strip()))
    containers = tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," post-body ")]')
    if len(containers) != 1:
        raise ValueError('Missing/ambiguous source article container')
    reference = clean_body(containers[0])
    # Compare actual publisher text spans, not the fallback against itself.
    spans = [normalized(t) for t in containers[0].xpath('.//text()[not(ancestor::script) and not(ancestor::style) and not(ancestor::noscript) and not(ancestor::iframe) and not(ancestor::form)]') if len(normalized(t)) > 40]
    if len(reference) < 200 or not spans:
        raise ValueError('Article body is empty/too short or lacks comparison spans')
    generic = trafilatura.extract(raw, url=entry['final_url'], include_comments=False, include_tables=True) or ''
    missing_generic = sum(span not in normalized(generic) for span in spans)
    body, method = (reference, 'IndianWeb2 post-body/lxml') if missing_generic else (generic, 'trafilatura')
    if any(span not in normalized(body) for span in spans):
        raise ValueError('Body extractor lost publisher text spans')
    return title, authors, stamp.astimezone(timezone.utc), body, {
        'published_at_original': dates[0], 'canonical_url': canonical[0],
        'body_method': method, 'reference_spans': len(spans),
        'generic_missing_spans': missing_generic, 'missing_output_spans': 0}


def entity_predictions(doc, primary_company=None):
    values = {'companies': [], 'people': [], 'locations': []}
    evidence = []
    for ent in doc.ents:
        field = {'ORG': 'companies', 'PERSON': 'people', 'GPE': 'locations', 'LOC': 'locations'}.get(ent.label_)
        if not field:
            continue
        value = ent.text.strip()
        if '\n' in value or 'http' in value or value.casefold() in {'partner', 'co-founder', 'ceo', 'trust hubs', 'iphones', 'playstations'}:
            continue
        if field == 'locations' and value.casefold() in {'bangalore', 'bengaluru'}:
            value = 'Bengaluru'
        if value and value.casefold() not in {x.casefold() for x in values[field]}:
            values[field].append(value)
        evidence.append({'field': field, 'value': value, 'text': ent.text,
                         'start': ent.start_char, 'end': ent.end_char, 'label': ent.label_})
    # Context takes precedence over a model label; retain exact supporting spans.
    corrections = []
    name = r'[A-Z][A-Za-z’\'-]+(?: [A-Z][A-Za-z’\'-]+){1,3}'
    for match in re.finditer(rf'(?P<name>{name}),\s*(?i:co-founder|founder|CEO|COO|chief|managing partner|partner)\b', doc.text):
        # Require actual title-case names despite case-insensitive role matching.
        candidate = match.group('name')
        if all(part[0].isupper() for part in candidate.split()):
            corrections.append(('people', candidate, match.start('name'), match.end('name')))
    if primary_company:
        match = re.search(re.escape(primary_company), doc.text, re.I)
        if match:
            corrections.append(('companies', match.group(), match.start(), match.end()))
    for field, value, start, end in corrections:
        for other in values:
            values[other] = [v for v in values[other] if v.casefold() != value.casefold()]
        values[field].append(value)
        evidence.append({'field': field, 'value': value, 'text': doc.text[start:end],
                         'start': start, 'end': end, 'label': 'explicit_role_or_headline_subject'})
    orgs = {x.casefold() for x in values['companies']}
    values['locations'] = [v for v in values['locations'] if v.casefold() not in orgs]
    values['people'] = [v for v in values['people'] if v.casefold() not in orgs]
    # Prefer full personal names; collapse first-name references to those names.
    full_people = [v for v in values['people'] if 2 <= len(v.split()) <= 4 and not re.search(r'\d|[&/]', v)]
    personal_tokens = {v.split()[0].casefold() for v in full_people}
    values['people'] = full_people
    cleaned_orgs = []
    for value in values['companies']:
        value = re.sub(r'^(?:the)\s+', '', value, flags=re.I)
        value = re.sub(r'[’\']s$', '', value).strip()
        if value.casefold() in NON_ORGANIZATIONS or value.casefold() in personal_tokens:
            continue
        if re.search(r'\b(?:AI (?:Passport|Platform|Cost Management)|Control Tower|Asset Management|Configuration Management Database|Product Marketing|SEBI-registered)\b', value, re.I):
            continue
        if value.casefold() not in {v.casefold() for v in cleaned_orgs}:
            cleaned_orgs.append(value)
    values['companies'] = cleaned_orgs
    # Explicit mention matching prevents NER misses for the assignment's key alias.
    for match in re.finditer(r'\b(?:Bengaluru|Bangalore)\b', doc.text, re.I):
        if 'Bengaluru' not in values['locations']:
            values['locations'].append('Bengaluru')
        evidence.append({'field': 'locations', 'value': 'Bengaluru', 'text': match.group(),
                         'start': match.start(), 'end': match.end(), 'label': 'explicit_alias'})
    return refine(values, evidence, doc.text)


MONEY = re.compile(r'(?P<currency>₹|INR\s*|Rs\.?\s*|US\$\s*|USD\s*|\$\s*|EUR\s*|€\s*|GBP\s*|£\s*)\s*(?P<number>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>crores?|cr\b|lakhs?|lacs?|billion|million|bn\b|mn\b|[MB]\b)?', re.I)


def money_value(match):
    currency_text = match['currency'].strip().casefold()
    currency = ('INR' if currency_text.startswith(('₹', 'inr', 'rs')) else
                'EUR' if currency_text.startswith(('€', 'eur')) else
                'GBP' if currency_text.startswith(('£', 'gbp')) else 'USD')
    unit = (match['unit'] or '').casefold()
    scale = 10000000 if unit.startswith('cr') else 100000 if unit.startswith(('lakh', 'lac')) else 1000000000 if unit in {'billion', 'bn', 'b'} else 1000000 if unit in {'million', 'mn', 'm'} else 1
    return Decimal(match['number'].replace(',', '')) * scale, currency


def funding_details(title, doc):
    warnings = []
    # Announced raises only. Contract wins, IPO plans and market sizes are excluded.
    trigger = re.search(r'\b(raises|raised|secures|secured|gets backing|backs|invests|gets)\b', title, re.I)
    if not trigger or re.search(r'\b(IPO|contract|order|deal|FDI|support track|helps?)\b', title, re.I):
        return None, warnings
    if trigger.group().casefold() == 'gets' and 'financial support' not in title.casefold():
        return None, warnings
    sentences = [s for s in doc.sents if re.search(r'\b(raised|raises|funding|round|investment|invested|backing|seed|bond|NCD|financial support|mobilize|fundraising)\b', s.text, re.I)]
    if not sentences:
        return None, ['funding_headline_without_clear_body_evidence']
    # Only early announcement evidence; never use About Fund paragraphs for money.
    sentences = [s for s in sentences if s.start_char < min(len(doc.text), 2200)]
    if 'financial support' in title.casefold():
        sentences = [s for s in sentences if re.search(r'financial support|investment.*programme|provided.*debt', s.text, re.I)]
    if not sentences:
        return None, ['funding_announcement_not_in_lead']
    evidence = [s.text.strip() for s in sentences[:3]]
    headline_money = [m for m in MONEY.finditer(title) if not re.match(r'\s*(?:valuation|valued|market)', title[m.end():], re.I)]
    amount = currency = amount_text = None
    if headline_money:
        match = headline_money[0]
        # A number near "valuation" must not be treated as new money raised.
        local = title[max(0, match.start()-12):match.end()+18]
        if not re.search(r'valuation|valued', local, re.I):
            candidate_amount, candidate_currency = money_value(match)
            corroborated = any(money_value(m) == (candidate_amount, candidate_currency) for s in evidence
                               if re.search(r'raised|raises|secured|funding round|(?:seed|series) funding|invested|financial support|mobilize|raising', s, re.I)
                               for m in MONEY.finditer(s))
            if corroborated:
                amount, currency, amount_text = candidate_amount, candidate_currency, match.group().strip()
    if amount is None:
        warnings.append('funding_amount_unknown_or_ambiguous')
    before = re.split(r'\b(?:unveils?|launches?|announces?)\b', title[:trigger.start()], flags=re.I)[0].strip(' ,:')
    company = before if trigger.group().casefold() not in {'backs', 'back', 'invests', 'invest'} and before else None
    if company:
        company = re.sub(r'^(?:Bengaluru|Bangalore|Mumbai|Delhi|India|Indian)[- ]based\s+', '', company, flags=re.I)
    if not company:
        backed = re.search(r'\bbacks?\s+(.+?)(?=\s+with\b|\s+to\b|$)', title, re.I)
        if backed:
            company = backed.group(1).strip()
        else:
            target = re.search(r'\bacross\s+(.+?)[’\']s\b', title, re.I)
            if target:
                company = target.group(1).strip()
            else:
                warnings.append('funded_company_needs_review')
    if company and re.search(r'[’\']s', company):
        stem = re.split(r'[’\']s', company)[0].casefold()
        candidates = [e.text for e in doc.ents if e.label_ == 'ORG' and stem in e.text.casefold() and 'company' in e.text.casefold()]
        if candidates:
            company = candidates[0]
    if re.search(r'\bbond\b', title, re.I):
        issuer = re.search(r'\bwhen\s+([A-Z][A-Za-z]+ Finance Limited)\b', doc.text)
        company = issuer.group(1) if issuer else None
        if company is None:
            warnings.append('bond_issuer_needs_review')
    combined = title + '\n' + '\n'.join(evidence)
    stage = re.search(r'\b(pre[- ]seed|seed|pre[- ]series\s+[A-F]|series\s+[A-F](?:\d)?|pre[- ]A)\b', combined, re.I)
    investors = []
    def add_names(text):
        text = re.sub(r'^(?:existing\s+)?investors?\s+', '', text.strip(), flags=re.I)
        text = re.split(r',\s*(?:co-founder|founder|CEO|COO|chief|who)\b', text, flags=re.I)[0]
        text = re.split(r'\b(?:with|to|which)\b', text, maxsplit=1, flags=re.I)[0]
        for name in re.split(r'\s+and\s+|,\s*|\s*&\s*(?=and\b|others\b|angel investors\b)', text, flags=re.I):
            name = re.sub(r'^(?:and|&)\s+', '', name.strip(' ,.;'), flags=re.I)
            name = re.sub(r'\s*\(in personal capacity\)', '', name, flags=re.I)
            if name and len(name) < 100 and not re.search(r'\b(?:others|existing investors|angel investors|undisclosed|participation|global investors)\b', name, re.I):
                if name not in investors:
                    investors.append(name)
    for sentence in sentences[:3]:
        text = sentence.text
        for match in re.finditer(r'(?:led by|participation from|backing from|investment from|funding round from|involving existing backers)\s+(.+?)(?=\s+(?:with|and)\s+(?:follow-on investment|participation|investment)|,\s*(?:with|co-founder|founder|as well)|\.|;|$)', text, re.I):
            add_names(match.group(1))
        if re.search(r'\b(?:has led|led a|has backed)\b', text, re.I):
            add_names(text.split(',')[0])
        if re.search(r'\bjoined the round as an angel\b', text, re.I):
            angel = re.search(r"([A-Z][A-Za-z'-]+(?: [A-Z][A-Za-z'-]+){1,3}),\s*(?:COO|CEO|Founder|Co-founder)[^.]*joined the round as an angel", text)
            if angel:
                add_names(angel.group(1))
        investor = re.search(r'^(.+?)\s+has invested\b', text, re.I)
        if investor:
            add_names(re.sub(r'^\w+[- ]based\s+', '', investor.group(1), flags=re.I))
    # Headline relationships can rescue a sparse lead, but names must occur in
    # the original body too, and their body context is added as evidence.
    headline_relation = re.search(r'(?:backing from|valuation from)\s+(.+?)(?=\s+to\s+|$)', title, re.I)
    if headline_relation:
        old = list(investors)
        add_names(headline_relation.group(1))
        checked = list(old)
        for investor in investors:
            if investor in old:
                continue
            # "Person's Fund" identifies the fund as investor, not its owner.
            investor = re.split(r'[’\']s\s+', investor)[-1]
            match = re.search(re.escape(investor), doc.text, re.I)
            if match:
                checked.append(investor)
                evidence.append(doc.text[max(0, match.start()-65):min(len(doc.text), match.end()+100)])
        investors = checked
    status = 'closing' if re.search(r'\bis closing\b', '\n'.join(evidence), re.I) else 'reported'
    kind = 'strategic_investment' if trigger.group().casefold() == 'invests' else 'venture'
    if re.search(r'\b(?:NCD|bond)\b', title, re.I):
        kind = 'debt'
    if 'financial support' in title.casefold():
        kind = 'debt' if 'convertible debt' in doc.text.casefold() else 'financial_support'
        status = 'committed'
        warnings.append('financial_support_committed_not_proven_disbursed')
        board = re.search(r'\bThe ([A-Z][A-Za-z ]+ Board(?: \([A-Z]+\))?)', doc.text)
        if board:
            investors = [board.group(1)]
    if status == 'closing':
        warnings.append('funding_round_is_closing_not_reported_closed')
    if not investors:
        warnings.append('funding_investors_unknown_or_unparsed')
    warnings.append('funding_investor_list_not_guaranteed_complete')
    if re.search(r'\bshareholders\b', doc.text, re.I):
        warnings.append('shareholder_list_requires_full_manual_review')
    round_name = stage.group() if stage else ('NCD' if re.search(r'\bNCD\b', title) else 'bond' if re.search(r'\bbond\b', title, re.I) else None)
    if 'financial support' in title.casefold():
        round_name = 'OCD' if 'convertible debt' in doc.text.casefold() else None
    return Funding(company=company, amount=amount, currency=currency, amount_text=amount_text,
                   round=round_name, investors=investors, evidence=evidence, status=status, kind=kind), warnings


def extract_article(raw, entry, nlp):
    title, authors, published, body, provenance = metadata_body(raw, entry)
    doc = nlp(body)
    funding, warnings = funding_details(title, doc)
    subject = funding.company if funding else re.split(r'\b(?:launches?|announces?|expands?|partners?|introduces?|secures?|raises?|wins?|enters?|unveils?|marks?|hits?)\b', title, flags=re.I)[0].strip()
    primary = subject if subject and len(subject) < 65 else None
    values, entity_evidence = (nlp.entity_predictor.predict(body, primary) if hasattr(nlp, 'entity_predictor')
                               else entity_predictions(doc, primary))
    if funding:
        for investor in funding.investors:
            if not re.search(r'\b(?:Capital|Fund|Partners|Foundation|Ventures|Combinator|Labs|AJVC)\b', investor):
                continue
            match = re.search(re.escape(investor), body, re.I)
            if match:
                name = re.sub(r'^the\s+', '', match.group(), flags=re.I)
                values['companies'].append(name)
                entity_evidence.append({'field':'companies', 'value':name, 'text':match.group(),
                                        'start':match.start(), 'end':match.end(), 'label':'funding_relationship_org_suffix'})
        values['companies'] = sorted(set(values['companies']), key=lambda value: (value.casefold(), value))
    warnings.append('entities_are_model_and_rule_predictions_not_exhaustive_verified_lists')
    sentences = [s.text.strip() for s in doc.sents if len(s.text.strip()) >= 45 and re.search(r'[.!?][”\"\']?$', s.text.strip())]
    if len(sentences) < 2:
        raise ValueError('Fewer than two complete source sentences for summary')
    selected = sentences[:3]
    if not authors:
        warnings.append('missing_author_byline')
    if funding:
        category = 'funding'
    elif re.search(r'\b(layoffs?|job cuts?|redundan\w+)\b', title, re.I):
        category = 'layoffs'
    elif re.search(r'\bAI\b|artificial intelligence', title, re.I):
        category = 'AI'
    else:
        labels = {x.casefold() for x in entry['discovery'].get('labels', [])}
        category = 'technology' if 'technology' in labels else 'business' if labels & {'business', 'startups'} else 'other'
    provenance.update(raw_path=entry['raw_path'], raw_sha256=entry['sha256'],
                      extraction_version=EXTRACTION_VERSION, fingerprint=fingerprint(entry, nlp),
                      nlp_model=MODEL, nlp_version=nlp.meta['version'], summary_method='extractive_lead_sentences',
                      entity_backend=nlp.meta.get('entity_backend', 'spacy_test_or_baseline'),
                      summary_sentences=selected, entity_evidence=entity_evidence,
                      category_method='headline_rules_then_source_labels', source_labels=entry['discovery'].get('labels', []))
    return ArticleRecord(id=entry['id'], url=entry['final_url'], title=title, author=authors,
                         published_at=published, body=body, summary=' '.join(selected), funding=funding,
                         category=category, provenance=provenance, warnings=warnings, **values)
