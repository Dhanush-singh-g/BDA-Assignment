"""Normalize all food/nutrient records using a disk-backed join, with accounting."""

import csv
import json
import math
import sqlite3
from pathlib import Path
from zipfile import ZipFile

from .archive import RELEASE, checked_rows, members, rows, sha256


def clean_text(value):
    return " ".join(value.split()) or "unknown"


def integer(value):
    return int(value) if value.strip() else None


def prepare(source, destination):
    destination = Path(destination)
    # A new directory prevents mixing stale and current outputs after interruption.
    destination.mkdir(parents=True, exist_ok=False)
    counts = {"food": 0, "nutrient": 0, "food_nutrient": 0, "written": 0, "rejected": 0}
    with ZipFile(source) as archive, sqlite3.connect(destination / "join.sqlite") as db:
        tables = members(archive)
        for required in ("food", "nutrient", "food_nutrient"):
            if required not in tables:
                raise ValueError(f"Missing required CSV: {required}")
        db.execute("CREATE TABLE food (id INTEGER PRIMARY KEY, type TEXT, category INTEGER)")
        db.execute("CREATE TABLE nutrient (id INTEGER PRIMARY KEY, name TEXT, unit TEXT)")
        with (destination / "foods.tsv").open("w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_NONE, quotechar=None)
            with rows(archive, tables["food"]) as reader:
                for row in checked_rows(reader):
                    fid = int(row["fdc_id"])
                    kind = clean_text(row["data_type"])
                    category = integer(row.get("food_category_id", ""))
                    db.execute("INSERT INTO food VALUES (?,?,?)", (fid, kind, category))
                    writer.writerow((fid, kind, clean_text(row["description"]), category if category is not None else ""))
                    counts["food"] += 1
            db.commit()
        with rows(archive, tables["nutrient"]) as reader:
            for row in checked_rows(reader):
                db.execute("INSERT INTO nutrient VALUES (?,?,?)", (
                    int(row["id"]), clean_text(row["name"]), clean_text(row["unit_name"])))
                counts["nutrient"] += 1
            db.commit()
        with (destination / "food_nutrients.tsv").open("w", newline="", encoding="utf-8") as out, \
                (destination / "rejected.jsonl").open("w", encoding="utf-8") as rejected:
            writer = csv.writer(out, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_NONE, quotechar=None)
            with rows(archive, tables["food_nutrient"]) as reader:
                for row in checked_rows(reader):
                    counts["food_nutrient"] += 1
                    try:
                        fid, nid = int(row["fdc_id"]), int(row["nutrient_id"])
                        amount = float(row["amount"])
                        if not math.isfinite(amount):
                            raise ValueError("Nonfinite nutrient amount")
                        food = db.execute("SELECT type,category FROM food WHERE id=?", (fid,)).fetchone()
                        nutrient = db.execute("SELECT name,unit FROM nutrient WHERE id=?", (nid,)).fetchone()
                        if food is None or nutrient is None:
                            raise ValueError("Missing food or nutrient reference")
                        writer.writerow((fid, food[0], food[1] if food[1] is not None else "", nid, nutrient[0], nutrient[1], amount))
                        counts["written"] += 1
                    except (ValueError, OverflowError) as error:
                        rejected.write(json.dumps({"record": counts["food_nutrient"], "reason": str(error), "row": row}) + "\n")
                        counts["rejected"] += 1
    record = {
        "release": RELEASE, "source_sha256": sha256(source), "counts": counts,
        "scope": "All source records scanned; no sampling or row limit. Raw CSVs retained in the ZIP.",
        "foods_columns": ["fdc_id", "data_type", "description", "food_category_id"],
        "food_nutrients_columns": ["fdc_id", "data_type", "food_category_id", "nutrient_id", "nutrient_name", "unit", "amount"],
        "text_normalization": "Whitespace collapsed for Hadoop line records; original strings preserved by MongoDB import.",
    }
    (destination / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    return record
