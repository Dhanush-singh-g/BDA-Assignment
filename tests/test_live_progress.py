"""Verify that live metadata describes running work, never completed history."""
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from io import StringIO
from pathlib import Path
from fdc.dashboard_jobs import JobManager, Worker, write
from fdc.progress import tracked_run, operation


class LiveProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manager = JobManager(self.root)
        self.folder = self.manager.path('f' * 32)
        self.folder.mkdir()
        self.state = {'id': 'f' * 32, 'status': 'running', 'spec': {'action': 'existing'},
                      'stages': [{'name': 'Distributed checks', 'status': 'running',
                                  'started_at': '2026-01-01T00:00:00+00:00'}]}

    def tearDown(self):
        self.temp.cleanup()

    def test_actual_child_is_visible_before_exit_and_failure_is_recorded(self):
        path = self.folder / 'operation.json'
        release = self.root / 'release'
        errors = []
        def run():
            try:
                tracked_run(path, [sys.executable, '-c',
                    'import time, pathlib; p=pathlib.Path('+repr(str(release))+'); '
                    '\nwhile not p.exists(): time.sleep(.01)\nraise SystemExit(7)'], check=True)
            except subprocess.CalledProcessError as error:
                errors.append(error.returncode)
        thread = threading.Thread(target=run)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if path.is_file() and json.loads(path.read_text()).get('pid'):
                    break
                time.sleep(.01)
            live = self.manager.live(self.state)
            self.assertIsNotNone(live['operation']['pid'])
            self.assertEqual(live['operation']['status'], 'running')
            self.assertTrue(thread.is_alive())
        finally:
            release.touch()
            thread.join(5)
        self.assertEqual(errors, [7])
        recorded = json.loads(path.read_text())
        self.assertEqual(recorded['returncode'], 7)
        self.assertEqual(recorded['status'], 'failed')
        self.assertIsNone(self.manager.live(self.state)['operation'])

    def test_completed_job_never_has_live_metadata_and_old_stage_is_ignored(self):
        write(self.folder / 'operation.json', {'status': 'running', 'started_at': '2025-01-01', 'label': 'old command'})
        self.assertIsNone(self.manager.live(self.state)['operation'])
        self.state['status'] = 'succeeded'
        self.assertIsNone(self.manager.live(self.state))

    def test_deeper_timeline_and_active_hive_log_are_visible(self):
        result = self.root / 'data/realdev_123'
        (result / 'hive').mkdir(parents=True)
        self.state['evidence'] = 'data/realdev_123'
        write(self.folder / 'state.json', self.state)
        write(self.folder / 'evidence.json', {'run_directory': self.state['evidence']})
        write(result / 'activity.json', {'stages': [{'name': 'Hive queries', 'status': 'running', 'started_at': '2026-01-02'}]})
        write(result / 'operation.json', {'label': 'Run benchmark', 'status': 'running', 'started_at': '2026-01-03', 'pid': 123})
        name = '00-nutrient_summary-nutrients_text.log'
        write(result / 'hive/progress.json', {'current_query': {'log': name}, 'runs': []})
        (result / 'hive' / name).write_text('Map 50% Reduce 0%\n')
        live = self.manager.live(self.state)
        self.assertEqual(live['stage'], 'Hive queries')
        self.assertEqual(live['operation']['pid'], 123)
        self.assertEqual(live['last_output']['text'], 'Map 50% Reduce 0%')
        self.assertIn('Map 50%', self.manager.log(self.state['id']))
        write(result / 'hive/progress.json', {'current_query': {'log': '../../../outside.log'}})
        self.assertIsNone(self.manager.query_log(self.state))

    def test_timeout_and_interrupted_operations_do_not_claim_success(self):
        path = self.root / 'operation.json'
        with self.assertRaises(subprocess.TimeoutExpired):
            tracked_run(path, [sys.executable, '-c', 'import time; time.sleep(10)'], timeout=.05)
        self.assertEqual(json.loads(path.read_text())['status'], 'failed')
        with self.assertRaises(KeyboardInterrupt):
            with operation(path, 'Aggregation'):
                raise KeyboardInterrupt()
        self.assertEqual(json.loads(path.read_text())['status'], 'failed')

    def test_failed_captured_command_keeps_diagnostics(self):
        write(self.folder / 'state.json', self.state)
        worker = Worker(self.root, self.state['id'])
        with patch('sys.stdout', new_callable=StringIO) as output:
            with self.assertRaises(subprocess.CalledProcessError):
                worker.command([sys.executable, '-c', "print('service not ready'); raise SystemExit(2)"], capture=True)
        self.assertIn('service not ready', output.getvalue())
        self.assertEqual(json.loads((self.folder / 'operation.json').read_text())['status'], 'failed')

    def test_full_run_uses_inner_mongo_operation(self):
        result = self.root / 'results/fullui_test'
        (result / 'mongo').mkdir(parents=True)
        self.state['evidence'] = 'results/fullui_test'
        self.state['analysis_stages'] = [{'name': 'mongo_analytics_and_profile', 'status': 'running', 'started_at': '2026-01-02'}]
        write(result / 'mongo/activity.json', {'stages': [{'name': 'Aggregation pipelines', 'status': 'running', 'started_at': '2026-01-03'}]})
        write(result / 'mongo/operation.json', {'label': 'Join foods and nutrients', 'status': 'running', 'started_at': '2026-01-04'})
        live = self.manager.live(self.state)
        self.assertEqual(live['stage'], 'Aggregation pipelines')
        self.assertEqual(live['operation']['label'], 'Join foods and nutrients')
