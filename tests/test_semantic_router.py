"""Semantic-primary wiring/constraint contracts; real-encoder evaluation is separate."""
import unittest
import json
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch

import test_query as fixtures
from newsrag.query_planner import plan_query
from newsrag.query_engine import answer_records, QueryEngine
from newsrag.semantic_router import SemanticRouter


class SemanticRoutingTests(unittest.TestCase):
    def test_unparsed_temporal_units_require_clarification(self):
        plan = plan_query('List venture recipients during the preceding week.', semantic_route=lambda _: 'funding')
        self.assertIsNotNone(plan.clarification)

    def test_company_month_name_is_not_a_publication_date(self):
        plan = plan_query('What has May Mobility announced?', semantic_route=lambda _: 'company',
                          entity_catalog={'companies': ['May Mobility']})
        self.assertIsNone(plan.clarification)
        self.assertEqual(plan.company, 'May Mobility')

    def test_topic_and_company_slots_do_not_select_the_operation(self):
        for text in ('Summarize recent news about AI tools.',
                     'Show news about artificial intelligence research.'):
            plan = plan_query(text, semantic_route=lambda _: 'ai')
            self.assertEqual((plan.intent, plan.company), ('ai', None))
        for name in ('Novus AI', 'AI Dynamics', 'Unveilr AI'):
            plan = plan_query(f'What has {name} announced recently?', semantic_route=lambda _: 'company')
            self.assertEqual((plan.intent, plan.company), ('company', name))

    def test_semantic_operation_keeps_independent_dates(self):
        router = Mock(return_value='funding')
        plan = plan_query('Which businesses received backing recently?', as_of=fixtures.NOW,
                          semantic_route=router)
        router.assert_called_once()
        self.assertEqual(plan.intent, 'funding')
        self.assertEqual((plan.as_of - plan.since).days, 30)

    def test_only_explicit_intent_bypasses_semantic_recognition(self):
        router = Mock(side_effect=AssertionError('Explicit intent must bypass the model'))
        plan_query('Which businesses received backing?', semantic_route=router, intent='funding')
        for text, expected in [('Which investors appear in exactly two funding rounds?', 'investors'),
                               ('What did Acme announce?', 'company'),
                               ('What revenue did "Results" predict?', 'revenue'),
                               ('What did "Results" earn?', 'revenue')]:
            router = Mock(return_value=expected)
            self.assertEqual(plan_query(text, semantic_route=router).intent, expected)
            router.assert_called_once_with(text)

    def test_keywords_cannot_override_an_unsupported_semantic_decision(self):
        for text in ('Tell me a joke about AI.', 'Write a poem about venture funding.',
                     'Predict which startup will raise money next.', 'Should I buy ServiceNow stock?',
                     'Show funding and layoffs and revenue together.'):
            router = Mock(return_value='unsupported')
            self.assertEqual(plan_query(text, semantic_route=router).intent, 'unsupported')
            router.assert_called_once_with(text)

    def test_negative_constraint_is_checked_after_semantic_recognition(self):
        router = Mock(return_value='funding')
        plan = plan_query('Which businesses did not receive backing?', semantic_route=router)
        router.assert_called_once()
        self.assertEqual(plan.intent, 'funding')
        self.assertIsNotNone(plan.clarification)

    def test_exact_one_is_a_typed_constraint_not_a_funding_route(self):
        for phrase in ('exactly one funding round', 'only one round', 'exactly 1 financing round',
                       'at most one funding round', 'once', 'a lone funding round',
                       'a single funding round', 'just one funding round', 'one round only'):
            for options in ({'semantic_route': lambda _: 'investors'}, {'intent': 'investors'}):
                plan = plan_query(f'Which investors participated in {phrase}?', **options)
                self.assertEqual(plan.intent, 'investors')
                self.assertEqual(plan.count_condition.value, 1)
                self.assertEqual(plan.count_condition.unit, 'rounds')
                self.assertIsNone(plan.location)
                rows = [fixtures.funded(1), fixtures.funded(2, company='Beta')]
                result = answer_records(plan, {r.id: r for r in rows}, None)
                self.assertEqual(result['status'], 'clarification_required')
                self.assertEqual(result['items'], [])

    def test_count_phrase_does_not_consume_a_later_location(self):
        for phrase in ('a lone funding round', 'a single funding round', 'just one funding round',
                       'one round only', 'exactly one funding round'):
            with self.subTest(phrase=phrase):
                plan = plan_query(f'Which investors participated in {phrase} in New Delhi?',
                                  as_of=fixtures.NOW, intent='investors')
                self.assertEqual(plan.location, 'New Delhi')
                self.assertEqual(plan.count_condition.model_dump(), {'unit': 'rounds', 'comparison': 'eq', 'value': 1})
                self.assertIsNotNone(plan.clarification)

    def test_lone_round_cannot_fall_back_to_an_unrestricted_funding_list(self):
        plan = plan_query('Which investors participated in a lone funding round?',
                          as_of=fixtures.NOW, semantic_route=lambda _: 'funding')
        rows = [fixtures.funded(1), fixtures.funded(2, company='Beta')]
        result = answer_records(plan, {row.id: row for row in rows}, None)
        self.assertEqual(plan.intent, 'funding')
        self.assertIsNone(plan.location)
        self.assertEqual(result['status'], 'clarification_required')
        self.assertEqual(result['items'], [])

    def test_lone_in_a_place_name_is_not_a_count(self):
        plan = plan_query('Which investors participated in multiple rounds in Lone Pine?',
                          as_of=fixtures.NOW, intent='investors')
        self.assertEqual(plan.location, 'Lone Pine')
        self.assertEqual(plan.count_condition.model_dump(), {'unit': 'rounds', 'comparison': 'gt', 'value': 1})
        self.assertIsNone(plan.clarification)

    def test_conflicting_count_cannot_return_wrong_funding_list(self):
        plan = plan_query('Which investors joined exactly one funding round?', semantic_route=lambda _: 'funding')
        self.assertEqual(plan.intent, 'funding')  # validation must not choose an operation by keywords
        self.assertIsNotNone(plan.clarification)

    def test_uncertain_model_decision_requests_clarification(self):
        plan = plan_query('Unclear request', semantic_route=lambda _: {
            'intent': 'unsupported', 'accepted': False, 'candidate': 'funding'})
        self.assertEqual(answer_records(plan, {}, None)['status'], 'clarification_required')

    def test_unsupported_request_score_can_veto_a_confident_topic_match(self):
        decision = SemanticRouter.decide({'ai': .7, 'unsupported': .45, 'company': .1}, 'some request')
        self.assertEqual(decision['intent'], 'unsupported')
        self.assertFalse(decision['accepted'])

    def test_comparative_constraint_cannot_be_silently_dropped(self):
        route = Mock(return_value='layoffs')
        plan = plan_query('Compare funding amounts with revenue and employee reductions.', semantic_route=route)
        route.assert_called_once()
        self.assertEqual(plan.intent, 'layoffs')
        self.assertIsNotNone(plan.clarification)

    def test_planning_without_a_model_does_not_restore_keyword_routing(self):
        plan = plan_query('Which investors joined exactly one funding round?')
        self.assertEqual(plan.intent, 'unsupported')
        self.assertIsNotNone(plan.clarification)

    def test_catalog_resolves_slots_without_a_fixed_question_template(self):
        plan = plan_query('Bring me the things Orion Systems put out around Mumbai.',
                          semantic_route=lambda _: 'company',
                          entity_catalog={'companies': ['Orion Systems'], 'locations': ['Mumbai']})
        self.assertEqual((plan.company, plan.location), ('Orion Systems', 'Mumbai'))

    def test_common_nouns_and_question_words_are_not_corpus_company_slots(self):
        catalog = {'companies': ['Startups', 'WHO'], 'locations': []}
        for question, operation in [('Which startups raised funding?', 'funding'),
                                    ('Who repeatedly financed companies?', 'investors'),
                                    ('Summarise the news about layoffs this month.', 'layoffs')]:
            plan = plan_query(question, semantic_route=lambda _: operation, entity_catalog=catalog)
            self.assertIsNone(plan.company)
        self.assertEqual(SemanticRouter.prepare('Who repeatedly financed companies?', catalog),
                         'Who repeatedly financed companies?')

    def test_known_entities_and_titles_are_masked_only_for_scoring(self):
        text = SemanticRouter.prepare('What did Orion Systems in Pune report in "AI Revenue"?',
                                      {'companies': ['Orion Systems'], 'locations': ['Pune']})
        self.assertIn('the company', text)
        self.assertIn('the location', text)
        self.assertNotIn('AI Revenue', text)

    def test_semantic_location_still_requires_a_named_target(self):
        plan = plan_query('Show every report that names Pune.', semantic_route=lambda _: 'location')
        self.assertEqual(plan.location, 'Pune')
        plan = plan_query('Find geographically relevant coverage.', semantic_route=lambda _: 'location')
        self.assertEqual(answer_records(plan, {}, None)['status'], 'clarification_required')

    def test_conflicting_entity_types_do_not_rewrite_question_meaning(self):
        catalog = {'companies': ['India', 'Orion Systems'], 'locations': ['INDIA', 'Pune']}
        text = SemanticRouter.prepare('List all articles mentioning India and Pune.', catalog)
        self.assertEqual(text, 'List all articles mentioning India and the location.')
        self.assertEqual(SemanticRouter.prepare('What has India announced?', catalog),
                         'What has India announced?')

    def test_location_intent_does_not_gain_company_filter_from_noisy_catalog(self):
        catalog = {'companies': ['India'], 'locations': ['India']}
        for options in ({'semantic_route': lambda _: 'location'}, {'intent': 'location'}):
            plan = plan_query('List all articles that mention India.', entity_catalog=catalog,
                              as_of=fixtures.NOW, **options)
            self.assertEqual((plan.intent, plan.location, plan.company, plan.since),
                             ('location', 'India', None, None))
            rows = [fixtures.make_record(n, body='India supports the research programme.')
                    for n in range(1, 9)]
            result = answer_records(plan, {row.id: row for row in rows}, None)
            self.assertEqual(result['status'], 'answered')
            self.assertEqual(len(result['items']), 8)

    def test_company_target_with_shared_name_does_not_gain_location_filter(self):
        catalog = {'companies': ['India'], 'locations': ['India']}
        plan = plan_query('What has India announced recently?', semantic_route=lambda _: 'company',
                          entity_catalog=catalog, as_of=fixtures.NOW)
        self.assertEqual((plan.company, plan.location), ('India', None))
        explicit = plan_query('List all articles mentioning India.', intent='location', company='Example',
                              entity_catalog=catalog, as_of=fixtures.NOW)
        self.assertEqual((explicit.company, explicit.location), ('Example', 'India'))

    def test_body_only_ai_article_is_eligible(self):
        row = fixtures.make_record(1, title='A new research initiative', category='business',
                                   body='The researchers are developing artificial intelligence tools.')
        retrieve = Mock(return_value=[{'metadata': {'article_id': row.id}}])
        result = answer_records(plan_query('AI stories', intent='ai'), {row.id: row}, retrieve)
        self.assertEqual(result['items'][0]['article_id'], row.id)

    def test_similarity_requires_absolute_score_and_label_margin(self):
        for scores, expected in [({'funding': .8, 'investors': .5, 'unsupported': .2}, 'funding'),
                                 ({'funding': .8, 'investors': .79, 'unsupported': .2}, 'unsupported'),
                                 ({'funding': .2, 'investors': .1, 'unsupported': .05}, 'unsupported')]:
            self.assertEqual(SemanticRouter.decide(scores, 'question')['intent'], expected)

    def test_engine_uses_primary_semantic_route_even_when_question_says_funding(self):
        engine = QueryEngine(Path('unused-test-root'))
        engine.embedder = Mock()
        engine.router = Mock()
        engine.router.classify.return_value = {'intent': 'investors', 'candidate': 'investors',
                                               'accepted': True, 'score': .9, 'margin': .3}
        rows = [fixtures.funded(1), fixtures.funded(2, company='Beta')]
        state = {'config': {'selection': None}, 'chunks': 2, 'run_id': 'synthetic'}
        with patch('newsrag.query_engine.writer_lock', return_value=nullcontext()), \
             patch('newsrag.query_engine.checked_index', return_value=(Mock(), state)), \
             patch('newsrag.query_engine.load_inputs', return_value=({r.id: r for r in rows}, {})), \
             patch('newsrag.query_engine.atomic_json'):
            result = engine.answer('Which investors participated in exactly one funding round?', as_of=fixtures.NOW)
        engine.router.classify.assert_called_once()
        self.assertEqual(result['plan']['intent'], 'investors')
        self.assertEqual(result['plan']['count_condition'], {'unit': 'rounds', 'comparison': 'eq', 'value': 1})
        self.assertEqual(result['status'], 'clarification_required')
        self.assertEqual(result['items'], [])

    def test_evaluation_questions_are_not_routing_examples(self):
        from newsrag.semantic_router import EXAMPLES
        path = Path(__file__).parent / 'data/semantic_questions.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        heldout = {q.casefold() for values in data['heldout'].values() for q in values}
        development = {q.casefold() for values in data['development'].values() for q in values}
        prototypes = {q.casefold() for values in EXAMPLES.values() for q in values}
        self.assertFalse(heldout & development)
        self.assertFalse(heldout & prototypes)
        seen = heldout | development | prototypes
        for name in ('semantic_acceptance.json', 'semantic_final_acceptance.json'):
            groups = json.loads((path.parent / name).read_text(encoding='utf-8'))['questions']
            questions = {q.casefold() for values in groups.values() for q in values}
            self.assertFalse(questions & seen)
            seen |= questions


if __name__ == '__main__':
    unittest.main()
