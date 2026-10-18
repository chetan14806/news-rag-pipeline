"""Explicit query families and reproducible UTC publication windows."""
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator


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
    if intent is None:
        if re.search(r'\b(weather|temperature|rain|raining)\b', q):
            intent = 'unsupported'
        elif re.search(r'\b(revenue|revenues|turnover|sales figures)\b', q):
            intent = 'revenue'
        elif re.search(r'\b(investors?|backers?|funds?)\b', q) and re.search(r'more than one|multiple|repeat|two or more|several|across.*round|\b(?:two|[2-9]|\d{2,})\s+(?:funding\s+)?rounds\b', q):
            intent = 'investors'
        elif re.search(r'layoffs?|laid off|job cuts?|downsizing|redundan', q):
            intent = 'layoffs'
        elif re.search(r'funding|fundrais|raised|raises|capital rais', q):
            intent = 'funding'
        elif re.search(r'\b(ai|artificial intelligence|machine learning)\b', q) and not company and not re.search(r'what (?:has|did|have) .+? announc|company updates|(?:announcements?|updates?|news) (?:from|by) ', q):
            intent = 'ai'
        elif location or re.search(r'bengaluru|bangalore', q) or re.search(r'\b(all|list|every)\b.*\b(mention|mentions|mentioning|in)\b', q):
            intent = 'location'
        elif company or re.search(r'announc|company updates|recent updates|latest.*\bfrom\b|news (?:on|about)', q):
            intent = 'company'
        elif re.search(r'\b(ai|artificial intelligence|machine learning)\b', q):
            intent = 'ai'
        else:
            intent = 'unsupported'
    if intent == 'company' and not company:
        patterns = [r'what (?:has|did|have) (.+?) announc', r'(.+?) company updates',
                    r'(?:announcements?|updates?|news) (?:from|about|on|by) (.+?)(?: recently| lately| this | in the | over the |\?|$)']
        for pattern in patterns:
            match = re.search(pattern, question, re.I)
            if match:
                company = match.group(1).strip(' ?"')
                if normalize(company) in ('recent', 'latest', 'the', 'any'):
                    company = None
                break
    if not location and re.search('bengaluru|bangalore', q):
        location = 'Bengaluru'
    if intent == 'location' and not location:
        if re.search('bengaluru|bangalore', q):
            location = 'Bengaluru'
        else:
            match = re.search(r'(?:mention(?:s|ing)?|\bin)\s+(.+?)[.?]*$', question, re.I)
            location = match.group(1).strip(' .?') if match else None
            if location:
                location = re.split(r'\s+(?:(?:in|over|during)\s+(?:the\s+)?)?(?:(?:last|past|previous)\s+(?:\d+|seven|thirty)\s+days?|(?:last|past|previous)\s+week|(?:this|last|previous)\s+month|recently)\b', location, maxsplit=1, flags=re.I)[0].strip(' .?')
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
                     company=company, location=location, title=title, time_policy=policy)
