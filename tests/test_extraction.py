"""Offline extraction behavior with synthetic, non-publisher fixtures."""
import json
import tempfile
import unittest
from pathlib import Path

import spacy
from lxml import html

from newsrag.extraction import clean_body, extract_article, funding_details, metadata_body, money_value, MONEY
from newsrag.extraction_runner import run_extraction
from newsrag.models import ArticleRecord
from newsrag.local_entities import LocalEntities, windows, clean_name
from newsrag.storage import RawStore, article_id, sha256
from newsrag.fetching import Response

URL = 'https://www.indianweb2.com/2026/10/example.html'


def fixture(date='2026-10-14T09:53:00+05:30', body=None):
    body = body or ('Example Labs has raised ₹25 crore in seed funding, led by Example Ventures. '
                    'The Bengaluru company reported ₹25 crore in transaction sales during its first year. '
                    'The funding will support product development and recruitment across India. '
                    'Its investor manages a separate $100 million fund, which is not the size of this round.')
    return (f'<html><head><meta charset="utf-8"><link rel="canonical" href="{URL}"></head><body>'
            '<h1 class="post-title">Example Labs Raises ₹25 Crore in Seed Funding</h1>'
            f'<abbr itemprop="datePublished" title="{date}"></abbr>'
            '<span itemprop="author"><span itemprop="name">News Desk</span></span>'
            f'<div class="post-body"><p>{body}</p><script>EVIL NAVIGATION TEXT</script></div>'
            '<aside>SIDEBAR ADVERTISEMENT</aside></body></html>').encode()


class ExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nlp = spacy.blank('en')
        cls.nlp.add_pipe('sentencizer')
        ruler = cls.nlp.add_pipe('entity_ruler')
        ruler.add_patterns([{'label': 'ORG', 'pattern': 'Example Labs'},
                            {'label': 'ORG', 'pattern': 'Example Ventures'},
                            {'label': 'GPE', 'pattern': 'Bengaluru'}])

    def setUp(self):
        self.base = Path(__file__).resolve().parents[1] / 'tmp' / 'extraction-tests'
        self.base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=self.base)
        self.root = Path(self.temp.name)

    def tearDown(self):
        assert self.root.resolve().is_relative_to(self.base.resolve())
        self.temp.cleanup()

    def save(self, raw):
        return RawStore(self.root).save(URL, Response(URL, 200, {'content-type': 'text/html'}, raw), {'labels': ['Startup Funding']}, 'test')

    def test_complete_record_utc_evidence_and_funding_vs_sales(self):
        raw = fixture()
        entry = self.save(raw)
        result = extract_article(raw, entry, self.nlp)
        self.assertEqual(result.published_at.isoformat(), '2026-10-14T04:23:00+00:00')
        self.assertEqual(result.funding.amount, 250000000)
        self.assertEqual(result.funding.currency, 'INR')
        self.assertEqual(result.funding.investors, ['Example Ventures'])
        self.assertEqual(result.funding.company, 'Example Labs')
        self.assertEqual(result.category, 'funding')
        self.assertIn('Bengaluru', result.locations)
        self.assertNotIn('EVIL NAVIGATION', result.body)
        self.assertNotIn('SIDEBAR', result.body)
        self.assertTrue(all(s in result.body for s in result.provenance['summary_sentences']))
        ArticleRecord.model_validate_json(result.model_dump_json())

    def test_body_headings_and_nested_blocks_do_not_merge_words(self):
        container = html.fromstring('<div>Lead paragraph.<h4>Revenue grows</h4>'
            'Company raised funding.<div>New paragraph with <b>inline emphasis</b>.</div>'
            'Final paragraph.<h5>About</h5>Company details.</div>')
        self.assertEqual(clean_body(container).splitlines(), [
            'Lead paragraph.', 'Revenue grows', 'Company raised funding.',
            'New paragraph with inline emphasis.', 'Final paragraph.', 'About', 'Company details.'])

    def test_body_fallback_preserves_table_columns_for_revenue_evidence(self):
        from newsrag.query_engine import revenue_passages
        container = html.fromstring('<div><table><tr><th>Company</th><th>Revenue USD (m)</th></tr>'
            '<tr><td>Acme</td><td>100</td></tr></table></div>')
        body = clean_body(container)
        self.assertEqual(body.splitlines(), ['| Company | Revenue USD (m) |', '| Acme | 100 |'])
        self.assertEqual(revenue_passages(body), [body])

    def test_missing_timezone_quarantines_instead_of_using_fetch_time(self):
        for stamp in ['', '2026-10-14T09:53:00']:
            raw = fixture(stamp)
            with self.assertRaises(ValueError):
                metadata_body(raw, self.save(raw))

    def test_valuation_and_fund_size_are_not_raised_amount(self):
        doc = self.nlp('Example Labs has raised pre-seed funding led by Example Ventures. Its investor manages a $100 million fund.')
        funding, warnings = funding_details('Example Labs Raises Pre-Seed at ₹16.7 Crore Valuation', doc)
        self.assertIsNone(funding.amount)
        self.assertIn('funding_amount_unknown_or_ambiguous', warnings)
        for title in ['Example Labs Secures ₹25 Crore Contract', 'Example Labs Plans ₹25 Crore IPO']:
            self.assertIsNone(funding_details(title, doc)[0])

    def test_amount_units_and_decimal_precision(self):
        for text, expected, currency in [('₹45 lakh', '4500000', 'INR'), ('$1.3M', '1300000', 'USD'),
                                          ('Rs. 1,250 crore', '12500000000', 'INR'), ('€2.75 million', '2750000', 'EUR')]:
            value, code = money_value(MONEY.search(text))
            self.assertEqual(str(value.normalize()), str(__import__('decimal').Decimal(expected).normalize()))
            self.assertEqual(code, currency)

    def test_rerun_skips_and_changed_invalid_record_is_not_current(self):
        raw = fixture()
        entry = self.save(raw)
        run = lambda: run_extraction(self.root, nlp=self.nlp, progress=lambda *a: None)
        first = run()
        self.assertEqual((first['written'], first['accepted']), (1, 1))
        record_path = self.root / 'records' / f"{entry['id']}.json"
        before = record_path.read_bytes(), record_path.stat().st_mtime_ns
        second = run()
        self.assertEqual((second['written'], second['skipped']), (0, 1))
        self.assertEqual((record_path.read_bytes(), record_path.stat().st_mtime_ns), before)
        self.save(fixture(date=''))
        third = run()
        self.assertEqual((third['failed'], third['accepted']), (1, 0))
        manifest = json.loads((self.root / 'extraction/manifest.json').read_text())
        self.assertEqual(manifest['records'], {})
        self.assertTrue(record_path.exists())  # Historical JSON does not imply current acceptance.

    def test_tampered_record_summary_is_recomputed(self):
        entry = self.save(fixture())
        run = lambda: run_extraction(self.root, nlp=self.nlp, progress=lambda *a: None)
        run()
        path = self.root / 'records' / f"{entry['id']}.json"
        value = json.loads(path.read_text())
        value['summary'] = 'Invented summary with no source evidence.'
        path.write_text(json.dumps(value))
        self.assertEqual(run()['written'], 1)

    def test_investor_relationships_preserve_affiliations_and_ampersand_names(self):
        doc = self.nlp('Example Labs has raised ₹25 crore in seed funding, led by Example Ventures, '
                       'with participation from The Jane & John Foundation and Ravi Sharma, co-founder of Unrelated Corp. '
                       'Arun Kumar, COO of Another Corp, has also joined the round as an angel.')
        result, _ = funding_details('Example Labs Raises ₹25 Crore', doc)
        self.assertEqual(set(result.investors), {'Example Ventures', 'The Jane & John Foundation', 'Ravi Sharma', 'Arun Kumar'})

    def test_closing_round_is_not_claimed_as_closed(self):
        doc = self.nlp('Example Labs is closing a ₹25 crore funding round involving existing backers Example Ventures and Ravi Sharma, as well as new global investors.')
        result, warnings = funding_details('Example Labs Raises ₹25 Crore', doc)
        self.assertEqual(result.status, 'closing')
        self.assertEqual(set(result.investors), {'Example Ventures', 'Ravi Sharma'})
        self.assertIn('funding_round_is_closing_not_reported_closed', warnings)

    def test_schema_valid_but_changed_cached_record_is_recomputed(self):
        entry = self.save(fixture())
        run = lambda: run_extraction(self.root, nlp=self.nlp, progress=lambda *a: None)
        run()
        path = self.root / 'records' / f"{entry['id']}.json"
        value = json.loads(path.read_text())
        value['companies'] = ['Invented Organization']
        path.write_text(json.dumps(value))
        self.assertEqual(run()['written'], 1)

    def test_debt_raise_is_distinct_from_venture_round(self):
        doc = self.nlp('Example Finance has successfully raised ₹100 crore through non-convertible debentures. The issue included a ₹50 crore base and ₹50 crore green shoe option.')
        funding, _ = funding_details('Example Finance Raises ₹100 Crore via NCD Issue', doc)
        self.assertEqual((funding.amount, funding.round, funding.kind), (1000000000, 'NCD', 'debt'))

    def test_committed_support_does_not_inherit_historical_equity_round(self):
        doc = self.nlp('The Technology Development Board (TDB) has signed an agreement with Example Labs to provide ₹86 crore in financial support. '
                       'In February, Example Labs raised ₹70 crore in a Series A funding round led by Old Ventures. '
                       'The financial support will be provided through Optionally Convertible Debt.')
        funding, _ = funding_details('Example Labs Gets ₹86 Cr Financial Support', doc)
        self.assertEqual(funding.amount, 860000000)
        self.assertEqual((funding.status, funding.round, funding.kind), ('committed', 'OCD', 'debt'))
        self.assertEqual(funding.investors, ['Technology Development Board (TDB)'])

    def test_secure_adjective_is_not_a_fundraising_verb(self):
        self.assertEqual(funding_details('Example Integrates Secure Digital Payments', self.nlp('Example launches a payment product.')), (None, []))

    def test_entity_windows_reach_end_of_long_article_with_correct_offsets(self):
        import re
        from types import SimpleNamespace
        class FakeModel:
            data_processor = SimpleNamespace(
                transformer_tokenizer=SimpleNamespace(encode=lambda text, **kwargs: text.split()),
                words_splitter=lambda text: iter(text.split()))
            def inference(self, texts, labels, **kwargs):
                return [[{'label':'location', 'text':m.group(), 'start':m.start(), 'end':m.end(), 'score':0.9}
                         for m in re.finditer('Bengaluru', text)] for text in texts]
        predictor = LocalEntities.__new__(LocalEntities)
        predictor.model = FakeModel()
        body = 'ordinary text ' * 700 + 'Bengaluru is the final city.'
        values, evidence = predictor.predict(body)
        self.assertIn('Bengaluru', values['locations'])
        supported = [e for e in evidence if e['label'] == 'location']
        self.assertTrue(supported)
        self.assertTrue(all(body[e['start']:e['end']] == e['text'] for e in supported))
        self.assertGreater(supported[0]['start'], 8000)

    def test_entity_oversized_token_fails_instead_of_silent_truncation(self):
        from types import SimpleNamespace
        tokenizer = SimpleNamespace(encode=lambda text, **kwargs: list(text))
        with self.assertRaises(ValueError):
            list(windows('x'*1000, tokenizer, lambda text: 1))

    def test_generic_groups_are_not_named_people_or_companies(self):
        self.assertIsNone(clean_name('Researchers and engineers', 'people'))
        self.assertIsNone(clean_name('Indian professionals', 'people'))
        self.assertIsNone(clean_name('Fortune 500 companies', 'companies'))
        self.assertEqual(clean_name('Attorney General Todd Blanche', 'people'), 'Todd Blanche')
        self.assertEqual(clean_name('Example FintechFounded', 'companies'), 'Example Fintech')


if __name__ == '__main__':
    unittest.main()
