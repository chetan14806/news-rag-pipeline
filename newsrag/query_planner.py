"""Explicit query families and reproducible UTC publication windows."""
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


AI_TERMS = re.compile(r'\b(?:ai|artificial intelligence|machine learning)\b', re.I)
LAYOFF_TERMS = re.compile(
    r'\b(?:layoffs?|laid off|lay off|job cuts?|downsizing|redundan\w*|'
    r'(?:workforce|staff|headcount) (?:cuts?|reductions?))\b', re.I)
INVESTOR_TERMS = re.compile(r'\b(?:investors?|backers?|funds?|investment firms?|venture capitalists?|vcs?)\b')
REPEAT_TERMS = re.compile(
    r'more than (?:one|1)|multiple|repeat\w*|recurring|two or more|at least (?:two|2)|'
    r'several|across.*round|common to|shared (?:by|across)|different.*round|'
    r'\b(?:two|three|four|five|six|seven|eight|nine|ten|[2-9]|\d{2,})\s+(?:funding\s+)?rounds\b')


def trim_target(value):
    """Keep a named target separate from supported trailing time/scope phrases."""
    value = re.split(
        r'\s+(?:(?:in|over|during|within|for)\s+(?:the\s+)?)?'
        r'(?:(?:last|past|previous)\s+(?:\d+|seven|thirty)\s+days?|'
        r'(?:last|past|previous)\s+week|(?:this|last|previous)\s+month|recently|lately)\b',
        value, maxsplit=1, flags=re.I)[0]
    value = re.split(r'\s+(?:in|from)\s+(?:this|the)\s+collection\b', value, maxsplit=1, flags=re.I)[0]
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
            if normalize(target) not in {'recent', 'latest', 'the', 'any', 'company', 'companies',
                                         'ai', 'artificial intelligence', 'machine learning'}:
                return target or None
    return None


def location_target(question):
    match = re.search(r'(?:mention(?:s|ing)?|referr?ing to|refer(?:s)? to|references?(?: to)?|\bin)\s+(.+?)[.?]*$',
                      question, re.I)
    return trim_target(match.group(1)) if match else None


def investor_clarification(q):
    if re.search(r'\b(?:not|never)\b', q):
        return ('This aggregation identifies repeated investors, not investors absent from other rounds. '
                'Ask for investors in more than one funding round to use the supported operation.')
    if re.search(r'\b(?:more than one|multiple|at least (?:two|2)|two or more|several)\s+'
                 r'(?:startups?|companies|businesses)\b', q):
        return ('Do you mean distinct companies or distinct funding rounds? This operation counts '
                'investors across more than one conservatively distinct funding round; '
                'company counts are a different calculation.')
    # The supported aggregation is "more than one", not an arbitrary/exact threshold.
    threshold = re.search(r'\b(two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:funding\s+)?rounds\b', q)
    different_comparison = re.search(
        r'\b(?:exactly|only|at most|fewer than|less than|more than)\s+'
        r'(?:two|2)\s+(?:funding\s+)?rounds\b', q)
    if different_comparison or (threshold and threshold.group(1) not in {'two', '2'}):
        return ('This aggregation reports investors in more than one distinct funding round. '
                'Your exact or higher round-count condition needs a different calculation. '
                'Ask for investors in multiple funding rounds to use the supported operation.')
    return None


def normalize(text):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold()))


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


def plan_query(question, *, as_of=None, intent=None, company=None, location=None, title=None, since=None, before=None):
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Reference time must have a timezone')
    now = now.astimezone(timezone.utc)
    if not question.strip():
        raise ValueError('Question cannot be empty')
    q = normalize(question)
    inferred_company = company_target(question) if not company else company
    clarification = None
    funding_question = bool(re.search(r'\b(?:funding|funded|financed)\b|fundrais\w*|\brais(?:e|ed|es|ing)\b|capital rais', q) or
                            re.search(r'\b(?:secur(?:e|ed|es|ing)|obtain(?:ed|s|ing)?|'
                                      r'receiv(?:e|ed|es|ing)|attract(?:ed|s|ing)?|land(?:ed|s|ing)?)\b'
                                      r'(?:\s+\w+){0,4}\s+(?:investment|financing|capital|funding)\b', q))
    startup_subject = bool(re.search(r'\b(?:which|what|list|show)(?: me)?\s+'
                                     r'(?:(?:all|the|those)\s+)*(?:young\s+)?(?:startups?|companies)\b', q))
    investor_subject = bool(INVESTOR_TERMS.search(q) or
                            re.search(r'\bwho\b.*\b(?:backed|funded|financed|invested in)\b', q))
    investor_question = bool(investor_subject and REPEAT_TERMS.search(q) and not startup_subject)
    if intent is None:
        if re.search(r'\b(weather|temperature|rain|raining)\b', q):
            intent = 'unsupported'
        elif re.search(r'\b(revenue|revenues|turnover|sales figures)\b', q):
            intent = 'revenue'
        elif re.search(r'\bearn(?:ed|s|ings)?\b', q):
            intent = 'revenue'
            clarification = ('Do you mean revenue or profit? "Earn" and "earnings" are ambiguous. '
                             'Ask explicitly for revenue/turnover, or use --intent revenue if that is what you mean.')
        elif investor_question:
            intent = 'investors'
        elif LAYOFF_TERMS.search(q):
            intent = 'layoffs'
        elif funding_question:
            intent = 'funding'
        elif inferred_company and not location:
            intent = 'company'
        elif AI_TERMS.search(q) and not company:
            intent = 'ai'
        elif location or re.search(r'\b(?:bengaluru|bangalore)\b', q) or re.search(
                r'\b(?:articles?|stor(?:y|ies)|reports?)\b.*\b(?:mentions?|mentioning|referring to|references?|in)\b', q):
            intent = 'location'
        elif company or re.search(r'announc|company updates|recent updates|product launches|product releases|latest.*\bfrom\b|news (?:on|about)', q):
            intent = 'company'
        else:
            intent = 'unsupported'
    if intent == 'company' and not company:
        company = inferred_company
    if intent == 'investors':
        clarification = investor_clarification(q)
    if not location and re.search(r'\b(?:bengaluru|bangalore)\b', q):
        location = 'Bengaluru'
    if intent == 'location' and not location:
        location = location_target(question)
    if intent == 'revenue' and not title:
        match = re.search(r'["“](.+?)["”]', question)
        title = match.group(1) if match else None
    policy = 'All stored publication dates through the reference instant'
    # Explicit CLI bounds take precedence over natural-language defaults as a pair.
    if since is None and before is None:
        days = re.search(r'(?:last|past|previous)\s+(\d+|seven|thirty)\s+days?', q)
        if days:
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
                     clarification=clarification)
