"""Query semantics with synthetic source records; real-model evaluation is separate."""
import unittest
from datetime import datetime, timezone, timedelta

from newsrag.models import ArticleRecord
from newsrag.query_planner import plan_query
from newsrag.query_engine import answer_records, mentions, revenue_passages

NOW = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)


def make_record(n, **kwargs):
    # Explicit source sentence evidence includes terminal punctuation.
    lead = 'Example Company announced a new research programme today. The programme supports engineering development and practical education.'
    body = lead + '\n' + kwargs.pop('body', 'The Bengaluru office is supporting the initiative with local engineers and academic partners.')
    body += '\nAdditional reporting provides context for this development and its intended practical applications.'
    return ArticleRecord(id=f'{n:064x}', url=f'https://example.test/{n}', title=kwargs.pop('title', f'Article {n}'),
                         author=[], published_at=kwargs.pop('date', NOW), body=body, summary=lead,
                         companies=[], people=[], locations=[], category=kwargs.pop('category', 'business'),
                         funding=kwargs.pop('funding', None), provenance={'summary_sentences': [
                         'Example Company announced a new research programme today.',
                         'The programme supports engineering development and practical education.']}, warnings=[], **kwargs)


def funded(n, company='Alpha', stage='seed', status='reported', investor='Example Ventures', **kwargs):
    quote = f'{company} raised $5 million in {stage or "unspecified"} funding from {investor}.'
    fund = {'company': company, 'amount': '5000000', 'currency': 'USD', 'amount_text': '$5 million',
            'round': stage, 'investors': [investor], 'status': status, 'kind': 'venture', 'evidence': [quote]}
    return make_record(n, body=quote, funding=fund, **kwargs)


