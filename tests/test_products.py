import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_products import validate_catalog

class ProductPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'data/products.json').read_text())

    def test_public_catalog_retains_coverage_without_promoting_pending_products(self):
        counts=validate_catalog(self.data)
        self.assertEqual(len(self.data['insurers']),21)
        self.assertEqual(counts,{'products':61,'examples':17,'pending':2})
        self.assertTrue(all(p['id'] not in {'H03','HK01'} for p in self.data['products']))
        hanwha=next(p for p in self.data['products'] if p['id']=='H02')
        self.assertIn('HNEWGA',hanwha['source_ids'])
        self.assertEqual(hanwha['pays'],[10,12])
        self.assertFalse(hanwha['examples'])
        self.assertEqual(sum(e['version_status']=='current_document' for p in self.data['products'] for e in p['examples']),5)

    def test_news_only_refund_claim_cannot_be_published_as_official(self):
        value=copy.deepcopy(self.data)
        p=next(p for p in value['products'] if p['examples'])
        p['examples'][0]['source_id']='N11'
        with self.assertRaisesRegex(ValueError,'official summary'):
            validate_catalog(value)

    def test_current_label_requires_version_evidence(self):
        value=copy.deepcopy(self.data)
        e=next(e for p in value['products'] for e in p['examples'] if e['version_status']=='version_unconfirmed')
        e['version_status']='current_document'
        with self.assertRaisesRegex(ValueError,'version-check date'):
            validate_catalog(value)

    def test_pending_entry_cannot_be_added_to_main_list(self):
        value=copy.deepcopy(self.data)
        p=copy.deepcopy(value['products'][0]);p['id']='HK01';value['products'].append(p)
        with self.assertRaises(ValueError):
            validate_catalog(value)

    def test_unsafe_source_is_rejected(self):
        value=copy.deepcopy(self.data);value['sources'][0]['url']='javascript:alert(1)'
        with self.assertRaisesRegex(ValueError,'Unsafe source URL'):
            validate_catalog(value)

    @unittest.skipUnless(shutil.which('node'),'Node is unavailable')
    def test_browser_model_publication_and_filtering_rules(self):
        result=subprocess.run(['node','--test',str(ROOT/'tests/test_products_model.cjs')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
