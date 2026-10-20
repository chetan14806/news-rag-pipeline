"""Slot/executor behavior under an injected semantic operation.

These fixtures do not measure model wording accuracy; the real-encoder benchmark does.
"""
import unittest
from datetime import datetime, timedelta

import test_query as fixtures
from newsrag.query_engine import answer_records
from newsrag.query_planner import plan_query


class QueryWordingTests(unittest.TestCase):
    def ask(self, question, rows, **options):
        records = {r.id: r for r in rows}

        def retrieve(text, ids, count):
            return [{'metadata': {'article_id': ident}, 'text': records[ident].body}
                    for ident in ids[:count]]

        return answer_records(plan_query(question, as_of=fixtures.NOW,
                              semantic_route=lambda _: self.operation, **options), records, retrieve)

    def test_injected_operations_preserve_family_contracts(self):
        cases = {
            'ai': ['Give me a roundup of artificial intelligence developments.',
                   'What is new in machine learning?', 'Catch me up on AI news.'],
            'funding': ['Which young companies secured investment during the past week?',
                        'List startups that obtained financing in the past seven days.',
                        'Which startups got funded last week?',
                        'Which companies attracted capital in the last 14 days?'],
            'company': ["Tell me about Orion Systems' latest product launches.",
                        "Tell me about Orion Systems's latest product launches.",
                        'What did Orion Systems unveil recently?',
                        'What are Orion Systems\'s recent announcements?',
                        "What's new at Orion Systems?",
                        'Show recent product releases from Orion Systems.'],
            'location': ['Find reports referring to Pune.',
                         'Show stories that reference New Delhi.',
                         'Find all articles mentioning Mumbai in the past week.'],
            'layoffs': ['Give me a roundup of workforce reductions this month.',
                        'Summarise staff cuts this month.', 'Show headcount reductions last month.'],
            'investors': ['Which investment firms took part in multiple funding rounds?',
                          'List recurring backers across funding rounds.',
                          'Name investors common to different funding rounds.',
                          'Who backed more than one funding round?',
                          'Which investors participated in at least two funding rounds?'],
            'revenue': ['What turnover did the article "Quarterly Results" report?',
                        'What sales figures were reported in "Quarterly Results"?'],
            'unsupported': ['Is it sunny in Mumbai today?',
                            'Tell me the current temperature in Pune.', 'Write a poem about the sea.'],
        }
        for expected, questions in cases.items():
            for question in questions:
                with self.subTest(question=question):
                    self.assertEqual(plan_query(question, as_of=fixtures.NOW,
                                     semantic_route=lambda _: expected).intent, expected)

    def test_company_target_is_clean_and_preserves_legal_name_and_punctuation(self):
        for question, target in [
            ("Tell me about ServiceNow's latest product launches.", 'ServiceNow'),
            ("Tell me about Orion Systems’ latest releases.", 'Orion Systems'),
            ('What did L&T Technology Services unveil recently?', 'L&T Technology Services'),
            ("What are Orion Systems's recent announcements?", 'Orion Systems'),
            ("What's new at Orion Systems?", 'Orion Systems'),
            ('Show recent product releases from Northstar Labs in the past week.', 'Northstar Labs'),
            ('What has Novus AI announced recently?', 'Novus AI'),
            ('ServiceNow company updates on AI', 'ServiceNow'),
        ]:
            with self.subTest(question=question):
                plan = plan_query(question, as_of=fixtures.NOW, intent='company')
                self.assertEqual((plan.intent, plan.company), ('company', target))

    def test_company_paraphrase_returns_same_sources_and_does_not_broaden(self):
        self.operation = 'company'
        first = fixtures.make_record(1, title='Orion Systems launches a new platform',
                                    body='Orion Systems introduced a platform for its customers.')
        other = fixtures.make_record(2, title='Different Company launches a product')
        reference = self.ask('What has Orion Systems announced recently?', [first, other])
        variant = self.ask("Tell me about Orion Systems's latest product launches.", [first, other])
        self.assertEqual([i['article_id'] for i in variant['items']],
                         [i['article_id'] for i in reference['items']])
        self.assertEqual(len(variant['items']), 1)
        unknown = self.ask("Tell me about MissingCorp's latest product launches.", [first, other])
        self.assertEqual((unknown['status'], unknown['items']), ('no_matches', []))

    def test_location_target_strips_time_but_keeps_multiword_place(self):
        for question, target in [
            ('Find reports referring to Pune in the past week.', 'Pune'),
            ('Show stories that reference New Delhi during the last 7 days.', 'New Delhi'),
            ('List all articles mentioning Mumbai last month.', 'Mumbai'),
        ]:
            with self.subTest(question=question):
                plan = plan_query(question, as_of=fixtures.NOW, intent='location')
                self.assertEqual((plan.intent, plan.location), ('location', target))
                self.assertIsNotNone(plan.since)

    def test_location_paraphrase_is_exhaustive_and_respects_dates(self):
        self.operation = 'location'
        rows = [fixtures.make_record(i, body='Pune hosts the new research office.') for i in range(1, 36)]
        rows.extend([fixtures.make_record(36, body='Puneri is not the exact requested name.'),
                     fixtures.make_record(37, body='Pune is mentioned in older reporting.',
                                          date=fixtures.NOW - timedelta(days=20))])
        result = self.ask('Find reports referring to Pune in the past week.', rows)
        self.assertEqual(result['plan']['location'], 'Pune')
        self.assertEqual({i['article_id'] for i in result['items']}, {r.id for r in rows[:35]})

    def test_funding_paraphrase_preserves_eligibility_and_window(self):
        self.operation = 'funding'
        current = fixtures.funded(1)
        old = fixtures.funded(2, date=fixtures.NOW - timedelta(days=10))
        debt = fixtures.funded(3)
        debt.funding.kind = 'debt'
        pending = fixtures.funded(4, status='closing')
        rows = [current, old, debt, pending]
        answer = self.ask('Which young companies secured investment during the past week?', rows)
        self.assertEqual([i['article_id'] for i in answer['items']], [current.id])
        self.assertEqual([i['article_id'] for i in answer['pending_financing']], [pending.id])
        self.assertEqual(datetime.fromisoformat(answer['plan']['since']), fixtures.NOW - timedelta(days=7))

    def test_workforce_paraphrases_find_evidence_without_claiming_event_dates(self):
        self.operation = 'layoffs'
        first = fixtures.make_record(1, body='Acme announced today it will make staff cuts affecting 200 workers.')
        second = fixtures.make_record(2, body='Acme discussed workforce reductions in 2025.')
        answer = self.ask('Give me a roundup of workforce reductions this month.', [first, second])
        self.assertEqual({i['article_id'] for i in answer['items']}, {first.id, second.id})
        labels = [label for item in answer['items'] for label in item['mention_classifications']]
        self.assertIn('historical_context', labels)

    def test_recurring_investor_wording_preserves_distinct_round_count(self):
        self.operation = 'investors'
        rows = [fixtures.funded(1), fixtures.funded(2), fixtures.funded(3, company='Beta')]
        answer = self.ask('Which investment firms took part in multiple funding rounds?', rows)
        self.assertEqual(answer['investors'][0]['conservative_distinct_round_count'], 2)
        self.assertEqual(len(answer['investors']), 1)

    def test_negated_new_workforce_terms_are_not_counted_as_layoff_events(self):
        self.operation = 'layoffs'
        for phrase in ('staff cuts', 'workforce reductions', 'headcount reductions'):
            with self.subTest(phrase=phrase):
                row = fixtures.make_record(1, body=f'Acme announced today there will be no {phrase}.')
                answer = self.ask('Summarise workforce reductions this month.', [row])
                self.assertEqual(answer['items'][0]['mention_classifications'],
                                 ['negated_conditional_or_speculative'])
                self.assertIn('0 contain an explicit current-article event', answer['answer'])

    def test_ambiguous_earnings_do_not_silently_mean_revenue(self):
        self.operation = 'revenue'
        row = fixtures.make_record(1, title='Quarterly Results',
                                   body='Revenue was Rs 50 crore. Net profit was Rs 5 crore.')
        answer = self.ask('How much did the company in "Quarterly Results" earn?', [row])
        self.assertEqual(answer['status'], 'clarification_required')
        self.assertEqual(answer['items'], [])
        self.assertIn('revenue', answer['answer'].lower())
        self.assertIn('profit', answer['answer'].lower())
        explicit = self.ask('How much did the company in "Quarterly Results" earn?', [row], intent='revenue')
        self.assertEqual(explicit['status'], 'answered')

    def test_company_counts_and_higher_round_thresholds_are_not_reinterpreted(self):
        self.operation = 'investors'
        rows = [fixtures.funded(1), fixtures.funded(2, company='Beta')]
        for question in ('Which investment firms backed at least two startups?',
                         'Which investors backed multiple companies?',
                         'Which investors participated in at least three funding rounds?',
                         'Which investors participated in more than two funding rounds?',
                         'Which investors did not appear in multiple funding rounds?',
                         'Which investors appeared in exactly two funding rounds?'):
            with self.subTest(question=question):
                answer = self.ask(question, rows)
                self.assertEqual(answer['status'], 'clarification_required')
                self.assertEqual(answer['items'], [])

    def test_semantic_operation_is_not_changed_by_topic_words(self):
        for question, expected in [
            ('Which startups raised funding from multiple investors?', 'funding'),
            ('List all startups that raised funding from multiple investors.', 'funding'),
            ('Show me the companies that raised funding from multiple investors.', 'funding'),
            ('Which startups secured investment in Bengaluru last week?', 'funding'),
            ('What are the latest AI announcements?', 'ai'),
            ('Show news about artificial intelligence', 'ai'),
            ('Show job cuts mentioned in Bengaluru this month.', 'layoffs'),
        ]:
            with self.subTest(question=question):
                self.assertEqual(plan_query(question, as_of=fixtures.NOW,
                                 semantic_route=lambda _: expected).intent, expected)

    def test_explicit_targets_and_date_bounds_still_take_precedence(self):
        before = fixtures.NOW - timedelta(days=60)
        plan = plan_query("Tell me about Orion's latest product launches.", as_of=fixtures.NOW,
                          intent='company', company='Different Company', before=before)
        self.assertEqual(plan.company, 'Different Company')
        self.assertEqual(plan.before, before)
        self.assertIsNone(plan.since)
        plan = plan_query('Find reports referring to Pune.', as_of=fixtures.NOW,
                          intent='location', location='New Delhi')
        self.assertEqual(plan.location, 'New Delhi')


if __name__ == '__main__':
    unittest.main()
