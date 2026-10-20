"""Semantic operation selection with explicit, validated query constraints."""
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


GENERIC_TARGETS = {'recent', 'latest', 'the', 'any', 'company', 'companies', 'organization', 'group',
                   'ai', 'artificial intelligence', 'machine learning', 'funding', 'funding rounds',
                   'layoffs', 'job cuts', 'workforce reductions', 'staff cuts', 'revenue', 'sales',
                   'news', 'business', 'technology', 'startups', 'startup', 'investors', 'investor'}
LAYOFF_TERMS = re.compile(
    r'\b(?:layoffs?|laid off|lay off|job cuts?|downsizing|redundan\w*|'
    r'cut(?:s|ting)?\s+(?:\d[\d,]*\s+)?(?:jobs|positions)|'
    r'(?:employees|workers|staff|people)\s+(?:being\s+|were\s+|will be\s+)?let go|'
    r'(?:workforce|staff|headcount) (?:cuts?|reductions?))\b', re.I)


def trim_target(value):
    """Keep a named target separate from supported trailing time/scope phrases."""
    value = re.split(
        r'\s+(?:(?:in|over|during|within|for)\s+(?:the\s+)?)?'
        r'(?:(?:last|past|previous)\s+(?:\d+|seven|thirty)\s+days?|'
        r'(?:last|past|previous)\s+week|(?:this|last|previous)\s+month|recently|lately)\b',
        value, maxsplit=1, flags=re.I)[0]
    value = re.split(r'\s+(?:in|from)\s+(?:this|the)\s+collection\b', value, maxsplit=1, flags=re.I)[0]
    value = re.split(r'\s+(?:in|during|for)\s+20\d{2}\b|\s+(?:this|last|previous)\s+year\b',
                     value, maxsplit=1, flags=re.I)[0]
    return value.strip(' .?"')


def company_target(question):
    patterns = [
        r'^(?:(?:please\s+)?(?:tell me about|show me|give me|summari[sz]e|list|what are|what were)\s+)?'
        r"(.+?)(?:['’]s|['’])\s+(?:(?:latest|recent|new)\s+)*(?:product\s+)?"
        r'(?:launches|announcements|updates|releases|news)\b',
        r'what (?:has|did|have) (.+?)\s+(?:announc\w*|launch\w*|introduc\w*|unveil\w*|releas\w*)\b',
        r'^(?:(?:show|give)(?: me)?\s+)?(.+?)\s+company updates\b',
        r'(?:announcements?|updates?|developments?|news|(?:product\s+)?launches|(?:product\s+)?releases)'
        r'\s+(?:from|about|on|by|at)\s+(.+?)(?:\?|$)',
        r"what(?: is|'s|’s) new (?:at|with|from) (.+?)(?:\?|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question, re.I)
        if match:
            target = trim_target(match.group(1))
            # A topic noun phrase is not a company. Keep names such as Novus AI
            # and AI Dynamics intact rather than globally prioritizing AI words.
            if re.fullmatch(r'(?:ai|artificial intelligence|machine learning)\s+'
                            r'(?:tools|technology|technologies|developments|research|news|stories)',
                            normalize(target)):
                continue
            if normalize(target) not in GENERIC_TARGETS:
                return target or None
    # A proper name can be bound even when the rest of the question uses new
    # wording. This only supplies a slot; it never chooses the operation.
    match = re.search(r'(?i:\b(?:at|by|from|with)\s+)([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,4})', question)
    if match and normalize(match.group(1)) not in GENERIC_TARGETS:
        return trim_target(match.group(1))
    return None


def location_target(question):
    match = re.search(r'(?:mention(?:s|ing)?|referr?ing to|refer(?:s)? to|references?(?: to)?|\bnam(?:e|es|ing)|\bin)\s+(.+?)[.?]*$',
                      question, re.I)
    return trim_target(match.group(1)) if match else None


def location_constraint(question):
    """Extract an explicit place phrase independently of the requested operation.

    This is a body-mention filter, not an inference about company headquarters.
    Funder phrases ("funding from X") are deliberately not location syntax.
    """
    text = re.sub(r'["“][^"”]*["”]', 'the quoted target', question)
    # Overlapping matches allow "in one round in Pune" to reject the count
    # phrase and still inspect the later, genuine place phrase.
    patterns = [r'(?=\bin\s+(.+?)(?:[.?]|$))',
                r'\b(?:stories|articles|reports|news)\b.*?\bfrom\s+(.+?)(?:[.?]|$)']
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            target = trim_target(match.group(1))
            target = re.split(r'\s+(?:raised|secured|received|announced|that|which|who|this|during)\b',
                              target, maxsplit=1, flags=re.I)[0].strip()
            if count_condition(normalize(target)) is not None:
                continue
            if re.match(r'^(?:an?\s+)?(?:pre[-\s]?seed|seed|(?:pre[-\s]?)?series\b|'
                        r'pre[-\s][a-z]\b|bridge\b)', target, re.I):
                continue
            if (not target or re.match(r'^(?:the|this|our|last|past|previous|recent|more|multiple|at|'
                                       r'exactly|only|one|single|once|twice|two|three|several|each|every|any|all|seed|series|\d+)\b', target, re.I)
                    or normalize(target) in {'ai', 'artificial intelligence', 'machine learning',
                                             'funding', 'technology', 'business', 'total'}):
                continue
            return target
    return None


def normalize(text):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold()))


