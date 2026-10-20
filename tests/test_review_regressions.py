"""Constraint regressions under explicit/stubbed operations, not model accuracy tests."""
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

import test_query as fixtures
from newsrag.query_engine import answer_records, revenue_passages, layoff_context
from newsrag.query_planner import plan_query


class ReviewQueryTests(unittest.TestCase):
    def test_recognized_operations_do_not_drop_exclusions(self):
        for question, operation in (
            ('List articles that do not mention Bengaluru.', 'location'),
            ("Which startups didn't raise funding in the last 7 days?", 'funding'),
            ('Show AI stories excluding robotics.', 'ai'),
            ('What has ServiceNow never announced?', 'company'),
            ('Show layoffs without job cuts.', 'layoffs'),
            ('List all articles mentioning Mumbai except reports about finance.', 'location'),
        ):
            with self.subTest(question=question):
                result = answer_records(plan_query(question, as_of=fixtures.NOW,
                                        semantic_route=lambda _: operation), {}, Mock(return_value=[]))
                self.assertEqual(result['status'], 'clarification_required')
                self.assertEqual(result['items'], [])

    def test_explicit_intent_cannot_silently_override_an_exclusion(self):
        plan = plan_query('Show articles without Bengaluru.', intent='location',
                          location='Bengaluru', as_of=fixtures.NOW)
        self.assertIsNotNone(plan.clarification)

    def test_negation_in_article_title_is_not_a_query_filter(self):
        plan = plan_query('What revenue did "No More Losses" report?', as_of=fixtures.NOW, intent='revenue')
        self.assertEqual(plan.title, 'No More Losses')
        self.assertIsNone(plan.clarification)

    def test_locations_constrain_each_operation(self):
        for question, intent, location in (
            ('Which startups raised funding in Mumbai in the last 7 days?', 'funding', 'Mumbai'),
            ('What are the AI stories from Mumbai?', 'ai', 'Mumbai'),
            ('Show job cuts in New Delhi this month.', 'layoffs', 'New Delhi'),
            ('Which startups in Pune raised funding last week?', 'funding', 'Pune'),
            ('What has ServiceNow announced in London recently?', 'company', 'London'),
            ('Which startups raised funding in mumbai?', 'funding', 'mumbai'),
        ):
            with self.subTest(question=question):
                plan = plan_query(question, as_of=fixtures.NOW, semantic_route=lambda _: intent)
                self.assertEqual((plan.intent, plan.location), (intent, location))

    def test_location_words_do_not_misread_time_or_funders(self):
        for question in ('Which startups raised funding in the last 7 days?',
                         'Which startups raised funding from multiple investors?',
                         'What are the AI stories in this collection?',
                         'What has ServiceNow announced recently?'):
            with self.subTest(question=question):
                self.assertIsNone(plan_query(question, as_of=fixtures.NOW).location)

    def test_funding_place_filter_changes_membership(self):
        mumbai = fixtures.funded(1)
        mumbai.body += '\nMumbai is mentioned in the source.'
        other = fixtures.funded(2)
        plan = plan_query('Which startups raised funding in Mumbai in the last 7 days?',
                          as_of=fixtures.NOW, intent='funding')
        result = answer_records(plan, {r.id: r for r in (mumbai, other)}, Mock(return_value=[]))
        self.assertEqual([item['article_id'] for item in result['items']], [mumbai.id])

    def test_calendar_years_and_unsupported_date_expressions(self):
        for question, year in (('What has ServiceNow announced in 2025?', 2025),
                               ('Which startups raised funding last year?', 2025),
                               ('Which startups raised funding this year?', 2026)):
            with self.subTest(question=question):
                plan = plan_query(question, as_of=fixtures.NOW, intent='funding')
                self.assertEqual(plan.since, datetime(year, 1, 1, tzinfo=timezone.utc))
                self.assertEqual(plan.before, datetime(year + 1, 1, 1, tzinfo=timezone.utc))
        for question in ('AI news in September 2025', 'AI news yesterday',
                         'Funding over the last three months', 'What has ServiceNow announced in Q2 2025?'):
            with self.subTest(question=question):
                self.assertIsNotNone(plan_query(question, as_of=fixtures.NOW, intent='ai').clarification)

    def test_explicit_dates_replace_unsupported_natural_language_dates(self):
        plan = plan_query('AI news yesterday', as_of=fixtures.NOW, since=fixtures.NOW, intent='ai')
        self.assertIsNone(plan.clarification)
        self.assertEqual(plan.since, fixtures.NOW)

    def test_explicit_future_year_does_not_return_current_articles(self):
        plan = plan_query('AI news in 2027', as_of=fixtures.NOW, intent='ai')
        self.assertIsNotNone(plan.clarification)

    def test_compound_locations_clarify_instead_of_false_empty_results(self):
        for question, operation in (('List all articles that mention Pune or Mumbai.', 'location'),
                         ('List articles mentioning Bengaluru and Mumbai.', 'location'),
                         ('Which startups raised funding in Mumbai or Pune?', 'funding'),
                         ('AI stories from Mumbai, Pune and Delhi', 'ai')):
            with self.subTest(question=question):
                result = answer_records(plan_query(question, as_of=fixtures.NOW,
                                        semantic_route=lambda _: operation), {}, Mock(return_value=[]))
                self.assertEqual(result['status'], 'clarification_required')
        plan = plan_query('AI stories', location='Trinidad and Tobago', as_of=fixtures.NOW, intent='ai')
        self.assertIsNone(plan.clarification)

    def test_revenue_requires_a_linked_numerical_metric(self):
        for text in ('Revenue is not disclosed. The team has 50 million users.',
                     'Revenue is undisclosed, but the team has 50 million users.',
                     'Revenue is important to a business worth millions.',
                     'The company has 50 million users and does not disclose revenue.'):
            with self.subTest(text=text):
                self.assertEqual(revenue_passages(text), [])
        for text in ('Revenue was Rs 50 crore in FY26.',
                     'Revenue grew 50% in FY26.',
                     'Revenue increased 2X compared with last year.',
                     'Airlines generated $19 billion in revenue in FY26.'):
            with self.subTest(text=text):
                self.assertEqual(revenue_passages(text), [text])

    def test_revenue_does_not_borrow_nearby_funding_or_other_metrics(self):
        for text in ('The revenue team raised $5 million in funding.',
                     'The sales team secured $5 million in funding.',
                     'Revenue improved as net profit reached Rs 50 crore.',
                     'Turnover increased after the company raised $5 million.',
                     'The company reported sales of assets for $5 million.',
                     'Revenue forecasts followed a $5 million valuation.',
                     'Sales grew to 50 million users.'):
            with self.subTest(text=text):
                self.assertEqual(revenue_passages(text), [])
                row = fixtures.make_record(1, title='Financial Review', body=text)
                plan = plan_query('What revenue did "Financial Review" report?',
                                  as_of=fixtures.NOW, intent='revenue')
                answer = answer_records(plan, {row.id: row}, Mock(return_value=[]))
                self.assertEqual(answer['status'], 'insufficient_evidence')
                self.assertEqual(answer['items'], [])

    def test_sales_turnover_and_forecast_evidence_reaches_the_answer(self):
        for text in ('The company reported sales of $5 million in FY26.',
                     'Net sales stood at Rs 50 crore in FY26.',
                     'The company generated $5 million in sales last year.',
                     'Turnover was EUR 2 million last year.',
                     'Sales grew 20% in FY26.',
                     'Revenue is expected to reach $5 million next year.',
                     'The company targets Rs 100 crore revenue next year.',
                     'Revenue (FY26): Rs 50 crore (up 24.8% YoY)'):
            with self.subTest(text=text):
                self.assertEqual(revenue_passages(text), [text])
                row = fixtures.make_record(1, title='Financial Review', body=text)
                plan = plan_query('What revenue did "Financial Review" report?',
                                  as_of=fixtures.NOW, intent='revenue')
                answer = answer_records(plan, {row.id: row}, Mock(return_value=[]))
                self.assertEqual(answer['status'], 'answered')
                quotes = answer['items'][0]['evidence']
                self.assertIn(text, [quote['text'] for quote in quotes])
                for quote in quotes:
                    self.assertEqual(row.body[quote['start']:quote['end']], quote['text'])

    def test_revenue_table_requires_values_in_the_metric_row_or_column(self):
        for text in ('| Team | Funding |\n| Revenue team | $5 million |',
                     '| Revenue | Employees |\n| Undisclosed | 500 |',
                     '| Metric | FY26 |\n| Revenue | Undisclosed |'):
            with self.subTest(text=text):
                self.assertEqual(revenue_passages(text), [])
        for text in ('| Metric | FY26 |\n| Sales | Rs 50 crore |',
                     '| Company | Sales USD (m) |\n| Acme | 50 |'):
            with self.subTest(text=text):
                self.assertEqual(revenue_passages(text), [text])

    def test_layoff_router_and_evidence_share_event_wording(self):
        for text in ('Acme announced today it will cut 200 jobs.',
                     'Acme announced today 200 employees were let go.'):
            with self.subTest(text=text):
                row = fixtures.make_record(1, body=text)
                result = answer_records(plan_query('Summarise layoffs this month', as_of=fixtures.NOW, intent='layoffs'),
                                        {row.id: row}, Mock(return_value=[]))
                self.assertEqual(result['items'][0]['mention_classifications'], ['current_article_event'])

    def test_current_layoffs_ignore_unrelated_years_and_uncertainty(self):
        for text in ('Acme announced layoffs today after revenue grew 20% compared with 2025.',
                     'Acme announced layoffs today, although expansion may continue.',
                     'Although expansion may continue, Acme announced layoffs today.',
                     'Acme cut 500 jobs today.',
                     'Acme laid off 200 workers this month.',
                     'Acme is cutting 500 jobs today.',
                     'Acme announced layoffs today. Expansion may continue in 2027.',
                     'Acme, founded in 2025, announced layoffs today.',
                     'Acme announced layoffs today and its revenue grew in 2025.',
                     'Today, Acme cut 500 jobs.'):
            with self.subTest(text=text):
                self.assertEqual(layoff_context(text, fixtures.NOW), 'current_article_event')

    def test_layoff_clause_keeps_its_conditions_history_and_missing_time(self):
        cases = (
            ('If sales fall, Acme will cut 500 jobs today.', 'negated_conditional_or_speculative'),
            ('Acme may expand and cut 500 jobs today.', 'negated_conditional_or_speculative'),
            ('Acme denied layoffs today, although expansion will continue.', 'negated_conditional_or_speculative'),
            ('Acme announced layoffs will not happen today.', 'negated_conditional_or_speculative'),
            ('Acme is considering cutting 500 jobs today.', 'negated_conditional_or_speculative'),
            ('Acme reported layoffs in 2025, although revenue grew today.', 'historical_context'),
            ('In 2025, Acme cut 500 jobs.', 'historical_context'),
            ('Last year, Acme laid off 200 workers.', 'historical_context'),
            ('Acme cut 500 jobs.', 'timing_or_event_unconfirmed'),
            ('Acme discussed layoffs today.', 'timing_or_event_unconfirmed'),
            ('Acme is discussing layoffs today.', 'timing_or_event_unconfirmed'),
            ('Acme will discuss layoffs today.', 'timing_or_event_unconfirmed'),
        )
        for text, label in cases:
            with self.subTest(text=text):
                self.assertEqual(layoff_context(text, fixtures.NOW), label)

    def test_conflicting_layoff_events_in_one_passage_remain_unconfirmed(self):
        for text in ('Acme cut 500 jobs today. Beta reported layoffs in 2025.',
                     'Acme cut 500 jobs today and denied layoffs last year.'):
            with self.subTest(text=text):
                self.assertEqual(layoff_context(text, fixtures.NOW), 'timing_or_event_unconfirmed')

    def test_layoff_answer_counts_current_articles_and_keeps_exact_evidence(self):
        texts = ('Acme announced layoffs today after revenue grew 20% compared with 2025.',
                 'Acme announced layoffs today, although expansion may continue.',
                 'Acme cut 500 jobs today.',
                 'If sales fall, Acme will cut 500 jobs today.',
                 'In 2025, Acme cut 500 jobs.')
        rows = [fixtures.make_record(i+1, body=text) for i, text in enumerate(texts)]
        plan = plan_query('Summarise layoffs this month', as_of=fixtures.NOW, intent='layoffs')
        answer = answer_records(plan, {row.id: row for row in rows}, Mock(return_value=[]))
        self.assertIn('3 contain an explicit current-article event', answer['answer'])
        self.assertEqual(len(answer['items']), 5)
        by_id = {row.id: row for row in rows}
        for item in answer['items']:
            for quote in item['evidence']:
                self.assertEqual(by_id[item['article_id']].body[quote['start']:quote['end']], quote['text'])

    def test_ai_overview_shows_topic_evidence_when_lead_is_generic(self):
        row = fixtures.make_record(1, title='AI powers a new programme',
                                   body='The programme uses artificial intelligence for research.')
        result = answer_records(plan_query('AI stories', as_of=fixtures.NOW, intent='ai'), {row.id: row},
                                Mock(return_value=[{'metadata': {'article_id': row.id}}]))
        self.assertTrue(any('artificial intelligence' in q['text'] for q in result['items'][0]['evidence']))


if __name__ == '__main__':
    unittest.main()
