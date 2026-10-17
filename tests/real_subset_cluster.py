"""Compare a linked USDA development subset across MongoDB, MapReduce and Hive.

This is development evidence, not full-release assignment benchmarking.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fdc.prepare import prepare
from fdc.report import reference_groups, check_groups
from fdc.hive_benchmark import read_result
from fdc.progress import Timeline, snapshot, tracked_run
from test_workflows import fixture


def main():
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    run_id = "realdev_" + str(time.time_ns())
    local = Path("data") / run_id
    local.mkdir(parents=True)
    import argparse, shutil
    parser = argparse.ArgumentParser()
    parser.add_argument('--subset', required=True)
    parser.add_argument('--mongo-results', required=True)
    parser.add_argument('--result-file', help='Write the generated evidence directory for the dashboard worker')
    args = parser.parse_args()
    source = Path(args.subset)
    metadata = json.loads((source / 'subset.json').read_text())
    manifest = json.loads((source / 'prepared/manifest.json').read_text())
    profile = json.loads((Path(args.mongo_results) / 'profile.json').read_text())
    if (metadata['dataset_kind'] != 'development-subset' or
            profile.get('dataset_kind') != 'development-subset' or
            profile['source_sha256'] != metadata['source_sha256'] or
            profile['tables'] != metadata['tables'] or profile.get('selection') != metadata.get('selection')):
        raise ValueError('MongoDB results and exported subset provenance differ')
    shutil.copyfile(source / 'development.zip', local / 'development.zip')
    shutil.copytree(source / 'prepared', local / 'prepared')
    expected, counts = reference_groups(local / 'prepared/food_nutrients.tsv')
    actual_mongo = {}
    for line in (Path(args.mongo_results) / 'nutrient_summary.jsonl').read_text().splitlines():
        row = json.loads(line)
        actual_mongo[row['_id']['data_type'], int(row['_id']['nutrient_id'])] = row
    check_groups(expected, actual_mongo, 'MongoDB subset')
    hdfs = "/user/root/fdc/" + run_id
    database = "fdc_" + run_id
    compose = ["docker", "compose", "-f", "infra/compose.yaml", "exec", "-T", "master"]
    log_path = local / "cluster.log"
    timeline = Timeline(local / "activity.json")
    snapshot(local, root)

    def run(command):
        with log_path.open("a") as log:
            log.write("COMMAND " + repr(command) + "\n")
            log.flush()
            tracked_run(local / 'operation.json', compose + command, check=True, stdout=log, stderr=subprocess.STDOUT)

    if args.result_file:
        Path(args.result_file).write_text(json.dumps({'run_directory': local.as_posix()}) + '\n')
    print(f"Real-data subset development evidence: {local}", flush=True)
    with timeline.stage("cluster_verification"):
        run(["bash", "scripts/verify_cluster.sh"])
    with timeline.stage("hdfs_operations"):
        run(["bash", "scripts/hdfs_demo.sh", str(local / "development.zip"), str(local / "prepared"), hdfs])
    with timeline.stage("mapreduce"):
        run(["bash", "scripts/run_mapreduce.sh", hdfs + "/prepared/food_nutrients.tsv", hdfs + "/mapreduce", "2"])
        result = subprocess.check_output(compose + ["hdfs", "dfs", "-cat", hdfs + "/mapreduce/part-*"], text=True)
        actual = {}
        for line in result.splitlines():
            key, count, total, mean = line.split('\t')
            kind, nid = key.rsplit('|', 1)
            actual[kind, int(nid)] = dict(records=int(count), total_amount=float(total), mean_amount=float(mean))
        check_groups(expected, actual, 'YARN MapReduce')
        (local / "mapreduce.tsv").write_text(result)
    with timeline.stage("pig"):
        run(["pig", "-x", "mapreduce", "-param", "INPUT=" + hdfs + "/prepared/food_nutrients.tsv",
             "-param", "OUTPUT=" + hdfs + "/pig_clean", "-f", "pig/clean_nutrients.pig"])
        cleaned = subprocess.check_output(compose + ["hdfs", "dfs", "-cat", hdfs + "/pig_clean/part-*"], text=True)
        if len(cleaned.splitlines()) != counts["clean_rows"] or any(float(line.split("\t")[-1]) < 0 for line in cleaned.splitlines()):
            raise AssertionError("Pig output count/filter differs")
    with timeline.stage("hive_tables"):
        run(["beeline", "-u", "jdbc:hive2://localhost:10000/default", "-n", "root",
             "--hivevar", "DATABASE=" + database, "--hivevar", "INPUT=" + hdfs + "/pig_clean",
             "--hivevar", "RC_OUTPUT=" + hdfs + "/hive_rc", "-f", "hive/tables.hql"])
    with timeline.stage("hive_benchmark"):
        run(["python3", "-m", "fdc.hive_benchmark", "--database", database,
             "--manifest", str(local / "prepared/manifest.json"),
             "--text-path", hdfs + "/pig_clean", "--rc-path", hdfs + "/hive_rc",
             "--output", str(local / "hive"), "--runs", "1"])
        evidence = json.loads((local / "hive/benchmark.json").read_text())
        for index, execution in enumerate(evidence['runs']):
            query, table = execution['query'], execution['table']
            raw = (local / 'hive' / f'{index:02d}-{query}-{table}.tsv').read_text()
            actual = {}
            for (kind, nid, unit), (count, total, mean) in read_result(raw).items():
                key = kind, int(nid)
                if key not in expected or unit != expected[key]['unit']:
                    raise ValueError('Hive nutrient unit mismatch')
                actual[key] = dict(records=count, total_amount=total, mean_amount=mean)
            reference = expected if query == 'nutrient_summary' else {
                k: v for k, v in expected.items() if k[1] == 1003 and v['unit'].lower() == 'g'}
            check_groups(reference, actual, 'Hive ' + query + '/' + table)
    (local / "SUCCESS.json").write_text(json.dumps({"scope": "real-data development subset only",
        "hdfs": hdfs, "hive_database": database, "expected_usable_records": counts["clean_rows"], "counts": counts,
        "parent_source_sha256": metadata["source_sha256"],
        "subset_sha256": manifest["source_sha256"], "mongo_results": args.mongo_results}, indent=2) + "\n")
    print(f"Distributed development checks passed; evidence: {local}")


if __name__ == "__main__":
    main()
