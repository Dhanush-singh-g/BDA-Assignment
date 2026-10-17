"""Run identical Hive queries, preserve output, and reject mismatched results."""

import argparse
import json
import math
import os
import random
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def read_result(text):
    result = {}
    for line in text.splitlines():
        # Beeline emits blank lines for SET/USE statements even in silent TSV mode.
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != 6:
            raise ValueError(f"Expected six-column Beeline TSV output: {line[:120]!r}")
        key = tuple(fields[:3])
        if key in result:
            raise ValueError("Duplicate summary key")
        count, total, average = int(fields[3]), float(fields[4]), float(fields[5])
        if count < 1 or not math.isfinite(total) or not math.isfinite(average):
            raise ValueError("Invalid aggregate result")
        result[key] = (count, total, average)
    if not result:
        raise ValueError("Hive returned no summary rows")
    return result


def equivalent(left, right):
    return left.keys() == right.keys() and all(
        left[key][0] == right[key][0] and all(
            math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
            for a, b in zip(left[key][1:], right[key][1:])) for key in left)


def collect_storage(paths):
    source = Path(__file__).resolve().parent.parent / "hadoop/StorageSummary.java"
    result = {}
    with tempfile.TemporaryDirectory(prefix="fdc-storage-") as classes:
        classpath = subprocess.check_output(["hadoop", "classpath"], text=True).strip()
        subprocess.run(["javac", "-cp", classpath, "-d", classes, str(source)], check=True)
        process_env = os.environ.copy()
        process_env["HADOOP_CLASSPATH"] = classes + os.pathsep + process_env.get("HADOOP_CLASSPATH", "")
        for table, path in paths.items():
            run = subprocess.run(["hadoop", "StorageSummary", path], env=process_env,
                                 text=True, capture_output=True, check=True)
            result[table] = {"path": path, **json.loads(run.stdout)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-path", required=True)
    parser.add_argument("--rc-path", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--database", default="fdc_202410")
    parser.add_argument("--manifest", required=True, help="Preparation manifest for this input dataset")
    args = parser.parse_args()
    if args.runs < 1 or args.text_path == args.rc_path:
        parser.error("Use positive runs and distinct HDFS table paths")
    if not re.fullmatch(r"fdc_[a-zA-Z0-9_]+", args.database):
        parser.error("Use a dedicated fdc_<name> database")
    url = os.environ.get("HIVE_JDBC_URL", "jdbc:hive2://localhost:10000/default")
    user = os.environ.get("HIVE_USER", os.environ.get("USER", "hadoop"))
    manifest = json.loads(Path(args.manifest).read_text())
    if not re.fullmatch(r"[a-f0-9]{64}", manifest.get("source_sha256", "")):
        raise ValueError("Preparation manifest must include a valid source SHA-256")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    query_dir = Path(__file__).resolve().parent.parent / "hive"
    queries = [query_dir / name for name in ("nutrient_summary.hql", "protein_summary.hql")]
    evidence = {"recorded_at": datetime.now(timezone.utc).isoformat(), "database": args.database,
                "complete": False, "runs": [], "storage": {}, "source_manifest": manifest,
                "method": "One warmup per query/table pair, then seeded randomized order; elapsed includes Beeline startup. No cache flush.",
                "queries": {q.stem: q.read_text() for q in queries},
                "result_tolerance": {"relative": 1e-9, "absolute": 1e-9}}
    def checkpoint():
        temporary = output / "progress.tmp"
        temporary.write_text(json.dumps(evidence, indent=2) + "\n")
        temporary.replace(output / "progress.json")
    checkpoint()
    # Validate storage/toolchain access before launching repeated query jobs.
    evidence["storage"] = collect_storage({"nutrients_text": args.text_path, "nutrients_rcfile": args.rc_path})
    checkpoint()
    references = {}
    schedule = [(True, table, q) for q in queries for table in ("nutrients_text", "nutrients_rcfile")]
    measured = [(table, q) for _ in range(args.runs) for q in queries for table in ("nutrients_text", "nutrients_rcfile")]
    random.Random(714).shuffle(measured)
    schedule += [(False, table, q) for table, q in measured]
    for index, (warmup, table, query) in enumerate(schedule):
        evidence['current_query'] = {'number': index + 1, 'total': len(schedule),
                                     'query': query.stem, 'table': table, 'warmup': warmup,
                                     'started_at': datetime.now(timezone.utc).isoformat(),
                                     'log': f'{index:02d}-{query.stem}-{table}.log'}
        checkpoint()
        print(f"Hive query {index + 1}/{len(schedule)}: {query.stem} on {table} ({'warmup' if warmup else 'measured'})", flush=True)
        result_path = output / f"{index:02d}-{query.stem}-{table}.tsv"
        # Direct file output lets the dashboard tail Beeline/YARN diagnostics
        # while a query runs, including long intervals before its answer arrives.
        with result_path.open('w') as stdout, (output / evidence['current_query']['log']).open('w') as stderr:
            start = time.perf_counter()
            run = subprocess.run(["beeline", "-u", url, "-n", user, "--silent=true", "--showHeader=false",
                                  "--outputformat=tsv2", "--hivevar", f"TABLE={table}",
                                  "--hivevar", f"DATABASE={args.database}", "-f", str(query)],
                                 stdout=stdout, stderr=stderr)
            elapsed = time.perf_counter() - start
        run.check_returncode()
        result = read_result(result_path.read_text())
        reference = references.get(query.stem)
        if reference is not None and not equivalent(reference, result):
            raise ValueError("Text/RCFile results differ; performance comparison is invalid")
        references[query.stem] = result
        evidence["runs"].append({"table": table, "query": query.stem, "warmup": warmup, "seconds": elapsed,
                                 "groups": len(result), "records": sum(row[0] for row in result.values())})
        checkpoint()
    evidence["current_query"] = None
    evidence["complete"] = True
    checkpoint()
    (output / "benchmark.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"Verified equivalent results for {len(schedule)} executions; saved {output}/benchmark.json")


if __name__ == "__main__":
    main()
