"""Persistent extraction contracts; validation is separate from factual review."""
from datetime import timezone
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Funding(BaseModel):
    model_config = ConfigDict(extra='forbid')
    company: str | None
    amount: Decimal | None = Field(ge=0)
    currency: Literal['INR', 'USD', 'EUR', 'GBP'] | None
    amount_text: str | None
    round: str | None
    investors: list[str]
    status: Literal['reported', 'closing', 'committed'] = 'reported'
    kind: Literal['venture', 'strategic_investment', 'debt', 'financial_support'] = 'venture'
    evidence: list[str] = Field(min_length=1)

    @model_validator(mode='after')
    def amount_needs_currency(self):
        if self.amount is not None and (self.currency is None or self.amount_text is None):
            raise ValueError('A normalized amount needs currency and original text')
        return self


class ArticleRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-f0-9]{64}$')
    url: str
    title: str = Field(min_length=1)
    author: list[str]
    published_at: AwareDatetime
    body: str = Field(min_length=200)
    summary: str = Field(min_length=20)
    companies: list[str]
    people: list[str]
    locations: list[str]
    category: Literal['funding', 'layoffs', 'AI', 'technology', 'business', 'other']
    funding: Funding | None
    provenance: dict
    warnings: list[str]

    @model_validator(mode='after')
    def evidence_contract(self):
        self.published_at = self.published_at.astimezone(timezone.utc)
        sentences = self.provenance.get('summary_sentences', [])
        if not 2 <= len(sentences) <= 3 or ' '.join(sentences) != self.summary:
            raise ValueError('Summary must contain 2–3 declared source sentences')
        if any(sentence not in self.body for sentence in sentences):
            raise ValueError('Summary sentence is not present in body')
        if self.funding and any(passage not in self.body for passage in self.funding.evidence):
            raise ValueError('Funding evidence is not present in body')
        return self
