"""Entity type corrections require source evidence and preserve genuine cities."""
import unittest

from newsrag.entity_rules import refine


class EntityRuleTests(unittest.TestCase):
    def classify(self, body, companies=(), locations=()):
        return refine({'companies': list(companies), 'people': [], 'locations': list(locations)}, [], body)

    def test_institution_moves_to_organizations_with_exact_evidence(self):
        body = 'IIT Kanpur and Indian Institute of Technology Bombay announced a laboratory in Kanpur.'
        values, evidence = self.classify(body, locations=['IIT Kanpur', 'Indian Institute of Technology Bombay', 'Kanpur'])
        self.assertEqual(values['locations'], ['Kanpur'])
        self.assertEqual(values['companies'], ['IIT Kanpur', 'Indian Institute of Technology Bombay'])
        for quote in evidence:
            self.assertEqual(body[quote['start']:quote['end']], quote['text'])

    def test_operations_fragment_is_removed_without_inventing_a_city(self):
        values, evidence = self.classify('The site head leads Pune Operations across North America and Western Division.',
                                       locations=['Pune Operations', 'North America', 'Western Division'])
        self.assertEqual(values['locations'], ['North America', 'Western Division'])
        self.assertTrue(evidence[0]['excluded'])

    def test_explicit_platform_list_does_not_turn_products_into_places(self):
        body = ('Our technology powers HarborGo, Chennai One and Orchid Ride, which serve millions of trips. '
                'The platforms are built on shared software. The office is in Chennai.')
        values, _ = self.classify(body, locations=['HarborGo', 'Chennai One', 'Orchid Ride', 'Chennai'])
        self.assertEqual(values['locations'], ['Chennai'])
        self.assertEqual(values['companies'], [])

    def test_powered_cities_without_platform_evidence_are_retained(self):
        body = 'Our technology powers Chennai and Pune, which rely on smart grids. The cities have expanded their networks.'
        values, _ = self.classify(body, locations=['Chennai', 'Pune'])
        self.assertEqual(values['locations'], ['Chennai', 'Pune'])

    def test_generic_organization_fragments_do_not_remove_named_groups(self):
        values, _ = self.classify('The Group works with RPG Group, GroupM and Company.',
                                 companies=['Group', 'RPG Group', 'GroupM', 'Company'])
        self.assertEqual(values['companies'], ['GroupM', 'RPG Group'])

    def test_unrelated_later_platform_sentence_does_not_remove_cities(self):
        body = ('Our technology powers Chennai and Pune, which rely on smart grids. '
                'The cities have expanded their networks. The platforms elsewhere use different software.')
        values, _ = self.classify(body, locations=['Chennai', 'Pune'])
        self.assertEqual(values['locations'], ['Chennai', 'Pune'])

    def test_institution_correction_requires_a_real_body_mention(self):
        values, evidence = self.classify('Research teams work in Kanpur.', locations=['IIT Kanpur', 'Kanpur'])
        self.assertNotIn('IIT Kanpur', values['companies'])
        self.assertEqual(evidence, [])


if __name__ == '__main__':
    unittest.main()
