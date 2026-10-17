"""Explicit synthetic correctness check on the development YARN cluster.

Run: .venv/bin/python tests/cluster_smoke.py
This does NOT download/sample USDA data and does NOT produce assignment benchmarks.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fdc.prepare import prepare
from test_workflows import fixture


def main():
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    run_id = "smoke_" + str(time.time_ns())
    local = Path("data") / run_id
    local.mkdir(parents=True)
    fixture(local / "synthetic.zip")
    prepare(local / "synthetic.zip", local / "prepared")
    hdfs = "/user/root/fdc/" + run_id
    database = "fdc_" + run_id
    compose = ["docker", "compose", "-f", "infra/compose.yaml", "exec", "-T", "master"]
    log_path = local / "cluster.log"

    def run(command):
        with log_path.open("a") as log:
            log.write("COMMAND " + repr(command) + "\n")
            log.flush()
            subprocess.run(compose + command, check=True, stdout=log, stderr=subprocess.STDOUT)

    print(f"Synthetic development evidence: {local}", flush=True)
    run(["bash", "scripts/verify_cluster.sh"])
    run(["bash", "scripts/hdfs_demo.sh", str(local / "synthetic.zip"), str(local / "prepared"), hdfs])
    run(["bash", "scripts/run_mapreduce.sh", hdfs + "/prepared/food_nutrients.tsv", hdfs + "/mapreduce", "2"])
    result = subprocess.check_output(compose + ["hdfs", "dfs", "-cat", hdfs + "/mapreduce/part-*"], text=True)
    actual = {parts[0]: parts[1:] for parts in (line.split("\t") for line in result.splitlines())}
    expected = {"foundation_food|1003": ["2", "4.0", "2.0"], "branded_food|1003": ["1", "7.5", "7.5"]}
    if actual != expected:
        raise AssertionError(f"YARN calculation differs: {actual!r}")
    (local / "mapreduce.tsv").write_text(result)
    run(["pig", "-x", "mapreduce", "-param", "INPUT=" + hdfs + "/prepared/food_nutrients.tsv",
         "-param", "OUTPUT=" + hdfs + "/pig_clean", "-f", "pig/clean_nutrients.pig"])
    cleaned = subprocess.check_output(compose + ["hdfs", "dfs", "-cat", hdfs + "/pig_clean/part-*"], text=True)
    if len(cleaned.splitlines()) != 3 or any(float(line.split("\t")[-1]) < 0 for line in cleaned.splitlines()):
        raise AssertionError("Pig output count/filter differs")
    run(["beeline", "-u", "jdbc:hive2://localhost:10000/default", "-n", "root",
         "--hivevar", "DATABASE=" + database, "--hivevar", "INPUT=" + hdfs + "/pig_clean",
         "--hivevar", "RC_OUTPUT=" + hdfs + "/hive_rc", "-f", "hive/tables.hql"])
    run(["python3", "-m", "fdc.hive_benchmark", "--database", database,
         "--manifest", str(local / "prepared/manifest.json"),
         "--text-path", hdfs + "/pig_clean", "--rc-path", hdfs + "/hive_rc",
         "--output", str(local / "hive"), "--runs", "1"])
    evidence = json.loads((local / "hive/benchmark.json").read_text())
    if any(row["records"] != 3 for row in evidence["runs"]):
        raise AssertionError("Hive did not aggregate all three expected clean observations")
    (local / "SUCCESS.json").write_text(json.dumps({"scope": "synthetic development correctness only",
        "hdfs": hdfs, "hive_database": database, "expected_usable_records": 3}, indent=2) + "\n")
    print(f"Distributed development checks passed; evidence: {local}")


if __name__ == "__main__":
    main()
