"""Complete raw-table ingestion and reproducible MongoDB analytical evidence."""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from pymongo import ASCENDING, MongoClient
from pymongo.errors import OperationFailure

from .archive import RELEASE, checked_rows, members, rows, sha256
from .progress import Timeline, save_json


def connect(database):
    if not re.fullmatch(r"fdc_[a-zA-Z0-9_]+", database):
        raise ValueError("Use a dedicated database named fdc_<name>")
    client = MongoClient(os.environ.get("MONGODB_URI", "mongodb://127.0.0.1:27017"),
                         serverSelectionTimeoutMS=10000)
    try:
        client.admin.command("ping")
    except Exception:
        client.close()
        raise
    return client, client[database]


def ingest(source, database, batch_size=1000):
    if not 1 <= batch_size <= 10000:
        raise ValueError("batch-size must be between 1 and 10000")
    client, db = connect(database)
    try:
        if db.list_collection_names():
            raise ValueError("Destination database is not empty. Use a new database to preserve existing work.")
        manifest = {"_id": "import", "release": RELEASE, "complete": False,
                    "source_sha256": sha256(source), "tables": {}}
        db.metadata.insert_one(manifest)
        with ZipFile(source) as archive:
            for table, member in sorted(members(archive).items()):
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", table):
                    raise ValueError(f"Unsupported table name: {table}")
                collection = db.create_collection("raw_" + table)
                count, batch = 0, []
                with rows(archive, member) as reader:
                    for count, row in enumerate(checked_rows(reader), 1):
                        # Raw CSV strings are preserved; the synthetic key is a source row ordinal.
                        if "_id" in row:
                            raise ValueError("Source unexpectedly contains reserved _id column")
                        batch.append({"_id": count, **row})
                        if len(batch) == batch_size:
                            collection.insert_many(batch, ordered=True)
                            batch.clear()
                    if batch:
                        collection.insert_many(batch, ordered=True)
                actual = collection.count_documents({})
                if actual != count:
                    raise RuntimeError(f"Count mismatch for {table}: {actual} != {count}")
                manifest["tables"][table] = count
                db.metadata.update_one({"_id": "import"}, {"$set": {f"tables.{table}": count}})
                print(f"Imported {table}: {count} rows", flush=True)
        manifest["complete"] = True
        db.metadata.replace_one({"_id": "import"}, manifest)
        return manifest
    finally:
        client.close()


def pipelines():
    return {
        "foods_by_type": [
            {"$match": {"data_type": {"$ne": ""}}},
            {"$group": {"_id": "$data_type", "foods": {"$sum": 1}}},
            {"$project": {"_id": 0, "data_type": "$_id", "foods": 1}},
            {"$sort": {"foods": -1, "data_type": 1}},
        ],
        "nutrient_summary": [
            {"$unwind": "$nutrients"},
            {"$match": {"nutrients.amount": {"$gte": 0}, "nutrients.nutrient_id": {"$ne": None}}},
            {"$group": {"_id": {"data_type": "$data_type", "nutrient_id": "$nutrients.nutrient_id"},
                         "records": {"$sum": 1}, "total_amount": {"$sum": "$nutrients.amount"},
                         "mean_amount": {"$avg": "$nutrients.amount"}}},
            {"$sort": {"_id.data_type": 1, "_id.nutrient_id": 1}},
        ],
        "overview": [{"$facet": {
            "food_count": [{"$count": "foods"}],
            "by_type": [{"$group": {"_id": "$data_type", "foods": {"$sum": 1}}}, {"$sort": {"_id": 1}}],
            "nutrient_coverage": [{"$project": {"n": {"$size": "$nutrients"}}},
                                  {"$group": {"_id": None, "mean_nutrients_per_food": {"$avg": "$n"}}}],
        }}],
    }