class QueryTests(unittest.TestCase):
    def ask(self, question, rows, **kwargs):
        records = {r.id:r for r in rows}
        def retrieve(text, ids, count):
            return [{'metadata': {'article_id': ident}, 'text': records[ident].body} for ident in ids[:count]]
        return answer_records(plan_query(question, as_of=NOW, **kwargs), records, retrieve)

    def test_paraphrase_intents(self):
        for question, expected in [
            ('Give an overview of artificial intelligence stories', 'ai'),
            ('Startups that raised capital in the past seven days', 'funding'),
            ('Recent announcements from ServiceNow?', 'company'),
            ('Show every story mentioning Bangalore', 'location'),
            ('News on job cuts this month', 'layoffs'),
            ('Which backers participated in multiple rounds?', 'investors'),
            ('Revenue figures in the article "Example"?', 'revenue'),
            ('Will it rain in Mumbai today?', 'unsupported')]:
            self.assertEqual(plan_query(question, as_of=NOW).intent, expected)

    def test_timezone_and_rolling_boundary_future_exclusion(self):
        cutoff = NOW - timedelta(days=7)
        rows = [funded(1,date=cutoff), funded(2,date=cutoff-timedelta(seconds=1)),
                funded(3,date=NOW+timedelta(seconds=1)), funded(4,date=NOW)]
        result = self.ask('Which startups raised funding in the last 7 days?', rows)
        self.assertEqual({i['article_id'] for i in result['items']}, {rows[0].id, rows[3].id})
        self.assertEqual(plan_query('layoffs this month', as_of=NOW).since.day, 1)
        with self.assertRaises(ValueError):
            plan_query('AI stories', as_of=NOW, since=NOW+timedelta(days=1))

    def test_additional_query_wording_does_not_change_operation(self):
        for question, expected in [
            ('What are the latest AI announcements?', 'ai'),
            ('Show news about artificial intelligence', 'ai'),
            ('Which investors participated in two funding rounds?', 'investors'),
            ('Which backers appear in 3 rounds?', 'investors'),
            ('What revenue forecast did "Company Results" report?', 'revenue'),
            ('What is the weather forecast in Mumbai?', 'unsupported'),
            ('Recent announcements from OpenAI?', 'company')]:
            with self.subTest(question=question):
                self.assertEqual(plan_query(question, as_of=NOW).intent, expected)
        company_plan = plan_query('ServiceNow company updates on AI', as_of=NOW)
        self.assertEqual((company_plan.intent, company_plan.company), ('company', 'ServiceNow'))

    def test_explicit_upper_bound_does_not_get_overwritten_or_gain_default_lower_bound(self):
        upper = datetime(2026, 9, 15, tzinfo=timezone.utc)
        for question in ('funding last month', 'recent funding'):
            plan = plan_query(question, as_of=NOW, before=upper)
            self.assertEqual(plan.before, upper)
            self.assertIsNone(plan.since)
            self.assertEqual(plan.time_policy, 'Explicit publication window')
        lower = datetime(2026, 9, 1, tzinfo=timezone.utc)
        plan = plan_query('funding last month', as_of=NOW, since=lower, before=upper)
        self.assertEqual((plan.since, plan.before), (lower, upper))

    def test_location_time_phrase_is_not_part_of_the_city(self):
        for question in ('List all articles that mention Mumbai in the last 7 days.',
                         'List every story mentioning Mumbai last month.'):
            plan = plan_query(question, as_of=NOW)
            self.assertEqual(plan.location, 'Mumbai')
            self.assertIsNotNone(plan.since)

    def test_calendar_month_and_non_utc_reference(self):
        plan=plan_query('funding last month',as_of=NOW)
        self.assertEqual(plan.since.isoformat(),'2026-09-01T00:00:00+00:00')
        self.assertEqual(plan.before.isoformat(),'2026-10-01T00:00:00+00:00')
        india=datetime.fromisoformat('2026-10-01T01:00:00+05:30')
        self.assertEqual(plan_query('layoffs this month',as_of=india).since.month,9)
        rows=[funded(1,date=datetime(2026,9,30,tzinfo=timezone.utc)),funded(2,date=datetime(2026,10,1,tzinfo=timezone.utc))]
        self.assertEqual(len(self.ask('funding last month',rows)['items']),1)

    def test_exhaustive_location_alias_and_word_boundary(self):
        rows = [make_record(i,body='Bangalore is mentioned as a location.') for i in range(1,36)]
        rows.append(make_record(36,body='Bengalurux is not the requested city.'))
        result = self.ask('List all articles that mention Bengaluru.',rows)
        self.assertEqual(len(result['items']),35)
        self.assertFalse(mentions('Armstrong','Arm'))

    def test_funding_pending_and_debt_excluded(self):
        rows = [funded(1), funded(2,status='closing'), funded(3)]
        rows[2].funding.kind = 'debt'
        result = self.ask('funding last 7 days',rows)
        self.assertEqual(len(result['items']),1)
        self.assertEqual(len(result['pending_financing']),1)

    def test_combined_financial_location_and_company_filters(self):
        one=funded(1,company='Bengaluru Labs')
        two=funded(2,company='Mumbai Labs')
        answer=self.ask('Which startups raised funding in Bengaluru in the last 7 days?',[one,two])
        self.assertEqual(answer['plan']['intent'],'funding')
        self.assertEqual([i['article_id'] for i in answer['items']],[one.id])
        answer=self.ask('funding last 7 days',[one,two],company='MissingCorp')
        self.assertEqual(answer['items'],[])

    def test_repeat_investors_duplicate_unknown_and_distinct_rounds(self):
        rows = [funded(1),funded(2),funded(3,company='Beta')]
        result = self.ask('Investors in more than one funding round?',rows)
        self.assertEqual(result['investors'][0]['conservative_distinct_round_count'],2)
        self.assertTrue(result['ambiguous_round_groups'])
        self.assertEqual(self.ask('repeat investors',rows[:2])['investors'],[])
        unknown = [funded(1,stage=None),funded(2,stage='series a')]
        self.assertEqual(self.ask('repeat investors',unknown)['investors'],[])
        distinct = [funded(1,stage='seed'),funded(2,stage='series a')]
        self.assertEqual(self.ask('repeat investors',distinct)['investors'][0]['conservative_distinct_round_count'],2)

    def test_distinct_funds_are_not_parent_merged(self):
        rows=[funded(1,investor='IAN Alpha Fund'),funded(2,company='Beta',investor='IAN Angel Fund')]
        self.assertEqual(self.ask('repeat investors',rows)['investors'],[])

    def test_company_legal_suffix_and_stage_aliases_do_not_inflate_rounds(self):
        rows=[funded(1,company='Alpha Pvt. Ltd.',stage='SeriesA'),
              funded(2,company='Alpha',stage='Series A round')]
        self.assertEqual(self.ask('repeat investors',rows)['investors'],[])

    def test_revenue_profit_forecast_subject_and_ambiguity(self):
        rows=[make_record(1,title='Company Results',body='Net profit was Rs 100 crore. Valuation reached $5 billion.'),
              make_record(2,title='Other Results',body='Airlines generated $19 billion in revenue in FY26. The company targets Rs 100 crore revenue next year.')]
        missing=self.ask('What revenue did "Company Results" report?',rows)
        self.assertEqual(missing['status'],'insufficient_evidence')
        supported=self.ask('What revenue did "Other Results" report?',rows)
        self.assertIn('Airlines generated',supported['answer'])
        self.assertIn('targets',supported['answer'])
        ambiguous=self.ask('Revenue in "Results"?',rows)
        self.assertEqual(ambiguous['status'],'clarification_required')
        self.assertEqual(len(ambiguous['candidates']),2)
        self.assertEqual(revenue_passages('Revenue-stage startups created 100 jobs.'),[])

    def test_revenue_table_keeps_headers_rows_and_units(self):
        text='| Bank | Revenue USD (m) |\n|---|---|\n| A | 100 |\n| B | 200 |'
        self.assertEqual(revenue_passages(text),[text])

    def test_layoffs_negation_history_conditional_and_current(self):
        rows=[make_record(1,body='No layoffs: this is not a downsizing exercise.'),
              make_record(2,body='The company reported 6000 layoffs in 2025.'),
              make_record(3,body='Not eligible if laid off 10% of staff.'),
              make_record(4,body='Acme announced today it will lay off 200 workers.')]
        result=self.ask('Summarise layoffs this month',rows)
        labels=[v for i in result['items'] for v in i['mention_classifications']]
        self.assertEqual(labels.count('current_article_event'),1)
        self.assertEqual(labels.count('historical_context'),1)
        self.assertEqual(labels.count('negated_conditional_or_speculative'),2)

    def test_layoff_timing_uses_article_year_and_requested_window(self):
        published = datetime(2025, 9, 12, tzinfo=timezone.utc)
        record = make_record(1, date=published,
            body='In 2025 Acme announced today it will lay off 200 workers.')
        answer = self.ask('Summarise layoffs', [record], since=published)
        self.assertEqual(answer['items'][0]['mention_classifications'], ['current_article_event'])
        empty = self.ask('Summarise layoffs last month', [])
        self.assertIn('requested publication window', empty['answer'])
        self.assertNotIn('current-month', empty['answer'])

    def test_weather_and_unhandled_requests_refuse_without_retrieval(self):
        for question in ('Weather in Mumbai today?', 'What is the CEO secret password?', 'Write a poem about the sea'):
            plan=plan_query(question,as_of=NOW)
            def forbidden(*args):
                raise AssertionError('Unsupported questions must not retrieve plausible answers')
            answer=answer_records(plan,{},forbidden)
            self.assertEqual(answer['status'],'unsupported')
            self.assertEqual(answer['sources'],[])

    def test_company_unknown_and_missing_parameter_do_not_broaden(self):
        rows=[make_record(1,title='Example Company Announces Research')]
        self.assertEqual(self.ask('What has MissingCorp announced recently?',rows)['items'],[])
        self.assertEqual(self.ask('Recent company updates',rows)['status'],'clarification_required')


if __name__=='__main__':
    unittest.main()
