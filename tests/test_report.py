import json
import tempfile
import unittest
from pathlib import Path

from fdc.part1 import run_part1
from fdc.inspect_archive import inspect_archive
from fdc.report import check_groups, generate, reference_groups, timing_summary


class ReportTests(unittest.TestCase):
    def test_archive_inventory_and_crc_use_real_file(self):
        from test_workflows import fixture
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "test.zip"
            fixture(source)
            record = inspect_archive(source, verify=True)
            self.assertEqual(record["zip_bytes"], source.stat().st_size)
            self.assertTrue(record["crc_verified"])
            self.assertIn("empty_table", record["tables"])
            self.assertEqual(len(record["source_sha256"]), 64)

    def test_reference_accounts_for_negative_and_zero_amounts(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.tsv"
            source.write_text("1\tbranded_food\t\t1003\tProtein\tG\t0\n"
                              "2\tbranded_food\t\t1003\tProtein\tG\t-1\n"
                              "3\tbranded_food\t\t1003\tProtein\tG\t3.5\n")
            groups, counts = reference_groups(source)
            self.assertEqual(counts, {"prepared_rows": 3, "negative_filtered": 1, "clean_rows": 2})
            item = groups["branded_food", 1003]
            self.assertEqual((item["records"], item["total_amount"], item["mean_amount"]), (2, 3.5, 1.75))

    def test_reconciliation_rejects_missing_and_wrong_counts(self):
        expected = {("foundation_food", 1003): {"records": 2, "total_amount": 4., "mean_amount": 2.}}
        check_groups(expected, expected, "same")
        with self.assertRaises(ValueError):
            check_groups(expected, {}, "missing")
        with self.assertRaises(ValueError):
            check_groups(expected, {("foundation_food", 1003): {"records": 1, "total_amount": 4., "mean_amount": 4.}}, "wrong")

    def test_report_refuses_mixed_source_fingerprints(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            for name in ("prepared", "mongo", "hive"):
                (run / name).mkdir()
            (run / "run.json").write_text(json.dumps({"prepared_directory": "prepared", "source_sha256": "a" * 64}))
            (run / "prepared/manifest.json").write_text(json.dumps({"source_sha256": "a" * 64}))
            (run / "mongo/profile.json").write_text(json.dumps({"source_sha256": "b" * 64}))
            (run / "hive/benchmark.json").write_text(json.dumps({"source_manifest": {"source_sha256": "a" * 64}}))
            with self.assertRaisesRegex(ValueError, "fingerprints"):
                generate(run)
            self.assertFalse((run / "PART1_REPORT.md").exists())

    def test_timings_require_finite_measurements(self):
        self.assertEqual(timing_summary([3., 1., 2.])["median_seconds"], 2.)
        with self.assertRaises(ValueError):
            timing_summary([float("nan")])

    def test_run_id_validation_precedes_any_side_effect(self):
        for value in ("../outside", "bad;name", "x'", "a" * 42):
            with self.assertRaises(ValueError):
                run_part1("does-not-exist.zip", value, "full-release")


if __name__ == "__main__":
    unittest.main()
