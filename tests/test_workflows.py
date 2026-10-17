import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from zipfile import ZipFile

from fdc.archive import checked_rows, members, rows
from fdc.hive_benchmark import equivalent, read_result
from fdc.prepare import prepare

ROOT = Path(__file__).resolve().parent.parent


def fixture(path, category="", include_unknown=False):
    tables = {
        "food": [
            ["fdc_id", "data_type", "description", "food_category_id"],
            ["10", "foundation_food", 'Apple, raw\nwith "skin"\tintact', "9"],
            ["20", "branded_food", "A" * 140000, category],
        ],
        "nutrient": [["id", "name", "unit_name"], ["1003", "Protein", "g"]],
        "food_nutrient": [
            ["id", "fdc_id", "nutrient_id", "amount"],
            ["1", "10", "1003", "2.5"], ["2", "20", "1003", "7.5"],
            ["3", "10", "1003", "-1"], ["4", "10", "1003", ""],
            ["5", "999", "1003", "5"], ["6", "10", "1003", "NaN"],
            ["7", "10", "1003", "1.5"],
        ],
        "food_category": [["id", "code", "description"], ["9", "0900", "Fruit"]],
        "additional_table": [["id", "notes"], ["1", "All source tables must survive"]],
        "empty_table": [["id", "notes"]],
    }
    if include_unknown:
        tables["food_nutrient"].append(["8", "10", "999999", "100"])
    with ZipFile(path, "w") as archive:
        for table, data in tables.items():
            text = io.StringIO(newline="")
            csv.writer(text).writerows(data)
            archive.writestr(f"release/{table}.csv", text.getvalue())
    return tables


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.source = self.path / "fixture.zip"
        fixture(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_full_scan_and_reconciliation(self):
        record = prepare(self.source, self.path / "prepared")
        self.assertEqual(record["counts"], {
            "food": 2, "nutrient": 1, "food_nutrient": 7, "written": 4, "rejected": 3})
        lines = (self.path / "prepared/foods.tsv").read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(len(lines[0].split("\t")), 4)
        self.assertIn('Apple, raw with "skin" intact', lines[0])
        self.assertEqual(len(lines[1].split("\t")[2]), 140000)
        rejects = [json.loads(line) for line in (self.path / "prepared/rejected.jsonl").read_text().splitlines()]
        self.assertEqual([row["record"] for row in rejects], [4, 5, 6])
        with self.assertRaises(FileExistsError):
            prepare(self.source, self.path / "prepared")
        zero = self.path / "zero.zip"
        fixture(zero, category="0")
        prepare(zero, self.path / "zero")
        self.assertEqual((self.path / "zero/foods.tsv").read_text().splitlines()[1].split("\t")[3], "0")

    def test_mapreduce_real_subprocesses(self):
        prepare(self.source, self.path / "prepared")
        data = (self.path / "prepared/food_nutrients.tsv").read_text()
        mapper = subprocess.run([sys.executable, str(ROOT / "mapreduce/mapper.py")],
                                input=data, text=True, capture_output=True, check=True)
        self.assertIn("NegativeAmountsFiltered,1", mapper.stderr)
        shuffled = "\n".join(sorted(mapper.stdout.splitlines())) + "\n"
        reducer = subprocess.run([sys.executable, str(ROOT / "mapreduce/reducer.py")],
                                 input=shuffled, text=True, capture_output=True, check=True)
        result = {row[0]: row[1:] for row in (line.split("\t") for line in reducer.stdout.splitlines())}
        self.assertEqual(result["foundation_food|1003"], ["2", "4.0", "2.0"])
        self.assertEqual(result["branded_food|1003"], ["1", "7.5", "7.5"])

    def test_bad_mapper_input_fails(self):
        result = subprocess.run([sys.executable, str(ROOT / "mapreduce/mapper.py")],
                                input="bad\trow\n", text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_archive_rejects_ambiguous_tables(self):
        source = self.path / "duplicate.zip"
        with ZipFile(source, "w") as archive:
            archive.writestr("a/food.csv", "id\n1\n")
            archive.writestr("b/food.csv", "id\n2\n")
        with ZipFile(source) as archive, self.assertRaises(ValueError):
            members(archive)

    def test_malformed_csv_is_not_silently_truncated(self):
        source = self.path / "bad.zip"
        with ZipFile(source, "w") as archive:
            archive.writestr("food.csv", "id,description\n1,apple,extra\n")
        with ZipFile(source) as archive:
            with rows(archive, members(archive)["food"]) as reader, self.assertRaises(ValueError):
                list(checked_rows(reader))

    def test_hive_comparison_detects_missing_and_changed_results(self):
        left = read_result("foundation_food\t1003\tg\t2\t4.0\t2.0\n")
        self.assertTrue(equivalent(left, read_result("\n\nfoundation_food\t1003\tg\t2\t4.0\t2.0\n\n")))
        self.assertTrue(equivalent(left, read_result("foundation_food\t1003\tg\t2\t4.00000000001\t2\n")))
        self.assertFalse(equivalent(left, read_result("foundation_food\t1003\tg\t1\t4\t4\n")))
        self.assertFalse(equivalent(left, read_result("branded_food\t1003\tg\t2\t4\t2\n")))
        with self.assertRaises(ValueError):
            read_result("")


@unittest.skipUnless(os.environ.get("FDC_MONGO_TESTS") == "1", "Set FDC_MONGO_TESTS=1 with local MongoDB")
class MongoIntegrationTests(unittest.TestCase):
    def test_full_import_analytics_and_explain(self):
        from fdc.mongo import analyze, connect, ingest
        database = "fdc_test_" + uuid.uuid4().hex
        client, db = connect(database)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                source = path / "fixture.zip"
                fixture(source, include_unknown=True)
                manifest = ingest(source, database, batch_size=2)
                self.assertTrue(manifest["complete"])
                self.assertEqual(manifest["tables"]["additional_table"], 1)
                self.assertEqual(manifest["tables"]["empty_table"], 0)
                self.assertIn("raw_empty_table", db.list_collection_names())
                self.assertEqual(manifest["tables"]["food_nutrient"], 8)
                self.assertEqual(db.raw_food.find_one({"fdc_id": "20"})["description"], "A" * 140000)
                with self.assertRaises(ValueError):
                    ingest(source, database)
                result = analyze(database, path / "results", repeats=2)
                self.assertEqual(result["food_count"], 2)
                summary = [json.loads(line) for line in (path / "results/nutrient_summary.jsonl").read_text().splitlines()]
                apple = next(row for row in summary if row["_id"]["data_type"] == "foundation_food")
                self.assertEqual((apple["records"], apple["mean_amount"]), (2, 2.0))
                self.assertEqual(apple["total_amount"], 4.0)
                self.assertNotIn(999999, [row["_id"]["nutrient_id"] for row in summary])
                profile = json.loads((path / "results/profile.json").read_text())
                for run in profile["profiles"]:
                    stats = run["explain"]["executionStats"]
                    self.assertEqual(stats["nReturned"], 1)
                    if run["mode"] == "indexed":
                        self.assertEqual(stats["totalDocsExamined"], 1)
                    else:
                        self.assertEqual(stats["totalDocsExamined"], 2)
        finally:
            client.drop_database(database)
            client.close()


if __name__ == "__main__":
    unittest.main()
