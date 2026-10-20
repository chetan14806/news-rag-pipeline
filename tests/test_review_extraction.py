"""Financial-event regressions from controlled source text."""
import unittest
import spacy
from newsrag.extraction import funding_details


class ReviewFinancialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.blank('en')
        cls.nlp.add_pipe('sentencizer')

    def test_body_debt_is_not_venture_funding(self):
        fund, _ = funding_details('Acme raises $5 million', self.nlp(
            'Acme raised $5 million in debt funding led by Example Bank. The loan will fund expansion.'))
        self.assertEqual(fund.kind, 'debt')

    def test_ongoing_and_explicitly_unclosed_rounds_are_pending(self):
        for body in (
            'Acme is raising $5 million in a funding round led by Example Ventures. The round has not closed.',
            'Acme plans to raise $5 million in a funding round led by Example Ventures.',
            'Acme raised $5 million in a funding round led by Example Ventures. The round is not yet closed.',
        ):
            with self.subTest(body=body):
                fund, _ = funding_details('Acme raises $5 million', self.nlp(body))
                self.assertEqual(fund.status, 'closing')

    def test_completed_equity_is_not_changed_by_unrelated_historical_debt(self):
        fund, _ = funding_details('Acme raises $5 million', self.nlp(
            'Acme raised $5 million in seed funding led by Example Ventures. '
            'Its older investment portfolio included a debt fund.'))
        self.assertEqual((fund.kind, fund.status), ('venture', 'reported'))

    def test_completed_round_headlines_are_not_missed(self):
        for verb in ('closes', 'closed', 'bags', 'lands'):
            with self.subTest(verb=verb):
                fund, _ = funding_details(f'Acme {verb} $5 million funding round', self.nlp(
                    'Acme closed a $5 million seed funding round led by Example Ventures.'))
                self.assertIsNotNone(fund)
                self.assertEqual((fund.amount, fund.currency, fund.company), (5000000, 'USD', 'Acme'))

    def test_completed_contract_is_not_funding(self):
        fund, _ = funding_details('Acme lands $5 million contract', self.nlp(
            'Acme secured a $5 million contract. It will support its investment programme.'))
        self.assertIsNone(fund)

    def test_funding_deal_wording_preserves_financial_fields(self):
        body = ('Acme has raised $5 million in a seed funding round led by Example Ventures. '
                'The company will expand its engineering team.')
        reference, _ = funding_details('Acme raises $5 million in funding', self.nlp(body))
        for headline in ('Acme raises $5 million in funding deal',
                         'Acme secures $5 million financing deal',
                         'Acme closes $5 million seed funding deal',
                         'Acme secures $5 million deal'):
            with self.subTest(headline=headline):
                funding, _ = funding_details(headline, self.nlp(body))
                self.assertEqual(funding.model_dump(), reference.model_dump())

    def test_closed_financing_deal_requires_an_explicit_body_event(self):
        funding, _ = funding_details('Acme closes $5 million financing deal', self.nlp(
            'Acme closed a $5 million seed funding round led by Example Ventures. '
            'The new funding will support its expansion.'))
        self.assertEqual((funding.amount, funding.currency, funding.status), (5000000, 'USD', 'reported'))

    def test_services_deal_cannot_inherit_a_previous_funding_round(self):
        body = ('Acme secured a $5 million managed services transformation deal. '
                'Acme raised $2 million in seed funding last year led by Example Ventures.')
        funding, warnings = funding_details('Acme secures $5 million managed services transformation deal', self.nlp(body))
        self.assertIsNone(funding)
        self.assertIn('deal_without_confirmed_financing_evidence', warnings)

    def test_funding_headline_cannot_override_commercial_lead_and_old_raise(self):
        funding, warnings = funding_details('Acme secures $5 million funding deal', self.nlp(
            'Acme secured a $5 million managed services transformation deal. '
            'Acme raised $2 million in seed funding last year led by Example Ventures.'))
        self.assertIsNone(funding)
        self.assertIn('deal_without_confirmed_financing_evidence', warnings)

    def test_generic_investment_programme_is_not_a_financing_deal(self):
        funding, warnings = funding_details('Acme secures $5 million deal', self.nlp(
            'Acme secured a $5 million managed services deal. '
            'The deal will support the customers investment programme.'))
        self.assertIsNone(funding)
        self.assertIn('deal_without_confirmed_financing_evidence', warnings)

    def test_contract_and_order_deals_remain_excluded(self):
        body = self.nlp('Acme has raised $5 million in seed funding led by Example Ventures.')
        for title in ('Acme lands $5 million contract deal', 'Acme secures $5 million order deal'):
            with self.subTest(title=title):
                self.assertIsNone(funding_details(title, body)[0])

    def test_deal_headline_without_financing_evidence_does_not_create_funding(self):
        for body in ('Acme announced a new technology partnership today. The partnership supports its customers.',
                     'Acme denied it raised $5 million in a funding round led by Example Ventures.'):
            with self.subTest(body=body):
                self.assertIsNone(funding_details('Acme secures $5 million funding deal', self.nlp(body))[0])

    def test_body_amount_is_used_when_headline_only_states_valuation(self):
        funding, warnings = funding_details('Acme raises funding at $50 million valuation', self.nlp(
            'Acme raised $5 million in a seed funding round led by Example Ventures. '
            'The investment values the business at $50 million.'))
        self.assertEqual((funding.amount, funding.currency, funding.amount_text), (5000000, 'USD', '$5 million'))
        self.assertNotIn('funding_amount_unknown_or_ambiguous', warnings)

    def test_body_amount_keeps_decimal_units_and_financial_evidence(self):
        for money, value, code in [('$2.75 million', '2750000', 'USD'),
                                   ('INR 45 lakh', '4500000', 'INR'),
                                   ('€500,000', '500000', 'EUR')]:
            with self.subTest(money=money):
                body = f'Acme, a technology startup, has raised {money} in seed funding led by Example Ventures.'
                funding, _ = funding_details('Acme raises seed funding', self.nlp(body))
                self.assertEqual((funding.amount, funding.currency), (__import__('decimal').Decimal(value), code))
                self.assertEqual(funding.amount_text, money)
                self.assertIn(body, funding.evidence)

    def test_secured_or_closed_body_amount_requires_financing_not_a_contract(self):
        for verb in ('secured', 'closed'):
            funding, _ = funding_details('Acme raises seed funding', self.nlp(
                f'Acme {verb} a $5 million seed funding round led by Example Ventures.'))
            self.assertEqual(funding.amount, 5000000)
        funding, _ = funding_details('Acme raises funding', self.nlp(
            'Acme raised undisclosed seed funding. Acme secured a $5 million contract for its investment programme.'))
        self.assertIsNone(funding.amount)

    def test_historical_and_planned_amounts_do_not_fill_an_undisclosed_current_raise(self):
        for context in ('Acme previously raised $5 million in seed funding.',
                        'Acme raised $5 million in funding last year.',
                        'Acme raised $5 million in funding in 2024.',
                        'Acme plans to raise $5 million in a future funding round.',
                        'Acme has raised $5 million in total funding to date.'):
            with self.subTest(context=context):
                funding, _ = funding_details('Acme raises seed funding', self.nlp(
                    'Acme has raised undisclosed seed funding led by Example Ventures. '+context))
                self.assertIsNone(funding.amount)

    def test_other_company_investor_fund_and_revenue_are_not_the_raise(self):
        for context in ('OtherCo raised $5 million in seed funding.',
                        'Example Ventures manages a $100 million investment fund.',
                        'Acme raised its revenue to $5 million after the funding.',
                        'Acme raised $5 million in revenue after the funding.'):
            with self.subTest(context=context):
                funding, _ = funding_details('Acme raises funding', self.nlp(
                    'Acme raised undisclosed seed funding led by Example Ventures. '+context))
                self.assertIsNone(funding.amount)

    def test_valuation_in_same_sentence_is_not_confused_with_the_raise(self):
        funding, _ = funding_details('Acme raises seed funding', self.nlp(
            'Acme raised $5 million in seed funding at a valuation of $50 million.'))
        self.assertEqual(funding.amount, 5000000)
        unknown, _ = funding_details('Acme raises funding', self.nlp(
            'Acme raised undisclosed seed funding at a valuation of $50 million.'))
        self.assertIsNone(unknown.amount)

    def test_conflicting_raises_components_and_currency_equivalents_stay_unknown(self):
        for body in ('Acme raised $5 million in seed funding. Acme raised $7 million in funding.',
                     'Acme raised $5 million and $2 million in seed funding.',
                     'Acme raised $5 million (INR 40 crore) in seed funding.'):
            with self.subTest(body=body):
                funding, _ = funding_details('Acme raises funding', self.nlp(body))
                self.assertIsNone(funding.amount)

    def test_headline_disagreement_is_not_silently_overwritten_by_body_amount(self):
        funding, warnings = funding_details('Acme raises $10 million in funding', self.nlp(
            'Acme raised $5 million in a seed funding round led by Example Ventures.'))
        self.assertIsNone(funding.amount)
        self.assertIn('funding_amount_unknown_or_ambiguous', warnings)

    def test_approximate_and_bounded_body_amounts_are_not_labeled_exact(self):
        for qualifier in ('over', 'up to', 'about', 'approximately', 'nearly', 'between'):
            with self.subTest(qualifier=qualifier):
                funding, _ = funding_details('Acme raises funding', self.nlp(
                    f'Acme raised {qualifier} $5 million in seed funding led by Example Ventures.'))
                self.assertIsNone(funding.amount)

    def test_repeated_same_amount_is_not_a_conflict_and_pending_stays_pending(self):
        funding, _ = funding_details('Acme raises funding', self.nlp(
            'Acme raised $5 million in seed funding. Acme raised $5 million in the funding round.'))
        self.assertEqual(funding.amount, 5000000)
        pending, _ = funding_details('Acme raises funding', self.nlp(
            'Acme is raising $5 million in seed funding led by Example Ventures.'))
        self.assertEqual((pending.amount, pending.status), (5000000, 'closing'))


if __name__ == '__main__':
    unittest.main()
