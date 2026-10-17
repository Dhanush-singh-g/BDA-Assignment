"""Exercise evidence loading and user-facing scope without live services."""
import json
import tempfile
import unittest
from pathlib import Path
from fdc.dashboard import create_app


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.client = create_app(self.root).test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def seed(self):
        run = self.root / 'data/realdev_test'
        (run / 'hive').mkdir(parents=True)
        (run / 'SUCCESS.json').write_text(json.dumps(dict(scope='real-data development subset only',
            parent_source_sha256='a'*64, subset_sha256='b'*64, counts={'clean_rows': 3})))
        executions = [dict(query='nutrient_summary',table='nutrients_text',warmup=True,seconds=99),
                      dict(query='nutrient_summary',table='nutrients_text',warmup=False,seconds=2),
                      dict(query='nutrient_summary',table='nutrients_text',warmup=False,seconds=4)]
        (run / 'hive/benchmark.json').write_text(json.dumps(dict(complete=True, runs=executions)))
        (run / 'hive/00-nutrient_summary-nutrients_text.tsv').write_text('branded_food\t1003\tg\t3\t12\t4\n')
        return run

    def test_empty_state_and_unknown_path(self):
        self.assertIn(b'No recorded runs found', self.client.get('/').data)
        self.assertEqual(self.client.get('/?run=../../etc').status_code, 404)
        self.assertEqual(self.client.get('/api/evidence?run=../../etc').status_code, 404)

    def test_scope_filter_and_warmup_exclusion(self):
        self.seed()
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'real-data development subset only', page.data)
        data = self.client.get('/api/evidence?run=data/realdev_test').json
        self.assertEqual(data['timings'][0]['median'], 3)
        self.assertEqual(data['timings'][0]['runs'], 2)
        self.assertEqual(data['rows'][0]['records'], 3)
        self.assertIn(b'No matching observations',self.client.get('/?q=nonexistent').data)
        self.assertNotIn(b'<script>alert',self.client.get('/?q=%3Cscript%3Ealert').data)

    def test_incomplete_evidence_reports_problem(self):
        run = self.seed()
        (run / 'hive/benchmark.json').write_text('{broken')
        self.assertIn(b'incomplete or malformed', self.client.get('/').data)
        self.assertEqual(self.client.get('/api/evidence?run=data/realdev_test').status_code,422)

    def test_full_run_preserves_scope_and_incomplete_status(self):
        run = self.root / 'results/full_run'
        run.mkdir(parents=True)
        (run / 'run.json').write_text(json.dumps(dict(dataset_kind='full-release',complete=False)))
        data = self.client.get('/api/evidence?run=results/full_run').json
        self.assertEqual(data['scope'],'full-release')
        self.assertFalse(data['complete'])

    def test_simplified_tabs_and_noneditable_source(self):
        html=self.client.get('/').data
        self.assertIn(b'View results',html)
        self.assertIn(b'Run analysis',html)
        self.assertIn(b'Entire dataset',html)
        self.assertIn(b'Choose another size',html)
        self.assertNotIn(b'id="source-db"',html)
        self.assertIn(b'fdc_home202410',html)
