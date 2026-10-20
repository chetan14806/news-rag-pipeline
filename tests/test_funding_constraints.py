"""Funding qualifiers must constrain execution or produce an explicit clarification."""
import unittest
from unittest.mock import Mock

import test_query as fixtures
from newsrag.query_engine import answer_records
from newsrag.query_planner import canonical_funding_round, plan_query


class FundingConstraintTests(unittest.TestCase):
    def ask(self, question, rows, **options):
        plan = plan_query(question, as_of=fixtures.NOW, intent='funding', **options)
        return answer_records(plan, {row.id: row for row in rows}, Mock(side_effect=AssertionError('No vector search needed')))

    def test_seed_does_not_include_preseed_series_a_or_unknown(self):
        rows = [fixtures.funded(1, stage='seed'), fixtures.funded(2, stage='pre-seed'),
                fixtures.funded(3, stage='Series A'), fixtures.funded(4, stage=None)]
        result = self.ask('Which startups raised seed funding in the last 7 days?', rows)
        self.assertEqual([item['article_id'] for item in result['items']], [rows[0].id])
        self.assertEqual(result['plan']['funding_round'], 'seed')
        self.assertEqual(result['funding_filter']['unknown_stage_articles'], 1)

    def test_series_filter_normalizes_case_and_keeps_different_stages_distinct(self):
        rows = [fixtures.funded(1, stage='Series A round'), fixtures.funded(2, stage='pre-Series A'),
                fixtures.funded(3, stage='Series A1'), fixtures.funded(4, stage='series B')]
        result = self.ask('Which startups raised series a funding?', rows)
        self.assertEqual([item['article_id'] for item in result['items']], [rows[0].id])
        self.assertEqual(canonical_funding_round('pre-A'), 'pre series a')
        self.assertEqual(canonical_funding_round('preseed'), 'pre seed')

    def test_round_phrases_are_not_misread_as_locations(self):
        for phrase, stage in [('in a seed round', 'seed'), ('in pre-seed funding', 'pre seed'),
                              ('in a Series A round', 'series a'), ('in bridge funding', 'bridge')]:
            with self.subTest(phrase=phrase):
                plan = plan_query(f'Which startups raised funding {phrase}?', as_of=fixtures.NOW, intent='funding')
                self.assertEqual(plan.funding_round, stage)
                self.assertIsNone(plan.location)

    def test_round_filter_also_applies_to_pending_financing(self):
        rows = [fixtures.funded(1, stage='seed', status='closing'),
                fixtures.funded(2, stage='Series A', status='closing')]
        result = self.ask('Which startups raised seed funding?', rows)
        self.assertEqual(result['items'], [])
        self.assertEqual([item['article_id'] for item in result['pending_financing']], [rows[0].id])

    def test_unknown_stages_do_not_become_false_negative_claims(self):
        rows = [fixtures.funded(1, stage=None), fixtures.funded(2, stage='seed')]
        result = self.ask('Which startups raised Series A funding?', rows)
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertEqual(result['items'], [])
        self.assertIn('unknown stage', result['answer'])

    def test_known_nonmatching_stages_can_return_no_matches(self):
        result = self.ask('Which startups raised Series A funding?', [fixtures.funded(1, stage='seed')])
        self.assertEqual(result['status'], 'no_matches')
        self.assertEqual(result['funding_filter']['unknown_stage_articles'], 0)

    def test_round_filter_keeps_date_company_location_and_venture_restrictions(self):
        from datetime import timedelta
        good = fixtures.funded(1, company='Alpha', stage='seed')
        bad_stage = fixtures.funded(2, company='Alpha', stage='Series A')
        old = fixtures.funded(3, company='Alpha', stage='seed', date=fixtures.NOW-timedelta(days=8))
        other = fixtures.funded(4, company='Beta', stage='seed')
        debt = fixtures.funded(5, company='Alpha', stage='seed')
        debt.funding.kind = 'debt'
        rows = [good, bad_stage, old, other, debt]
        for row in rows:
            row.body += '\nThe company has an office in Bengaluru.'
        rows.append(fixtures.funded(6, company='Alpha', stage='seed'))
        result = self.ask('Which startups raised seed funding in the last 7 days?', rows,
                          company='Alpha', location='Bengaluru')
        self.assertEqual([item['article_id'] for item in result['items']], [good.id])

    def test_money_filters_clarify_instead_of_returning_unrestricted_results(self):
        rows = [fixtures.funded(1)]
        for qualifier in ('more than $10 million', 'at least INR 5 crore', 'over 10m',
                          'under €2 million', 'above 10', 'between five and ten million',
                          '10 million dollars', 'less than 10 lakh rupees'):
            with self.subTest(qualifier=qualifier):
                answer = self.ask(f'Which startups raised {qualifier} in funding in the last 7 days?', rows)
                self.assertEqual(answer['status'], 'clarification_required')
                self.assertEqual(answer['items'], [])
                self.assertIn('amount/currency', answer['answer'])

    def test_investor_conditions_do_not_become_company_mentions_or_ignore_lead_role(self):
        rows = [fixtures.funded(1, investor='Accel')]
        for question in ('Show funding rounds led by Accel in the last 7 days.',
                         'Show seed funding backed by Accel.',
                         'Which startups received funding from Example Ventures?',
                         'Which startups raised funding from multiple investors?',
                         'Which startups did Accel fund?',
                         'Show funding involving Accel.',
                         'Which startups has Accel invested in?',
                         'Show Accel-backed funding rounds.'):
            with self.subTest(question=question):
                answer = self.ask(question, rows,
                                  entity_catalog={'companies': ['Accel', 'Example Ventures']})
                self.assertEqual(answer['status'], 'clarification_required')
                self.assertEqual(answer['items'], [])
                self.assertIn('lead-investor', answer['answer'])

    def test_multi_stage_and_unsupported_stage_filters_clarify(self):
        for stage in ('seed or Series A', 'Series A and B', 'Series A/B', 'Series',
                      'early-stage', 'growth', 'angel'):
            with self.subTest(stage=stage):
                answer = self.ask(f'Which startups raised {stage} funding?', [fixtures.funded(1)])
                self.assertEqual(answer['status'], 'clarification_required')
                self.assertEqual(answer['items'], [])

    def test_plain_funding_questions_still_show_amounts_and_investors(self):
        for question in ('Which startups raised funding in the last 7 days, and how much?',
                         'Which startups raised funding, and who are their investors?'):
            result = self.ask(question, [fixtures.funded(1)])
            self.assertEqual(result['status'], 'answered')
            self.assertEqual(len(result['items']), 1)
            self.assertNotIn('funding_round', result['plan'])

    def test_guard_runs_after_semantic_selection_and_preserves_operation(self):
        for operation in ('funding', 'investors'):
            route = Mock(return_value=operation)
            plan = plan_query('Show funding led by Accel.', as_of=fixtures.NOW, semantic_route=route)
            route.assert_called_once()
            self.assertEqual(plan.intent, operation)
            self.assertEqual(answer_records(plan, {r.id:r for r in [fixtures.funded(1)]}, None)['status'],
                             'clarification_required')

    def test_stage_filtered_aggregation_clarifies_without_changing_operation(self):
        plan = plan_query('Which investors repeated across seed rounds?', as_of=fixtures.NOW, intent='investors')
        self.assertEqual(plan.intent, 'investors')
        self.assertIsNotNone(plan.clarification)

    def test_numeric_round_count_is_not_mistaken_for_a_monetary_filter(self):
        plan = plan_query('Which investors participated in more than 1 funding round?',
                          as_of=fixtures.NOW, intent='investors')
        self.assertIsNone(plan.clarification)


if __name__ == '__main__':
    unittest.main()
