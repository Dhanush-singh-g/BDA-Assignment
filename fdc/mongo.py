"""Complete raw-table ingestion and reproducible MongoDB analytical evidence."""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from pymongo import ASCENDING, MongoClient

from .archive import RELEASE, checked_rows, members, rows, sha256


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


def analyze(database, output, repeats=5):
    if repeats < 1:
        raise ValueError("repeats must be positive")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    client, db = connect(database)
    try:
        manifest = db.metadata.find_one({"_id": "import", "complete": True})
        if not manifest:
            raise ValueError("A completed full import is required")
        for table in ("food", "food_nutrient", "nutrient"):
            if table not in manifest["tables"]:
                raise ValueError(f"Missing required table: {table}")
        db.raw_food_nutrient.create_index([("fdc_id", ASCENDING)], name="idx_fdc_id")
        db.raw_nutrient.create_index([("id", ASCENDING)], name="idx_nutrient_id")
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
        list(db.raw_food.aggregate(materialize, allowDiskUse=True))
        if db.foods.count_documents({}) != manifest["tables"]["food"]:
            raise RuntimeError("Derived food count does not match raw food count")
        for name, pipeline in pipelines().items():
            with (output / f"{name}.jsonl").open("w") as stream:
                for document in db.foods.aggregate(pipeline, allowDiskUse=True):
                    stream.write(json.dumps(document, allow_nan=False) + "\n")
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
                start = time.perf_counter()
                explain = db.command("explain", {"find": "raw_food", "filter": query, "hint": hint},
                                     verbosity="executionStats")
                profiles.append({"iteration": iteration + 1, "mode": mode,
                                 "wall_seconds": time.perf_counter() - start, "explain": explain})
        record = {"release": RELEASE, "source_sha256": manifest["source_sha256"],
                  "recorded_at": datetime.now(timezone.utc).isoformat(),
                  "mongodb_version": client.server_info()["version"], "tables": manifest["tables"],
                  "query": query, "profiles": profiles,
                  "method": "Alternating forced collection scan and index scan; warm-cache development measurements, not cluster evidence"}
        (output / "profile.json").write_text(json.dumps(record, indent=2, default=str) + "\n")
        return {"output": str(output), "profile_runs": len(profiles), "food_count": manifest["tables"]["food"]}
    finally:
        client.close()
