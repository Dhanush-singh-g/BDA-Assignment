"""Presentation commands target recorded sources and never execute during viewing."""
import json
import shlex
import tempfile
import unittest
from pathlib import Path
from fdc.presentation import commands,input_sample
from fdc.mongo import pipelines


class PresentationTests(unittest.TestCase):
    def test_mongo_commands_are_quoted_read_only_and_target_selected_database(self):
        found=commands('fdc_demo','/user/root/fdc/demo','fdc_demo',pipeline_definitions=pipelines())
        for key in ['raw','linked','aggregate','observations','explain','nutrient_summary']:
            argv=shlex.split(found[key])
            self.assertEqual(argv[:3],['docker','exec','fdc-mongo-dev'])
            js=argv[-1]
            self.assertIn('getSiblingDB("fdc_demo")',js)
            self.assertNotIn('dropDatabase',js)
        self.assertIn('$unwind',found['nutrient_summary'])
        self.assertIn('/user/root/fdc/demo/prepared/food_nutrients.tsv',found['hdfs_input'])

    def test_native_hadoop_commands_do_not_use_compose_or_guess_databases(self):
        native=commands(None,'/user/hadoop/fdc/demo','fdc_demo',native=True)
        self.assertTrue(native['hdfs_list'].startswith('hdfs dfs'))
        self.assertTrue(native['hive_text'].startswith('beeline'))
        self.assertNotIn('docker',native['hive_text'])
        self.assertIsNone(native['raw'])
        self.assertIsNone(commands(None,None,None)['hive_text'])
        self.assertIsNone(commands(None,None,'bad`; DROP DATABASE test;')['hive_text'])

    def test_bounded_prepared_rows_require_matching_source_and_stay_inside_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'run';prepared=folder/'prepared';prepared.mkdir(parents=True)
            (prepared/'manifest.json').write_text(json.dumps({'source_sha256':'a'*64}))
            (prepared/'food_nutrients.tsv').write_text('1\tbranded_food\tcat\t1003\tProtein\tg\t4\n'*10)
            rows=input_sample(folder,root,{}, {},'a'*64)
            self.assertEqual(len(rows),5)
            self.assertEqual(rows[0]['amount'],'4')
            self.assertEqual(input_sample(folder,root,{}, {},'b'*64),[])
            self.assertEqual(input_sample(folder,root,{'prepared_directory':'/etc'}, {},'a'*64),[])

    def test_generated_commands_parse_in_shell_and_skip_write_pipelines(self):
        import subprocess
        for native in [True,False]:
            for command in commands('fdc_test','/user/root/fdc/test','fdc_test',native=native,pipeline_definitions=pipelines()).values():
                if command:
                    checked=subprocess.run(['bash','-n'],input=command,text=True,capture_output=True)
                    self.assertEqual(checked.returncode,0,checked.stderr)
        bad=commands('fdc_test',None,None,pipeline_definitions={'nutrient_summary':[{'$out':'overwrite'}]})
        self.assertFalse(bad.get('nutrient_summary'))
