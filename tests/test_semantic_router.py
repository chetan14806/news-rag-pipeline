"""Routing boundaries without downloading models; real-model probes are separate."""
import unittest
from unittest.mock import Mock
import numpy as np

import test_query as fixtures
from newsrag.query_planner import plan_query
from newsrag.query_engine import answer_records
from newsrag.semantic_router import SemanticRouter


class SemanticRoutingTests(unittest.TestCase):
    def test_topic_phrase_is_not_company_but_ai_names_are_preserved(self):
        for text in ('Summarize recent news about AI tools.',
                     'Show news about artificial intelligence research.'):
            plan = plan_query(text, as_of=fixtures.NOW)
            self.assertEqual((plan.intent, plan.company), ('ai', None))
        for name in ('Novus AI', 'AI Dynamics', 'Unveilr AI'):
            plan = plan_query(f'What has {name} announced recently?', as_of=fixtures.NOW)
            self.assertEqual((plan.intent, plan.company), ('company', name))

    def test_semantic_fallback_keeps_dates_and_operation(self):
        router = Mock(return_value='funding')
        plan = plan_query('Which businesses received backing recently?', as_of=fixtures.NOW,
                          semantic_route=router)
        router.assert_called_once()
        self.assertEqual(plan.intent, 'funding')
        self.assertEqual((plan.as_of - plan.since).days, 30)

    def test_explicit_and_recognized_plans_bypass_fallback(self):
        router = Mock(side_effect=AssertionError('Fallback should not run'))
        for text, options in [('Which businesses received backing?', {'intent': 'funding'}),
                              ('Which investors appear in exactly two funding rounds?', {}),
                              ('What did Acme announce?', {}),
                              ('What revenue did "Results" predict?', {}),
                              ('What did "Results" earn?', {})]:
            plan_query(text, as_of=fixtures.NOW, semantic_route=router, **options)

    def test_unsupported_actions_and_negated_fallback_do_not_return_news(self):
        router = Mock(side_effect=AssertionError('Fallback should not run'))
        for text in ('Tell me a joke about AI.', 'Write a poem about venture funding.',
                     'Predict which startup will raise money next.',
                     'Explain how startup financing works.', 'Should I buy ServiceNow stock?',
                     'Which businesses did not receive backing?',
                     "Which businesses didn't receive backing?",
                     'Which businesses haven’t received backing?'):
            with self.subTest(text=text):
                self.assertEqual(plan_query(text, semantic_route=router).intent, 'unsupported')

    def test_semantic_location_still_requires_named_target(self):
        plan = plan_query('Show every report that names Pune.', semantic_route=lambda _: 'location')
        self.assertEqual(plan.location, 'Pune')
        plan = plan_query('Find geographically relevant coverage.', semantic_route=lambda _: 'location')
        self.assertIsNone(plan.location)
        self.assertEqual(answer_records(plan, {}, None)['status'], 'clarification_required')

    def test_body_only_ai_article_is_eligible(self):
        row = fixtures.make_record(1, title='A new research initiative', category='business',
                                   body='The researchers are developing artificial intelligence tools.')
        seen = []
        def retrieve(text, ids, count):
            seen.extend(ids)
            return [{'metadata': {'article_id': ident}} for ident in ids]
        result = answer_records(plan_query('AI stories', as_of=fixtures.NOW), {row.id: row}, retrieve)
        self.assertEqual(seen, [row.id])
        self.assertEqual(result['items'][0]['article_id'], row.id)

    def test_similarity_gate_requires_absolute_score_and_distinct_label_margin(self):
        router = SemanticRouter.__new__(SemanticRouter)
        router.embedder = Mock()
        router.labels = ['funding', 'funding', 'investors', 'unsupported']
        # Set the whole example inventory for this synthetic score test.
        from unittest.mock import patch
        with patch('newsrag.semantic_router.EXAMPLES', dict.fromkeys(router.labels)):
            for scores, expected in [([.8, .79, .5, .2], 'funding'),
                                     ([.8, .79, .76, .2], 'unsupported'),
                                     ([.4, .39, .1, .2], 'unsupported')]:
                router.vectors = np.array(scores).reshape(-1, 1)
                router.embedder.encode.return_value = np.array([[1.]])
                self.assertEqual(router.classify('question')['intent'], expected)


if __name__ == '__main__':
    unittest.main()
