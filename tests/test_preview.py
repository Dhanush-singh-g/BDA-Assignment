"""Backfill previews without rerunning an analytical pipeline or modifying a DB."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fdc.preview import add_previews


class PreviewBackfillTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.output=Path(self.temp.name)
        self.profile={'database':'fdc_test','source_sha256':'a'*64,'tables':{'food':2},'selection':{'food_limit':2}}
        (self.output/'profile.json').write_text(json.dumps(self.profile))
        self.client=MagicMock();self.db=MagicMock()
        self.db.metadata.find_one.return_value={'complete':True,**self.profile}
        self.db.list_collection_names.return_value=['foods']

    def tearDown(self):self.temp.cleanup()

    def test_current_matching_capture_keeps_existing_metrics_and_does_not_run_analysis(self):
        previous=(self.output/'profile.json').read_bytes()
        def capture(db,meta,name,path,derived):
            self.assertIs(db,self.db);self.assertTrue(derived)
            (path/'previews.json').write_text(json.dumps({'source_sha256':'a'*64,'database':name}))
        with patch('fdc.preview.connect',return_value=(self.client,self.db)),patch('fdc.preview.capture_previews',side_effect=capture):
            result=add_previews(self.output)
        self.assertFalse(result['analysis_rerun'])
        self.assertEqual((self.output/'profile.json').read_bytes(),previous)
        self.assertIn('Current matching database',json.loads((self.output/'previews.json').read_text())['capture_context'])
        self.client.close.assert_called_once()

    def test_mismatched_source_selection_or_counts_is_rejected(self):
        for field,value in [('source_sha256','b'*64),('tables',{'food':3}),('selection',{'food_limit':3})]:
            self.db.metadata.find_one.return_value={'complete':True,**self.profile,field:value}
            with patch('fdc.preview.connect',return_value=(self.client,self.db)),patch('fdc.preview.capture_previews') as capture:
                with self.assertRaises(ValueError):add_previews(self.output)
                capture.assert_not_called()
        self.assertFalse((self.output/'previews.json').exists())

    def test_existing_preview_and_wrong_database_are_kept(self):
        with self.assertRaises(ValueError):add_previews(self.output,'fdc_other')
        (self.output/'previews.json').write_text('Original snapshot')
        with self.assertRaises(FileExistsError):add_previews(self.output)
        self.assertEqual((self.output/'previews.json').read_text(),'Original snapshot')

    def test_legacy_profile_needs_original_database_name(self):
        del self.profile['database'];(self.output/'profile.json').write_text(json.dumps(self.profile))
        with self.assertRaises(ValueError):add_previews(self.output)
