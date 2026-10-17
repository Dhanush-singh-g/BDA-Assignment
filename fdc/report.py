"""Reconcile independent analytical outputs and produce an evidence-based report."""
import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from .hive_benchmark import read_result


def close(left, right):
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)


def reference_groups(path):
    """Bounded by number of type/nutrient groups, not by number of input rows."""
    groups = {}
    seen = negative = 0
    with Path(path).open(encoding="utf-8") as source:
        for line in source:
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 7:
                raise ValueError("Malformed prepared TSV")
            _, kind, _, nid, _, unit, raw_amount = fields
            seen += 1
            amount = float(raw_amount)
            if not math.isfinite(amount):
                raise ValueError("Nonfinite prepared amount")
            if amount < 0:
                negative += 1
                continue
            key = (kind, int(nid))
            item = groups.setdefault(key, {"records": 0, "sum": 0.0, "correction": 0.0, "unit": unit})
            if item["unit"] != unit:
                raise ValueError("A nutrient ID has inconsistent units")
            # Neumaier compensated accumulation: O(groups) storage.
            total = item["sum"] + amount
            item["correction"] += ((item["sum"] - total) + amount if abs(item["sum"]) >= abs(amount)
                                    else (amount - total) + item["sum"])
            item["sum"] = total
            item["records"] += 1
    for item in groups.values():
        item["total_amount"] = item.pop("sum") + item.pop("correction")
        item["mean_amount"] = item["total_amount"] / item["records"]
    return groups, {"prepared_rows": seen, "negative_filtered": negative, "clean_rows": seen - negative}


def check_groups(expected, actual, system):
    if expected.keys() != actual.keys():
        raise ValueError(f"{system}: missing or unexpected analytical groups")
    for key in expected:
        left, right = expected[key], actual[key]
        if (left["records"] != right["records"] or
                not close(left["total_amount"], right["total_amount"]) or
                not close(left["mean_amount"], right["mean_amount"])):
            raise ValueError(f"{system}: result mismatch for {key}")


def timing_summary(values):
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("Missing or invalid timing observations")
    return {"runs": len(values), "median_seconds": statistics.median(values),
            "min_seconds": min(values), "max_seconds": max(values)}