def catalog_mentions(question, names):
    """Resolve named slots from current corpus vocabulary, independent of syntax."""
    text = re.sub(r'["“][^"”]*["”]', '', question)
    hits = []
    for name in sorted(set(names), key=lambda n: (-len(n), n.casefold())):
        if len(name.strip()) < 3 or normalize(name) in GENERIC_TARGETS:
            continue
        flags = 0 if name.isupper() and len(name) <= 4 else re.I
        for match in re.finditer(r'(?<!\w)' + re.escape(name) + r'(?!\w)', text, flags):
            if not any(match.start() >= left and match.end() <= right for left, right, _ in hits):
                hits.append((match.start(), match.end(), name))
    return list(dict.fromkeys(name for _, _, name in sorted(hits)))


class CountCondition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    unit: Literal['rounds', 'companies']
    comparison: Literal['eq', 'gt', 'gte', 'lt', 'lte']
    value: int = Field(ge=0)


def count_condition(q):
    """Parse an arithmetic constraint, without choosing the query operation."""
    numbers = {word: value for value, word in enumerate(
        ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'))}
    q = re.sub(r'\bonce\b', 'one round', q)
    q = re.sub(r'\btwice\b', 'two rounds', q)
    number = r'(?:\d+|' + '|'.join(numbers) + r'|single|lone)'
    match = re.search(r'\b(?:(exactly|only|at least|at most|more than|less than|fewer than|over|under)\s+)?'
                      r'(' + number + r')\s+(?:(?:distinct|different|funding|financing|investment)\s+)*'
                      r'(rounds?|raises?|deals?|financings?|companies|startups?|businesses)\b', q)
    if match:
        operator, raw, unit = match.groups()
        value = int(raw) if raw.isdigit() else 1 if raw in {'single', 'lone'} else numbers[raw]
        comparison = {'at least': 'gte', 'at most': 'lte', 'more than': 'gt', 'over': 'gt',
                      'less than': 'lt', 'fewer than': 'lt', 'under': 'lt'}.get(operator, 'eq')
        if not operator and re.match(r'\s+or more\b', q[match.end():]):
            comparison = 'gte'
        return CountCondition(unit='companies' if unit.startswith(('compan', 'startup', 'business')) else 'rounds',
                              comparison=comparison, value=value)
    match = re.search(r'\b(?:multiple|several)\s+(?:(?:funding|distinct|different|separate)\s+)*'
                      r'(rounds?|raises?|deals?|financings?|companies|startups?|businesses)\b', q)
    if match:
        return CountCondition(unit='companies' if match.group(1).startswith(('compan', 'startup', 'business')) else 'rounds',
                              comparison='gt', value=1)
    return None


def investor_clarification(condition):
    if condition.unit != 'rounds':
        return ('This operation counts distinct funding rounds, not distinct companies. '
                'Use a round-count request or clarify the required company aggregation.')
    if not ((condition.comparison == 'gt' and condition.value == 1) or
            (condition.comparison == 'gte' and condition.value == 2)):
        return ('This operation supports investors in more than one distinct funding round. '
                f'Your requested condition ({condition.comparison} {condition.value}) needs a different '
                'calculation and will not be silently replaced by repeated-investor results.')
    return None


def canonical_funding_round(value):
    """Normalize stage spelling without equating different stages."""
    text = re.sub(r'\b(?:funding|financing|round)\b', '', (value or '').casefold())
    text = re.sub(r'[-\s]+', ' ', text).strip()
    text = re.sub(r'\bpre\s*seed\b', 'pre seed', text)
    text = re.sub(r'\bpre\s*series\b', 'pre series', text)
    text = re.sub(r'^pre ([a-z])$', r'pre series \1', text)
    return text


def funding_constraints(question):
    """Bind supported round stages; clarify filters the executor cannot apply.

    This validates the selected operation, never chooses an operation.
    """
    text = re.sub(r'["“][^"”]*["”]', '', question)
    rounds = list(dict.fromkeys(canonical_funding_round(match.group()) for match in re.finditer(
        r'\b(?:pre[-\s]?seed|seed|(?:pre[-\s]?)?series\s+[a-z](?:\d+)?|pre[-\s][a-z]|bridge)\b', text, re.I)))
    stage = rounds[0] if len(rounds) == 1 else None
    if len(rounds) > 1:
        return None, 'Specify one funding stage. Multiple-stage AND/OR filters are not supported.'
    if re.search(r'\bseries\s+[a-z](?:\d+)?\s*(?:[/,&]|\band\b|\bor\b)\s*[a-z]\b', text, re.I):
        return None, 'Specify one funding stage. Multiple-stage AND/OR filters are not supported.'
    if re.search(r'\bseries\b', text, re.I) and not any('series' in value for value in rounds):
        return stage, 'Specify an exact funding stage, such as seed or Series A.'
    if re.search(r'\b(?:early[- ]stage|late[- ]stage|growth|angel)\s+(?:funding|financing|rounds?)\b', text, re.I):
        return stage, 'That funding-stage classification is not supported. Specify an exact stage such as seed or Series A.'
    monetary = re.search(r'[$₹€£]|\b(?:USD|INR|EUR|GBP|rupees?|dollars?|euros?|pounds?|'
                        r'millions?|billions?|crores?|lakhs?|lacs?)\b|\b\d[\d,.]*\s*[kmb]\b', text, re.I)
    bare_threshold = re.search(r'\b(?:above|below|over|under|more than|less than|at least|at most|between)\s+\d', text, re.I)
    if monetary or (bare_threshold and count_condition(normalize(text)) is None):
        return stage, ('Funding amount/currency filters are not supported. I cannot apply that monetary '
                       'condition or convert currencies, so I will not return an unrestricted funding list. '
                       'Ask for funding amounts without a monetary filter, optionally for one round stage.')
    if re.search(r'\b(?:led|co[- ]led|backed|funded|financed|supported|sponsored)\s+by\b|'
                 r'\b(?:funding|investment|backing|capital|money|financing|rounds?|raised|secured|'
                 r'participation)\s+(?:from|by|with|involving)\b|'
                 r'\b(?:from|with|involving)\s+(?:(?:multiple|several|\d+)\s+)?investors?\b|'
                 r'\b(?:invested\s+in|[\w&.-]+-backed)\b|'
                 r'\b(?:did|has|have)\s+.+?\s+(?:fund|back|finance|invest)\b', text, re.I):
        return stage, ('Investor and lead-investor filters are not supported. Extracted investor lists '
                       'can be incomplete and do not reliably identify who led a round. I will not '
                       'substitute a company body-mention filter or an unrestricted funding list.')
    return stage, None


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    intent: Literal['ai', 'funding', 'company', 'location', 'layoffs', 'investors', 'revenue', 'unsupported']
    question: str
    as_of: AwareDatetime
    since: AwareDatetime | None = None
    before: AwareDatetime | None = None
    company: str | None = None
    location: str | None = None
    title: str | None = None
    time_policy: str = 'All stored publication dates through the reference instant'
    count_condition: CountCondition | None = None
    funding_round: str | None = Field(default=None, exclude_if=lambda value: value is None)
    # Emitted as the result's answer/status, without changing existing serialized plans.
    clarification: str | None = Field(default=None, exclude=True)

    @model_validator(mode='after')
    def dates(self):
        self.as_of = self.as_of.astimezone(timezone.utc)
        if self.since:
            self.since = self.since.astimezone(timezone.utc)
            if self.since > self.as_of:
                raise ValueError('since must not be after as_of')
        if self.before:
            self.before = self.before.astimezone(timezone.utc)
            if self.since and self.since >= self.before:
                raise ValueError('since must be before the exclusive upper bound')
        return self


def plan_query(question, *, as_of=None, intent=None, company=None, location=None, title=None, since=None, before=None,
               semantic_route=None, entity_catalog=None):
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Reference time must have a timezone')
    now = now.astimezone(timezone.utc)
    explicit_location = location is not None
    explicit_intent = intent is not None
    if not question.strip():
        raise ValueError('Question cannot be empty')
    # Preserve negation before punctuation normalization splits "didn't".
    q = normalize(re.sub(r"n['’]t\b", ' not', question, flags=re.I))
    inferred_company = company_target(question) if not company else company
    clarification = None
    if intent is None:
        if semantic_route is None:
            intent = 'unsupported'
            clarification = 'Semantic operation recognition is required. Supply a router or an explicit --intent.'
        else:
            decision = semantic_route(question)
            intent = decision['intent'] if isinstance(decision, dict) else decision
            if isinstance(decision, dict) and not decision['accepted']:
                clarification = ('I could not select a sufficiently clear operation from the question meaning. '
                                 'Please clarify the request or specify --intent.')
    # Slot parsing and arithmetic checks never override the semantic operation.
    constraint_q = normalize(re.sub(r'["“][^"”]*["”]', '', question))
    condition = count_condition(constraint_q)
    funding_round = None
    if intent in ('funding', 'investors'):
        funding_round, funding_reason = funding_constraints(question)
        clarification = clarification or funding_reason
        if intent == 'investors' and funding_round and not funding_reason:
            clarification = clarification or ('Funding-stage filters are not supported for investor aggregation. '
                                             'Ask for a stage-filtered funding list or an unfiltered repeated-investor calculation.')
    named_places = catalog_mentions(question, (entity_catalog or {}).get('locations', ()))
    named_companies = catalog_mentions(question, (entity_catalog or {}).get('companies', ()))
    shared_names = {normalize(name) for name in named_places} & {normalize(name) for name in named_companies}
    if intent == 'location':
        # A geographic mention must not acquire a second company filter merely
        # because extraction assigned the same name to both entity types.
        named_companies = [name for name in named_companies if normalize(name) not in shared_names]
    elif intent == 'company' and inferred_company and normalize(inferred_company) in shared_names:
        named_places = [name for name in named_places if normalize(name) != normalize(inferred_company)]
    if intent != 'unsupported' and not company and named_companies:
        if len(named_companies) == 1:
            company = named_companies[0]
        else:
            clarification = clarification or 'Several companies were named. Specify one company with --company.'
    if intent != 'unsupported' and not location and named_places:
        canonical = list(dict.fromkeys('Bengaluru' if normalize(p) in {'bengaluru', 'bangalore'} else p for p in named_places))
        if len(canonical) == 1:
            location = canonical[0]
        else:
            clarification = clarification or 'Several places were named. Specify one location with --location.'
    if intent == 'company' and not company:
        company = inferred_company if inferred_company not in named_places else None
    if intent == 'investors':
        condition = condition or CountCondition(unit='rounds', comparison='gt', value=1)
        clarification = clarification or investor_clarification(condition)
        if re.search(r'\b(?:exactly|only|at least|at most|more than|less than|fewer than)\b'
                     r'.{0,40}\b(?:rounds?|companies|startups?)\b', constraint_q) and count_condition(constraint_q) is None:
            clarification = 'I could not parse that count condition. Specify a supported numeric round condition.'
    elif condition is not None and intent != 'unsupported':
        clarification = clarification or ('The selected operation does not implement this round/company-count '
                         'condition. Please clarify the aggregation; I will not return an unrelated funding list.')
    if intent == 'revenue' and not explicit_intent and re.search(r'\bearn(?:ed|s|ings)?\b', q) and not re.search(
            r'\brevenues?\b|\bturnover\b|\bsales\b', q):
        clarification = clarification or ('Do you mean revenue or profit? Earnings are ambiguous. '
                         'Ask explicitly for revenue or use --intent revenue.')
    if intent != 'unsupported' and re.search(r'\b(?:compare|comparison|versus|vs)\b', constraint_q):
        clarification = clarification or ('Comparative calculations are not implemented by these operations. '
                         'Ask one operation at a time or specify the required comparison.')
    # Check every recognized operation, not just unresolved semantic wording.
    # Quoted titles/names describe targets rather than negative query filters.
    filter_text = re.sub(r'["“][^"”]*["”]', '', question)
    filter_text = normalize(re.sub(r"n['’]t\b", ' not', filter_text, flags=re.I))
    if intent != 'unsupported' and re.search(
            r'\b(?:no|not|never|without|except|excluding|exclude|neither|nor)\b|\bother than\b', filter_text):
        clarification = ('Negative and exclusion filters are not supported. Please ask for a positive '
                         'match, or split the request into separate queries; I will not silently '
                         'return the opposite set.')
    if not location and re.search(r'\b(?:bengaluru|bangalore)\b', q):
        location = 'Bengaluru'
    if intent == 'location' and not location:
        location = location_target(question)
    elif not location:
        location = location_constraint(question)
    requested_place = location_target(question) if intent == 'location' else location_constraint(question)
    if not explicit_location and requested_place and re.search(r'\b(?:and|or)\b|[,;]', requested_place, re.I):
        clarification = clarification or ('Please specify one location with --location. Multiple locations '
                         'and AND/OR combinations require separate queries; I will not treat them as one place.')
    if intent == 'company' and company and location:
        company = re.sub(r'\s+in\s+' + re.escape(location) + r'\s*$', '', company, flags=re.I)
    if intent == 'revenue' and not title:
        match = re.search(r'["“](.+?)["”]', question)
        title = match.group(1) if match else None
    policy = 'All stored publication dates through the reference instant'
    # Explicit CLI bounds take precedence over natural-language defaults as a pair.
    if since is None and before is None:
        date_text = re.sub(r'["“][^"”]*["”]', '', question)
        for target in named_companies + named_places:
            if target:
                date_text = re.sub(r'(?<!\w)' + re.escape(target) + r'(?!\w)', '', date_text, flags=re.I)
        date_q = normalize(date_text)
        residual_dates = re.sub(
            r'\b(?:last|past|previous)\s+(?:\d+|seven|thirty)\s+days?\b|'
            r'\b(?:last|past|previous)\s+week\b|\b(?:this|last|previous)\s+(?:month|year)\b|'
            r'\b(?:in|during|for)\s+20\d{2}\b', '', date_q)
        unsupported_dates = re.search(
            r'\b(?:yesterday|tomorrow|today|january|february|march|april|may|june|july|august|'
            r'september|october|november|december|jan|feb|apr|jun|jul|aug|sep|sept|oct|nov|dec|'
            r'monday|tuesday|wednesday|thursday|friday|saturday|sunday|quarter|q[1-4]|20\d{2})\b|'
            r'\b(?:last|past|previous|next)\s+(?:the\s+)?(?:\w+\s+){0,2}'
            r'(?:days?|weeks?|months?|years?|hours?)\b|'
            r'\b(?:days?|weeks?|months?|years?|hours?)\b', residual_dates)
        year_match = re.search(r'\b(?:in|during|for)\s+(20\d{2})\b', date_q)
        relative_year = re.search(r'\b(this|last|previous)\s+year\b', date_q)
        days = re.search(r'(?:last|past|previous)\s+(\d+|seven|thirty)\s+days?', q)
        if unsupported_dates:
            if intent != 'unsupported':
                clarification = clarification or ('I could not safely interpret the requested publication dates. '
                                'Use --since and --before with timezone-bearing ISO timestamps, or a supported '
                                'day/week/month/year window.')
        elif year_match or relative_year:
            year = int(year_match.group(1)) if year_match else now.year - int(relative_year.group(1) != 'this')
            if year > now.year:
                clarification = clarification or 'That publication year is after the reference time. Change --as-of or choose an earlier year.'
            else:
                since = now.replace(year=year, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                before = since.replace(year=year + 1)
                policy = 'Requested UTC calendar year by publication time; reference-time cap retained'
        elif days:
            number = {'seven': 7, 'thirty': 30}.get(days.group(1))
            number = int(days.group(1)) if number is None else number
            if not 1 <= number <= 3660:
                raise ValueError('Day window must be between 1 and 3660')
            since = now - timedelta(days=number)
            policy = f'Rolling last {number} days by publication time; not transaction/event date'
        elif 'last month' in q or 'previous month' in q:
            before = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            since = (before - timedelta(days=1)).replace(day=1)
            policy = 'Previous UTC calendar month by publication time; exclusive upper bound'
        elif re.search(r'(?:last|past|previous) week', q):
            since = now - timedelta(days=7)
            policy = 'Week interpreted as rolling seven days by publication time'
        elif 'this month' in q or intent == 'layoffs':
            since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            policy = 'Current UTC calendar month through reference instant, by publication time'
        elif re.search(r'recent|lately|latest', q) or intent == 'company':
            since = now - timedelta(days=30)
            policy = 'Recent means rolling 30 days by publication time'
        elif intent == 'funding':
            since = now - timedelta(days=7)
            policy = 'Default rolling seven days by publication time; not transaction/event date'
    else:
        policy = 'Explicit publication window'
    return QueryPlan(intent=intent, question=question, as_of=now, since=since, before=before,
                     company=company, location=location, title=title, time_policy=policy,
                     clarification=clarification, count_condition=condition, funding_round=funding_round)
