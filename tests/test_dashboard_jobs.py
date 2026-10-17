"""Verify workflow boundaries, background launch, locking and failure evidence."""
import fcntl
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fdc.dashboard import create_app
from fdc.dashboard_jobs import JobManager, Worker, BusyError, exports, write


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = create_app(self.root)
        self.client = self.app.test_client()
        self.headers = {'X-Control-Token': self.app.config['CONTROL_TOKEN']}
        self.manager = JobManager(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_mutations_require_token_same_origin_and_local_host(self):
        url = '/api/control/jobs'
        body = {'action': 'stop_services'}
        self.assertEqual(self.client.post(url,json=body).status_code,403)
        self.assertEqual(self.client.post(url,json=body,headers={**self.headers,'Origin':'https://elsewhere.example'}).status_code,403)
        self.assertEqual(self.client.get(url,headers={'Host':'malicious.example'}).status_code,403)
        self.assertEqual(self.client.post(url,headers=self.headers,data='x').status_code,415)

    def test_reject_commands_paths_and_invalid_sizes(self):
        for payload in ({'action':'shell','command':'touch /tmp/unsafe'},
                        {'action':['workflow']},
                        {'action':'workflow','foods':50001,'source':'fdc_main'},
                        {'action':'workflow','foods':True},
                        {'action':'workflow','foods':0},
                        {'action':'workflow','foods':100001},
                        {'action':'workflow','foods':50000,'source':'fdc_foo; uname'},
                        {'action':'existing','export':'../../etc'}):
            self.assertEqual(self.client.post('/api/control/jobs',json=payload,headers=self.headers).status_code,400)
        self.assertEqual(self.client.get('/api/control/jobs/../../etc/log').status_code,404)

    def test_only_one_worker_can_start_even_across_managers(self):
        with (self.manager.directory/'active.lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BusyError):
                JobManager(self.root).submit({'action':'stop_services'})
            response=self.client.post('/api/control/jobs',json={'action':'stop_services'},headers=self.headers)
            self.assertEqual(response.status_code,409)

    def test_background_launch_uses_fixed_argv_and_fresh_names(self):
        with patch('fdc.dashboard_jobs.subprocess.Popen') as launch:
            response=self.client.post('/api/control/jobs',json={'action':'workflow','foods':50000},headers=self.headers)
        self.assertEqual(response.status_code,202)
        args, kwargs=launch.call_args
        self.assertIn('fdc.dashboard_jobs',args[0])
        self.assertTrue(kwargs['start_new_session'])
        self.assertFalse(kwargs.get('shell',False))
        self.assertEqual(len(kwargs['pass_fds']),1)
        state=response.json
        self.assertEqual(state['status'],'queued')
        self.assertEqual(state['spec']['source'],'fdc_home202410')
        # With no real child holding a lock, stale queued jobs become interrupted.
        self.assertEqual(self.manager.jobs()[0]['status'],'interrupted')

    def test_failed_stage_is_saved_and_later_stages_do_not_run(self):
        job_id='a'*32
        folder=self.manager.path(job_id); folder.mkdir()
        write(folder/'state.json',dict(id=job_id,status='queued',spec={'action':'stop_services'},stages=[]))
        worker=Worker(self.root,job_id)
        with patch.object(worker,'check_tools',side_effect=ValueError('tools missing')), patch.object(worker,'command') as command:
            worker.run()
        state=json.loads((folder/'state.json').read_text())
        self.assertEqual(state['status'],'failed')
        self.assertIn('tools missing',state['error'])
        self.assertEqual(state['stages'][0]['status'],'failed')
        command.assert_not_called()

    def test_existing_export_needs_matching_scope_tables_and_selection(self):
        folder=self.root/'data/dev50k_export_01'; (folder/'prepared').mkdir(parents=True)
        mongo=self.root/'results/mongo/dev50k_01'; mongo.mkdir(parents=True)
        meta=dict(complete=True,dataset_kind='development-subset',source_sha256='a'*64,
                  tables={'food':50000},selection={'food_limit':50000})
        write(folder/'subset.json',meta)
        write(folder/'prepared/manifest.json',{'parent_source_sha256':'a'*64})
        write(mongo/'profile.json',meta)
        self.assertEqual(exports(self.root)['data/dev50k_export_01']['foods'],50000)
        meta['selection']={'food_limit':10000};write(mongo/'profile.json',meta)
        self.assertEqual(exports(self.root),{})

    def test_log_returns_only_bounded_tail_of_known_job_files(self):
        folder=self.manager.path('b'*32);folder.mkdir()
        write(folder/'state.json',{})
        (folder/'worker.log').write_text('x'*40000+'END')
        log=self.manager.log('b'*32)
        self.assertTrue(log.endswith('END'))
        self.assertLess(len(log),19000)

    def test_interrupted_worker_blocks_new_work_until_service_stop(self):
        folder=self.manager.path('c'*32);folder.mkdir()
        write(folder/'state.json',dict(id='c'*32,status='interrupted',spec={},stages=[]))
        with self.assertRaises(BusyError):
            self.manager.submit({'action':'start_cluster'})
        with patch('fdc.dashboard_jobs.subprocess.Popen'):
            state=self.manager.submit({'action':'stop_services'})
        self.assertEqual(state['spec']['action'],'stop_services')

    def test_custom_sizes_work_and_database_is_fixed(self):
        with patch('fdc.dashboard_jobs.subprocess.Popen'):
            response=self.client.post('/api/control/jobs',json={'action':'workflow','foods':25000},headers=self.headers)
        self.assertEqual(response.status_code,202)
        self.assertEqual(response.json['spec']['foods'],25000)
        self.assertEqual(response.json['spec']['source'],'fdc_home202410')
        response=self.client.post('/api/control/jobs',json={'action':'workflow','foods':10000,'source':'fdc_other'},headers=self.headers)
        self.assertEqual(response.status_code,400)

    def test_full_dataset_requires_zip_and_uses_fixed_source(self):
        with patch('fdc.dashboard_jobs.full_archive',return_value=None):
            response=self.client.post('/api/control/jobs',json={'action':'full_workflow'},headers=self.headers)
        self.assertEqual(response.status_code,400)
        folder=self.root/'data/raw';folder.mkdir(parents=True,exist_ok=True)
        archive=folder/'FoodData_Central_csv_2024-10-31.zip';archive.write_bytes(b'fixture')
        with patch('fdc.dashboard_jobs.subprocess.Popen'):
            response=self.client.post('/api/control/jobs',json={'action':'full_workflow'},headers=self.headers)
        self.assertEqual(response.status_code,202)
        self.assertEqual(response.json['spec']['source'],'fdc_home202410')
        self.assertEqual(response.json['spec']['archive'],str(archive))
        self.assertEqual(response.json['spec']['dataset_kind'],'full-release')

    def test_full_worker_reuses_import_and_selects_full_driver(self):
        job_id='d'*32;folder=self.manager.path(job_id);folder.mkdir()
        write(folder/'state.json',dict(id=job_id,status='queued',spec={'action':'full_workflow','archive':'/fixture.zip'},stages=[]))
        worker=Worker(self.root,job_id)
        with patch.object(worker,'check_tools'), patch.object(worker,'start_mongo'), patch('fdc.part1.run_part1') as run:
            worker.run()
        self.assertEqual(json.loads((folder/'state.json').read_text())['status'],'succeeded')
        self.assertEqual(run.call_args.kwargs['reuse_database'],'fdc_home202410')
        self.assertEqual(run.call_args.kwargs['repeats'],5)
        self.assertTrue(callable(run.call_args.kwargs['before_cluster']))
        self.assertTrue(json.loads((folder/'state.json').read_text())['result'].startswith('results/fullui_'))

    def test_existing_import_verifier_rejects_mismatch_and_checks_counts(self):
        from fdc.part1 import verify_existing_import
        client=MagicMock(); db=MagicMock()
        db.metadata.find_one.return_value={'complete':True,'source_sha256':'a'*64,'tables':{'food':2}}
        db.__getitem__.return_value.count_documents.return_value=2
        with patch('fdc.mongo.connect',return_value=(client,db)):
            verify_existing_import('fdc_home202410','a'*64,{'food':{}})
        client.close.assert_called_once()
        with patch('fdc.mongo.connect',return_value=(client,db)):
            with self.assertRaises(ValueError): verify_existing_import('fdc_home202410','b'*64,{'food':{}})
        db.__getitem__.return_value.count_documents.return_value=1
        with patch('fdc.mongo.connect',return_value=(client,db)):
            with self.assertRaises(ValueError): verify_existing_import('fdc_home202410','a'*64,{'food':{}})
        db.metadata.find_one.return_value['dataset_kind']='development-subset'
        with patch('fdc.mongo.connect',return_value=(client,db)):
            with self.assertRaises(ValueError): verify_existing_import('fdc_home202410','a'*64,{'food':{}})

    def test_full_progress_and_logs_are_read_from_results_directory(self):
        folder=self.manager.path('e'*32);folder.mkdir()
        write(folder/'state.json',dict(id='e'*32,status='failed',spec={'action':'full_workflow'},stages=[]))
        write(folder/'evidence.json',{'run_directory':'results/fullui_test'})
        result=self.root/'results/fullui_test';(result/'hive').mkdir(parents=True)
        write(result/'run.json',{'stages':[{'name':'hive_benchmark','status':'failed'}]})
        write(result/'hive/progress.json',{'runs':[{}],'complete':False})
        (result/'cluster.log').write_text('Saved full-run diagnostics')
        state=self.manager.jobs()[0]
        self.assertEqual(state['hive_progress']['expected'],24)
        self.assertEqual(state['hive_progress']['completed'],1)
        self.assertEqual(state['analysis_stages'][0]['name'],'hive_benchmark')
        self.assertIn('Saved full-run diagnostics',self.manager.log('e'*32))