def generate(run_dir):
    run_dir = Path(run_dir)
    context = json.loads((run_dir / "run.json").read_text())
    prepared = Path(context["prepared_directory"])
    if not prepared.is_absolute():
        prepared = run_dir / prepared
    manifest = json.loads((prepared / "manifest.json").read_text())
    mongo = json.loads((run_dir / "mongo/profile.json").read_text())
    hive = json.loads((run_dir / "hive/benchmark.json").read_text())
    fingerprint = manifest["source_sha256"]
    if context["source_sha256"] != fingerprint or mongo["source_sha256"] != fingerprint or hive["source_manifest"]["source_sha256"] != fingerprint:
        raise ValueError("Source archive fingerprints differ across systems")
    if not hive.get("complete"):
        raise ValueError("Hive benchmark is incomplete")
    required = {"cluster_verification", "prepare_all_records", "mongo_full_import", "mongo_analytics_and_profile",
                "hdfs_file_operations", "yarn_streaming", "pig_cleaning", "hive_tables", "hive_benchmark"}
    passed = {stage["name"] for stage in context.get("stages", []) if stage["status"] == "passed"}
    if not required <= passed:
        raise ValueError("Missing successful workflow-stage evidence")
    if set(context["archive_tables"]) != set(mongo["tables"]):
        raise ValueError("MongoDB collection inventory differs from the archive CSV inventory")
    counts = manifest["counts"]
    if counts["food_nutrient"] != counts["written"] + counts["rejected"]:
        raise ValueError("Preparation row accounting does not reconcile")
    for name in ("food", "nutrient", "food_nutrient"):
        if mongo["tables"][name] != counts[name]:
            raise ValueError(f"MongoDB source row count differs: {name}")
    expected, accounting = reference_groups(prepared / "food_nutrients.tsv")
    if accounting["prepared_rows"] != counts["written"] or not expected:
        raise ValueError("Prepared input count is wrong or no analyzable rows exist")
    pig = json.loads((run_dir / "pig.json").read_text())
    if pig["output_rows"] != accounting["clean_rows"] or pig["negative_values"] != 0:
        raise ValueError("Pig cleaning counts do not reconcile")
    actual_mongo = {}
    for line in (run_dir / "mongo/nutrient_summary.jsonl").read_text().splitlines():
        row = json.loads(line)
        key = (row["_id"]["data_type"], row["_id"]["nutrient_id"])
        if key in actual_mongo:
            raise ValueError("Duplicate MongoDB group")
        actual_mongo[key] = row
    check_groups(expected, actual_mongo, "MongoDB")
    actual_mr = {}
    for line in (run_dir / "mapreduce.tsv").read_text().splitlines():
        key, count, total, mean = line.split("\t")
        kind, nid = key.rsplit("|", 1)
        group = (kind, int(nid))
        if group in actual_mr:
            raise ValueError("Duplicate MapReduce group")
        actual_mr[group] = {"records": int(count), "total_amount": float(total), "mean_amount": float(mean)}
    check_groups(expected, actual_mr, "MapReduce")
    timings = defaultdict(list)
    pair_counts = defaultdict(lambda: {"warmup": 0, "measured": 0})
    for index, execution in enumerate(hive["runs"]):
        query, table = execution["query"], execution["table"]
        if query not in {"nutrient_summary", "protein_summary"} or table not in {"nutrients_text", "nutrients_rcfile"}:
            raise ValueError("Unknown Hive query or table in evidence")
        raw = (run_dir / "hive" / f"{index:02d}-{query}-{table}.tsv").read_text()
        actual_hive = {}
        for (kind, nid, unit), (count, total, mean) in read_result(raw).items():
            key = (kind, int(nid))
            if key in actual_hive:
                raise ValueError("Duplicate Hive nutrient group across units")
            if key not in expected or unit != expected[key]["unit"]:
                raise ValueError("Hive nutrient unit does not match prepared data")
            actual_hive[key] = {"records": count, "total_amount": total, "mean_amount": mean}
        subset = expected if query == "nutrient_summary" else {
            key: value for key, value in expected.items() if key[1] == 1003 and value["unit"].lower() == "g"}
        check_groups(subset, actual_hive, f"Hive {query}/{table}")
        if sum(row["records"] for row in actual_hive.values()) != execution["records"]:
            raise ValueError("Hive output count differs from recorded execution")
        pair_counts[query, table]["warmup" if execution["warmup"] else "measured"] += 1
        if not execution["warmup"]:
            timings[query, table].append(execution["seconds"])
    for query in ("nutrient_summary", "protein_summary"):
        for table in ("nutrients_text", "nutrients_rcfile"):
            pair = pair_counts[query, table]
            if pair["warmup"] != 1 or pair["measured"] < 1:
                raise ValueError("Missing warmup or measured Hive runs")
        if pair_counts[query, "nutrients_text"] != pair_counts[query, "nutrients_rcfile"]:
            raise ValueError("Unequal Hive benchmark repetitions")
    mongo_timings = defaultdict(list)
    mongo_scans = defaultdict(list)
    returned = set()
    for execution in mongo["profiles"]:
        stats = execution["explain"]["executionStats"]
        if not stats.get("executionSuccess"):
            raise ValueError("MongoDB profiling query failed")
        if execution["mode"] == "indexed" and stats.get("totalKeysExamined", 0) < stats["nReturned"]:
            raise ValueError("MongoDB indexed profile has no matching index-key evidence")
        returned.add(stats["nReturned"])
        mongo_timings[execution["mode"]].append(execution["wall_seconds"])
        mongo_scans[execution["mode"]].append(stats["totalDocsExamined"])
    if len(returned) != 1 or next(iter(returned)) < 1:
        raise ValueError("MongoDB profiling plans returned different/empty results")
    if set(mongo_timings) != {"collection_scan", "indexed"} or len(mongo_timings["collection_scan"]) != len(mongo_timings["indexed"]):
        raise ValueError("Unbalanced or incomplete MongoDB profiling")
    if not all(value == mongo["tables"]["food"] for value in mongo_scans["collection_scan"]):
        raise ValueError("MongoDB baseline did not scan the full food collection")
    for name in ("nutrients_text", "nutrients_rcfile"):
        storage = hive["storage"][name]
        if storage["logical_bytes"] <= 0 or storage["replicated_bytes"] < storage["logical_bytes"]:
            raise ValueError("Invalid HDFS storage evidence")
    report = {
        "computational_checks": "passed", "dataset_kind": context["dataset_kind"],
        "deployment_kind": context["deployment_kind"], "source_sha256": fingerprint,
        "source_counts": mongo["tables"], "accounting": {**counts, **accounting},
        "groups_reconciled": len(expected), "hive_executions_verified": len(hive["runs"]),
        "hive_timings": {f"{q}/{t}": timing_summary(v) for (q, t), v in timings.items()},
        "mongo_timings": {mode: {**timing_summary(values), "median_documents_examined": statistics.median(mongo_scans[mode])}
                          for mode, values in mongo_timings.items()},
        "storage": hive["storage"],
        "text_to_rcfile_logical_ratio": hive["storage"]["nutrients_text"]["logical_bytes"] / hive["storage"]["nutrients_rcfile"]["logical_bytes"],
        "submission_status": "Requires full-release provenance, acceptable deployment evidence, and faculty/report review",
    }
    (run_dir / "reconciliation.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Track B Part 1 — execution report", "", f"Dataset classification: **{context['dataset_kind']}**.",
             f"Deployment classification: **{context['deployment_kind']}**.",
             "Computational reconciliation: **passed**. This does not establish compliance with the physical lab-system requirement.",
             "", "## Dataset and accounting", "", f"Source SHA-256: `{fingerprint}`.",
             "All CSV tables were ingested; source row counts:", "", "| Table | Rows |", "| --- | ---: |"]
    lines += [f"| {name} | {count:,} |" for name, count in sorted(mongo["tables"].items())]
    lines += ["", f"Nutrient observations scanned: {counts['food_nutrient']:,}; prepared: {counts['written']:,}; rejected: {counts['rejected']:,}.",
              f"Negative observations excluded: {accounting['negative_filtered']:,}; clean observations: {accounting['clean_rows']:,}.",
              "See preparation `rejected.jsonl` for every rejected source record and reason.",
              "", "## Theme 1 — MongoDB", "",
              "Raw CSV strings and synthetic row IDs preserve every source record. Derived food documents contain finite observations with known nutrient references.",
              "Pipelines use `$match`, `$group`, `$project`, `$unwind`, and `$facet`.",
              "The same food-ID query is profiled using forced collection and index scans; these are warmed observations.", "",
              "| Plan | Runs | Median seconds | Min | Max | Median documents examined |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for mode, values in report["mongo_timings"].items():
        lines.append(f"| {mode} | {values['runs']} | {values['median_seconds']:.6f} | {values['min_seconds']:.6f} | {values['max_seconds']:.6f} | {values['median_documents_examined']:g} |")
    lines += ["", "See `mongo/profile.json` for complete executionStats, server version and individual measurements.",
              "", "## Theme 2 — HDFS and YARN MapReduce", "",
              "The driver verifies worker registration, submits a Pi job, uploads the archive and analytical TSVs, retrieves a probe and checks its bytes, and removes only that demo directory.",
              f"Streaming output reconciles with the independently scanned prepared TSV across {len(expected):,} analytical groups.",
              "See `cluster.log` for command results, job IDs and counters, and `mapreduce.tsv` for all analytical results.",
              "", "## Theme 3 — Pig and Hive", "",
              "Pig filters missing typed fields and negative nutrient amounts on the YARN MapReduce backend. Text and gzip RCFile tables contain the resulting observations.",
              "Each saved Hive result is checked against the independent reference and the MongoDB/MapReduce outputs.",
              "One warmup per query/table pair is excluded from the following summaries. Elapsed time includes Beeline startup; caches are not flushed.", "",
              "| Query / table | Measured runs | Median seconds | Min | Max |", "| --- | ---: | ---: | ---: | ---: |"]
    for name, values in report["hive_timings"].items():
        lines.append(f"| {name} | {values['runs']} | {values['median_seconds']:.6f} | {values['min_seconds']:.6f} | {values['max_seconds']:.6f} |")
    lines += ["", "| Storage | Logical bytes | Bytes including replication |", "| --- | ---: | ---: |"]
    for name, values in report["storage"].items():
        lines.append(f"| {name} | {values['logical_bytes']:,} | {values['replicated_bytes']:,} |")
    lines += ["", f"Text/RCFile logical-size ratio: {report['text_to_rcfile_logical_ratio']:.4f}. A ratio above one means RCFile is smaller for this run.",
              "This compares uncompressed Text with gzip RCFile, so format and codec effects are combined. Small fixture sizes are not representative of the USDA release.",
              "", "## Interpretation and limitations", "",
              "Index profiling measures a selective food-ID lookup; it does not establish that every aggregation benefits equally from that index.",
              "Cross-system checks compare observations of the same nutrient ID and unit. Means are unweighted means across recorded observations, not population dietary-intake estimates.",
              "Food records with different data types and repeated nutrient observations can have different coverage. Count observations separately from distinct foods.",
              "The Hive measurements include client startup and warmed execution. Engine-only timing requires the retained Hive/YARN job logs; no cold-cache claim is made."]
    for query in ("nutrient_summary", "protein_summary"):
        text_time = report["hive_timings"][query + "/nutrients_text"]["median_seconds"]
        rc_time = report["hive_timings"][query + "/nutrients_rcfile"]["median_seconds"]
        if text_time > 0 and rc_time > 0:
            lines.append(f"For {query}, the measured Text/RCFile median elapsed-time ratio is {text_time / rc_time:.4f}. This describes this run only and includes client overhead.")
    lines += [
              "", "## Remaining submission evidence", "",
              "Confirm the entire official October 2024 archive was used. Attach physical-node inventory (or faculty-approved alternative), configurations, task placement and resource specifications.",
              "Review rejects and analytical interpretation, add team details and dataset citations, and prepare the presentation/demo.",
              "Synthetic or container results must retain those classifications. Part 2's dashboard is separate.",
              "", "## References", "",
              "- USDA FoodData Central dataset documentation: https://fdc.nal.usda.gov/download-datasets/",
              "- October 2024 CSV package: https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_csv_2024-10-31.zip",
              "- Apache Hadoop cluster setup guide: https://apache.github.io/hadoop/hadoop-project-dist/hadoop-common/ClusterSetup.html", ""]
    (run_dir / "PART1_REPORT.md").write_text("\n".join(lines))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.run_directory), indent=2))


if __name__ == "__main__":
    main()