def preview_value(value):
    """Keep saved UI examples small; raw database documents are unchanged."""
    if isinstance(value, str):
        return value[:300] + '… [preview shortened]' if len(value) > 300 else value
    if isinstance(value, dict):
        return {key: preview_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [preview_value(item) for item in value[:5]]
    return value


def capture_previews(db, manifest, database, output, derived=False):
    foods = list(db.raw_food.find({}).sort('_id', 1).limit(3))
    observations = list(db.raw_food_nutrient.find({'fdc_id': foods[0]['fdc_id']}).limit(5)) if foods else []
    nutrient_ids = [row.get('nutrient_id') for row in observations]
    definitions = list(db.raw_nutrient.find({'id': {'$in': nutrient_ids}}).limit(5))
    record = {'source_sha256': manifest['source_sha256'], 'database': database,
              'captured_at': datetime.now(timezone.utc).isoformat(),
              'capture_context': 'Captured during this analytical run',
              'food_limit': 3, 'observation_limit': 5, 'string_limit': 300,
              'raw_food': foods, 'raw_food_nutrient': observations, 'raw_nutrient': definitions}
    if derived:
        record['foods'] = list(db.foods.find({}, {'nutrients': {'$slice': 5}}).sort('_id', 1).limit(3))
    save_json(Path(output) / 'previews.json', preview_value(record))


def analyze(database, output, repeats=5):
    if repeats < 1:
        raise ValueError("repeats must be positive")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    timeline = Timeline(output / "activity.json")
    client, db = connect(database)
    try:
        with timeline.stage("mongo_input"):
            manifest = db.metadata.find_one({"_id": "import", "complete": True})
            if not manifest:
                raise ValueError("A completed import is required")
            for table in ("food", "food_nutrient", "nutrient"):
                if table not in manifest["tables"]:
                    raise ValueError(f"Missing required table: {table}")
            origin = manifest
            origin_database = database
            candidate = manifest.get('source_database')
            if isinstance(candidate, str) and re.fullmatch(r'fdc_[A-Za-z0-9_]+', candidate):
                try:
                    previous = client[candidate].metadata.find_one({'_id': 'import', 'complete': True})
                except OperationFailure as error:
                    if error.code != 13:
                        raise
                    previous = None  # Parent metadata is optional for a restricted analytics account.
                if previous and previous.get('source_sha256') == manifest['source_sha256']:
                    origin, origin_database = previous, candidate
            source_import = {'database': origin_database, 'complete': origin.get('complete', False),
                             'dataset_kind': origin.get('dataset_kind', 'full-import'),
                             'tables': origin.get('tables', {}),
                             'basis': 'Snapshot of completed-import metadata, not a live recount by the dashboard'}
            input_record = {'database': database, 'source_sha256': manifest['source_sha256'],
                            'tables': manifest['tables'], 'source_import': source_import}
            save_json(output / 'input.json', input_record)
        with timeline.stage("mongo_indexes"):
            with timeline.operation("Build the food-nutrient lookup index"):
                db.raw_food_nutrient.create_index([("fdc_id", ASCENDING)], name="idx_fdc_id")
            with timeline.operation("Build the nutrient-definition index"):
                db.raw_nutrient.create_index([("id", ASCENDING)], name="idx_nutrient_id")
            save_json(output / 'indexes.json', {name: db[name].index_information() for name in ('raw_food_nutrient', 'raw_nutrient')})
        capture_previews(db, manifest, database, output)
        materialize = [
            {"$lookup": {"from": "raw_food_nutrient", "localField": "fdc_id", "foreignField": "fdc_id",
                         "pipeline": [
                             {"$lookup": {"from": "raw_nutrient", "localField": "nutrient_id",
                                          "foreignField": "id", "pipeline": [{"$project": {"_id": 0, "id": 1}}],
                                          "as": "definition"}},
                             {"$match": {"definition.0": {"$exists": True}}},
                             {"$project": {"_id": 0, "source_id": "$id",
                             "nutrient_id": {"$convert": {"input": "$nutrient_id", "to": "int", "onError": None, "onNull": None}},
                             "amount": {"$convert": {"input": "$amount", "to": "double", "onError": None, "onNull": None}}}},
                             {"$match": {"nutrient_id": {"$ne": None},
                                          "amount": {"$gt": float("-inf"), "$lt": float("inf")}}}],
                         "as": "nutrients"}},
            {"$out": "foods"},
        ]
        definitions = pipelines()
        save_json(output / 'pipelines.json', definitions)
        with timeline.stage("mongo_pipelines"):
            with timeline.operation("Join foods with their nutrient observations and save derived food documents"):
                list(db.raw_food.aggregate(materialize, allowDiskUse=True))
            if db.foods.count_documents({}) != manifest["tables"]["food"]:
                raise RuntimeError("Derived food count does not match raw food count")
            for name, pipeline in definitions.items():
                with timeline.operation("Calculate " + name.replace("_", " ")), (output / f"{name}.jsonl").open("w") as stream:
                    for document in db.foods.aggregate(pipeline, allowDiskUse=True):
                        stream.write(json.dumps(document, allow_nan=False) + "\n")
        capture_previews(db, manifest, database, output, derived=True)
        with timeline.stage("mongo_profile"):
            sample = db.raw_food.find_one({}, {"fdc_id": 1})
            if not sample:
                raise ValueError("No food rows available to profile")
            query = {"fdc_id": sample["fdc_id"]}
            db.raw_food.create_index([("fdc_id", ASCENDING)], name="idx_fdc_id")
            profiles = []
            # Alternate order; both plans use the same query. $natural forces the no-index baseline.
            for iteration in range(repeats):
                modes = [("collection_scan", {"$natural": 1}), ("indexed", "idx_fdc_id")]
                for mode, hint in modes[::1 if iteration % 2 == 0 else -1]:
                    with timeline.operation(f"Index comparison {iteration + 1}/{repeats}: {mode}"):
                        start = time.perf_counter()
                        explain = db.command("explain", {"find": "raw_food", "filter": query, "hint": hint},
                                             verbosity="executionStats")
                        elapsed = time.perf_counter() - start
                    profiles.append({"iteration": iteration + 1, "mode": mode,
                                     "wall_seconds": elapsed, "explain": explain})
            record = {"release": RELEASE, "source_sha256": manifest["source_sha256"],
                      "dataset_kind": manifest.get("dataset_kind", "full-import"),
                      "selection": manifest.get("selection"),
                      "recorded_at": datetime.now(timezone.utc).isoformat(),
                      "mongodb_version": client.server_info()["version"], "tables": manifest["tables"],
                      "query": query, "profiles": profiles,
                      "method": "Alternating forced collection scan and index scan; warm-cache development measurements, not cluster evidence"}
            record['database'] = database
            record['source_import'] = source_import
            record['indexes'] = {name: db[name].index_information() for name in
                                 ('raw_food', 'raw_food_nutrient', 'raw_nutrient')}
            record['derived_food_count'] = manifest['tables']['food']
            save_json(output / "profile.json", record)
        return {"output": str(output), "profile_runs": len(profiles), "food_count": manifest["tables"]["food"]}
    finally:
        client.close()
