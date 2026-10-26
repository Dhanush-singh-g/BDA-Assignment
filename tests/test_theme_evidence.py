"""Check assignment reporting against artifacts, including missing and failed steps."""
import json
import tempfile
import unittest
from pathlib import Path
from fdc.progress import Timeline, snapshot
from fdc.theme_evidence import details, live_themes
from fdc.dashboard import create_app


def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))


class ThemeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.run=self.root/'data/realdev_test';self.run.mkdir(parents=True)
        self.mongo=self.root/'results/mongo/test';self.mongo.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, rc_bytes=50):
        save(self.run/'SUCCESS.json',{'scope':'real-data development subset only','counts':{'prepared_rows':4,'negative_filtered':1,'clean_rows':3},'hdfs':'/user/root/fdc/test'})
        profile={'source_sha256':'a'*64,'tables':{'food':2,'food_nutrient':4,'nutrient':1},'query':{'fdc_id':'10'},'profiles':[]}
        for mode,docs,keys in [('collection_scan',2,0),('indexed',1,1)]:
            profile['profiles'].append({'mode':mode,'iteration':1,'explain':{'executionStats':{'executionSuccess':True,'nReturned':1,'totalDocsExamined':docs,'totalKeysExamined':keys,'executionTimeMillis':0}}})
        for name in ('foods_by_type','overview','nutrient_summary'):(self.mongo/(name+'.jsonl')).write_text('{}\n')
        hive={'complete':True,'source_manifest':{'counts':{'written':4,'rejected':0}},'runs':[{'table':'nutrients_text'},{'table':'nutrients_rcfile'}],
              'storage':{'nutrients_text':{'logical_bytes':100},'nutrients_rcfile':{'logical_bytes':rc_bytes}}}
        (self.run/'mapreduce.tsv').write_text('branded_food|1003\t3\t12\t4\n')
        (self.run/'cluster.log').write_text("COMMAND ['bash', 'scripts/verify_cluster.sh']\nHadoop 2.10.2\nLive datanodes (2)\nHostname: worker1\nHostname: worker2\nTotal Nodes:2\nCOMMAND ['bash', 'scripts/run_mapreduce.sh']\nRunning job: job_123_0002\nSubmitted application application_123_0002\nCOMMAND ['pig']\njob_123_0003\n")
        return profile,hive

    def test_completed_legacy_artifacts_cover_requirements_without_fabricated_snapshot(self):
        profile,hive=self.fixture()
        data=details(self.run,self.root,self.mongo,profile,hive,'a'*64)
        self.assertEqual([t['status'] for t in data['themes']],['passed']*3)
        self.assertEqual(data['jobs'],['job_123_0002','application_123_0002'])
        self.assertEqual(data['live_datanodes'],2);self.assertEqual(data['running_workers'],2)
        self.assertEqual(data['worker_names'],['worker1','worker2'])
        self.assertEqual({r['verb'] for r in data['operations']},{'mkdir','put','get','cat','rm -r'})
        self.assertEqual(data['pig_input'],4);self.assertEqual(data['pig_output'],3)
        self.assertEqual(data['negative_filtered'],1)
        self.assertEqual(data['compression']['change_percent'],50)
        self.assertFalse(data['pipelines_recorded']);self.assertFalse(data['programs']['pig']['recorded'])
        self.assertEqual(data['software']['Hadoop client'],'2.10.2')

    def test_missing_evidence_stays_unrecorded_and_failed_activity_wins(self):
        data=details(self.run,self.root,self.mongo,{}, {},'a'*64)
        self.assertTrue(all(t['status']=='not_recorded' for t in data['themes']))
        profile,hive=self.fixture()
        save(self.run/'activity.json',{'stages':[{'key':'mapreduce','status':'failed'}]})
        data=details(self.run,self.root,self.mongo,profile,hive,'a'*64)
        self.assertEqual(data['themes'][1]['status'],'failed')

    def test_larger_rcfile_is_not_reported_as_compression_saving(self):
        profile,hive=self.fixture(rc_bytes=250)
        data=details(self.run,self.root,self.mongo,profile,hive,'a'*64)
        self.assertFalse(data['compression']['smaller']);self.assertEqual(data['compression']['change_percent'],150)
        self.assertEqual(data['compression']['ratio'],.4)

    def test_live_theme_progress_reads_mongo_and_distributed_timelines(self):
        save(self.mongo/'activity.json',{'stages':[{'key':k,'status':'passed'} for k in ('mongo_input','mongo_indexes','mongo_pipelines','mongo_profile')]})
        save(self.run/'activity.json',{'stages':[{'key':'cluster_verification','status':'passed'},{'key':'hdfs_operations','status':'running'}]})
        state={'spec':{'action':'workflow'},'stages':[],'mongo_results':'results/mongo/test','evidence':'data/realdev_test'}
        themes=live_themes(self.root,state)
        self.assertEqual(themes[0]['status'],'passed');self.assertEqual(themes[1]['status'],'running');self.assertEqual(themes[2]['status'],'pending')

    def test_timeline_failure_records_failure_instead_of_success(self):
        progress=Timeline(self.run/'activity.json')
        with self.assertRaises(ValueError):
            with progress.stage('pig'):raise ValueError('bad row')
        stage=json.loads((self.run/'activity.json').read_text())['stages'][0]
        self.assertEqual(stage['status'],'failed');self.assertEqual(stage['error_type'],'ValueError')

    def test_view_only_disables_laptop_commands_and_keeps_results_view(self):
        root=self.root/'separate';root.mkdir()
        app=create_app(root,controls=False);client=app.test_client()
        page=client.get('/').data
        self.assertIn(b'job controls disabled',page);self.assertNotIn(b'id="new-job"',page)
        self.assertEqual(client.get('/api/control/jobs').status_code,403)
        self.assertEqual(client.post('/api/control/jobs',json={'action':'start_cluster'}).status_code,403)
        self.assertFalse((root/'data/ui_jobs').exists())

    def test_full_run_snapshots_actual_hdfs_driver_and_new_input_provenance(self):
        from fdc.theme_evidence import SOURCE_ROOT, source_programs
        snapshot(self.run,SOURCE_ROOT,full=True)
        code=source_programs(self.run)
        self.assertEqual(code['hdfs']['path'],'fdc/part1.py')
        self.assertTrue(code['hdfs']['recorded'])
        self.assertIn('def hdfs_operations',code['hdfs']['text'])
        save(self.mongo/'input.json',{'source_sha256':'a'*64,'database':'fdc_home202410','tables':{'food':2},
            'source_import':{'database':'fdc_source','tables':{'food':20},'complete':True}})
        details_data=details(self.run,self.root,self.mongo,{}, {},'a'*64)
        self.assertEqual(details_data['collections'],{'food':2})
        self.assertEqual(details_data['source_import']['tables'],{'food':20})

    def test_archived_previews_require_matching_source_and_bound_aggregate_rows(self):
        from fdc.theme_evidence import mongo_examples
        save(self.mongo/'previews.json',{'source_sha256':'a'*64,'raw_food':[{'fdc_id':'10'}]})
        (self.mongo/'foods_by_type.jsonl').write_text(''.join(json.dumps({'foods':i})+'\n' for i in range(10)))
        found=mongo_examples(self.mongo,'a'*64)
        self.assertEqual(found['documents']['raw_food'][0]['fdc_id'],'10')
        self.assertEqual(len(found['aggregations']['foods_by_type']),5)
        self.assertEqual(mongo_examples(self.mongo,'b'*64)['documents'],{})

    def test_document_preview_truncation_does_not_change_source(self):
        from fdc.mongo import preview_value
        source={'description':'A'*1000,'nutrients':list(range(10))}
        shown=preview_value(source)
        self.assertIn('[preview shortened]',shown['description'])
        self.assertEqual(shown['nutrients'],list(range(5)))
        self.assertEqual(len(source['description']),1000)
        self.assertEqual(len(source['nutrients']),10)
