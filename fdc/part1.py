"""Execute Track B Part 1 and preserve evidence without overwriting prior runs."""
import argparse
import contextlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from .archive import members, sha256
from .report import generate
from .progress import snapshot, tracked_run

ROOT = Path(__file__).resolve().parent.parent


def verify_existing_import(database, fingerprint, inventory):
    """Verify reuse without changing raw collections or inventing an import stage."""
    from .mongo import connect
    client, db = connect(database)
    try:
        manifest = db.metadata.find_one({'_id': 'import', 'complete': True})
        if (not manifest or manifest.get('dataset_kind') == 'development-subset' or
                manifest.get('source_sha256') != fingerprint or set(manifest.get('tables', {})) != set(inventory)):
            raise ValueError('Existing full import does not match the selected ZIP')
        for table, count in manifest['tables'].items():
            if db['raw_' + table].count_documents({}) != count:
                raise ValueError('Existing import count differs: ' + table)
        return manifest
    finally:
        client.close()


def run_part1(archive, run_id, dataset_kind, mode="docker", repeats=5,
              reuse_database=None, before_cluster=None):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,40}", run_id) or repeats < 1:
        raise ValueError("Use a letter followed by at most 40 letters/digits/underscores and positive repeats")
    if dataset_kind not in {"full-release", "synthetic"} or mode not in {"docker", "client"}:
        raise ValueError("Invalid dataset classification or cluster mode")
    archive = Path(archive).resolve(strict=True)
    with ZipFile(archive) as source:
        tables = members(source)
        if not {"food", "nutrient", "food_nutrient"} <= tables.keys():
            raise ValueError("The required USDA CSV tables are missing")
        inventory = {name: {"uncompressed_bytes": info.file_size, "compressed_bytes": info.compress_size}
                     for name, info in tables.items()}
    run_dir = ROOT / "results" / run_id
    prepared = ROOT / "data/prepared" / run_id
    if prepared.exists():
        raise FileExistsError("Prepared destination already exists; use a new run ID")
    run_dir.mkdir(parents=True, exist_ok=False)
    snapshot(run_dir, ROOT, full=True)
    prefix = ["docker", "compose", "-f", str(ROOT / "infra/compose.yaml"), "exec", "-T"] if mode == "docker" else []
    if mode == "docker":
        for name in ("HIVE_JDBC_URL", "HIVE_USER"):
            if os.environ.get(name):
                prefix.extend(["-e", name])
        prefix.append("master")
    state = {
        "run_id": run_id, "dataset_kind": dataset_kind,
        "deployment_kind": "containers-one-host" if mode == "docker" else "cluster-client-unverified-physical-topology",
        "complete": False, "started_at": datetime.now(timezone.utc).isoformat(),
        "source_sha256": sha256(archive), "source_archive": str(archive),
        "archive_tables": inventory, "prepared_directory": os.path.relpath(prepared, run_dir), "stages": [],
        "client": {"hostname": platform.node(), "os": platform.platform(), "cpu_count": os.cpu_count(),
                   "free_disk_bytes": shutil.disk_usage(ROOT).free},
        "submission_note": "Full release and acceptable physical deployment must be reviewed separately; dataset kind is caller-declared.",
    }
    hdfs_root = f"/user/{'root' if mode == 'docker' else os.environ.get('USER', 'hadoop')}/fdc/{run_id}"
    if not re.fullmatch(r"/user/[A-Za-z0-9_.-]+/fdc/[A-Za-z0-9_]+", hdfs_root):
        raise ValueError("Unsupported HDFS user/path")
    state["hdfs_root"] = hdfs_root
    database = "fdc_" + run_id
    mongo_database = reuse_database or database
    state['mongo_database'] = mongo_database
    state['mongo_input_mode'] = 'verified-existing-import' if reuse_database else 'new-import'

    def save():
        temp = run_dir / "run.tmp"
        temp.write_text(json.dumps(state, indent=2) + "\n")
        temp.replace(run_dir / "run.json")

    def remote_path(path):
        path = Path(path).resolve()
        return "/project/" + path.relative_to(ROOT).as_posix() if mode == "docker" else str(path)

    def command(args, *, remote=False, output=None, input_path=None):
        argv = (prefix if remote else []) + [str(arg) for arg in args]
        display = list(argv)
        if "-u" in display:
            display[display.index("-u") + 1] = "<configured JDBC URL>"
        with contextlib.ExitStack() as stack:
            log = stack.enter_context((run_dir / "cluster.log").open("ab"))
            log.write(("COMMAND " + json.dumps(display) + "\n").encode())
            log.flush()
            target = stack.enter_context(Path(output).open("wb")) if output else log
            source = stack.enter_context(Path(input_path).open("rb")) if input_path else subprocess.DEVNULL
            return tracked_run(run_dir / 'operation.json', argv, display=display, cwd=ROOT, stdin=source, stdout=target, stderr=log, check=True)

    def stage(name, action):
        print(f"{name}: starting", flush=True)
        item = {"name": name, "status": "running", "started_at": datetime.now(timezone.utc).isoformat()}
        state["stages"].append(item)
        save()
        started = time.perf_counter()
        try:
            result = action()
        except Exception as error:
            item.update(status="failed", seconds=time.perf_counter() - started, error_type=type(error).__name__)
            save()
            raise
        item.update(status="passed", seconds=time.perf_counter() - started)
        save()
        print(f"{name}: passed", flush=True)
        return result

    def upload(local, target):
        # Streaming avoids copying external-drive archives into a container layer.
        command(["hdfs", "dfs", "-put", "-", target], remote=True, input_path=local)

    def hdfs_operations():
        command(["hdfs", "dfs", "-mkdir", hdfs_root], remote=True)
        for name in ("raw", "prepared", "demo"):
            command(["hdfs", "dfs", "-mkdir", hdfs_root + "/" + name], remote=True)
        upload(archive, hdfs_root + "/raw/" + archive.name)
        for name in ("foods.tsv", "food_nutrients.tsv", "manifest.json"):
            upload(prepared / name, hdfs_root + "/prepared/" + name)
        probe = run_dir / "probe.txt"
        probe.write_bytes(b"Track B HDFS integrity round trip\n")
        upload(probe, hdfs_root + "/demo/probe.txt")
        command(["hdfs", "dfs", "-cat", hdfs_root + "/demo/probe.txt"], remote=True, output=run_dir / "probe-cat.txt")
        scratch = "/tmp/fdc_probe_" + run_id
        command(["mkdir", "-m", "700", scratch], remote=True)
        try:
            command(["hdfs", "dfs", "-get", hdfs_root + "/demo/probe.txt", scratch + "/probe.txt"], remote=True)
            command(["cat", scratch + "/probe.txt"], remote=True, output=run_dir / "probe-get.txt")
            if any((run_dir / name).read_bytes() != probe.read_bytes() for name in ("probe-cat.txt", "probe-get.txt")):
                raise ValueError("HDFS round-trip bytes differ")
        finally:
            command(["rm", "-f", scratch + "/probe.txt"], remote=True)
            command(["rmdir", scratch], remote=True)
        command(["hdfs", "dfs", "-rm", "-r", hdfs_root + "/demo"], remote=True)

    def pig_clean():
        command(["pig", "-x", "mapreduce", "-param", "INPUT=" + hdfs_root + "/prepared/food_nutrients.tsv",
                 "-param", "OUTPUT=" + hdfs_root + "/pig_clean", "-f", remote_path(ROOT / "pig/clean_nutrients.pig")], remote=True)
        command(["hdfs", "dfs", "-test", "-e", hdfs_root + "/pig_clean/_SUCCESS"], remote=True)
        count = 0
        with (run_dir / "cluster.log").open("ab") as log:
            process = subprocess.Popen(prefix + ["hdfs", "dfs", "-cat", hdfs_root + "/pig_clean/part-*"],
                                       stdout=subprocess.PIPE, stderr=log, text=True, cwd=ROOT)
            try:
                for line in process.stdout:
                    fields = line.rstrip("\n").split("\t")
                    if len(fields) != 7 or not math.isfinite(float(fields[6])) or float(fields[6]) < 0:
                        raise ValueError("Invalid Pig output row")
                    int(fields[0]); int(fields[3])
                    count += 1
            except Exception:
                process.terminate()
                raise
            finally:
                process.stdout.close()
                code = process.wait()
            if code:
                raise subprocess.CalledProcessError(code, process.args)
        (run_dir / "pig.json").write_text(json.dumps({"output_rows": count, "negative_values": 0}) + "\n")

    save()
    try:
        if before_cluster is None:
            stage("cluster_verification", lambda: command(["bash", remote_path(ROOT / "scripts/verify_cluster.sh")], remote=True))
        if reuse_database:
            stage("mongo_full_import", lambda: verify_existing_import(mongo_database, state['source_sha256'], inventory))
        stage("prepare_all_records", lambda: command([sys.executable, "-m", "fdc", "prepare", "--archive", archive, "--output", prepared]))
        if not reuse_database:
            stage("mongo_full_import", lambda: command([sys.executable, "-m", "fdc", "mongo-import", "--archive", archive, "--database", mongo_database]))
        stage("mongo_analytics_and_profile", lambda: command([sys.executable, "-m", "fdc", "mongo-analytics", "--database", mongo_database,
                                                           "--output", run_dir / "mongo", "--repeats", repeats]))
        if before_cluster is not None:
            stage("cluster_startup", before_cluster)
            stage("cluster_verification", lambda: command(["bash", remote_path(ROOT / "scripts/verify_cluster.sh")], remote=True))
        command(["hdfs", "dfs", "-mkdir", "-p", hdfs_root.rsplit("/", 1)[0]], remote=True)
        stage("hdfs_file_operations", hdfs_operations)
        stage("yarn_streaming", lambda: command(["bash", remote_path(ROOT / "scripts/run_mapreduce.sh"),
                                                  hdfs_root + "/prepared/food_nutrients.tsv", hdfs_root + "/mapreduce", "2"], remote=True))
        command(["hdfs", "dfs", "-cat", hdfs_root + "/mapreduce/part-*"], remote=True, output=run_dir / "mapreduce.tsv")
        stage("pig_cleaning", pig_clean)
        jdbc = os.environ.get("HIVE_JDBC_URL", "jdbc:hive2://localhost:10000/default")
        user = os.environ.get("HIVE_USER", "root" if mode == "docker" else os.environ.get("USER", "hadoop"))
        stage("hive_tables", lambda: command(["beeline", "-u", jdbc, "-n", user,
                                               "--hivevar", "DATABASE=" + database,
                                               "--hivevar", "INPUT=" + hdfs_root + "/pig_clean",
                                               "--hivevar", "RC_OUTPUT=" + hdfs_root + "/hive_rc",
                                               "-f", remote_path(ROOT / "hive/tables.hql")], remote=True))
        stage("hive_benchmark", lambda: command(["python3", "-m", "fdc.hive_benchmark", "--database", database,
                                                  "--manifest", remote_path(prepared / "manifest.json"),
                                                  "--text-path", hdfs_root + "/pig_clean", "--rc-path", hdfs_root + "/hive_rc",
                                                  "--output", remote_path(run_dir / "hive"), "--runs", repeats], remote=True))
        stage("cross_system_reconciliation_and_report", lambda: generate(run_dir))
        state["complete"] = True
        save()
        return {"output": str(run_dir), "computational_checks": "passed", "submission_review_required": True}
    except Exception:
        print(f"Run stopped. Preserved evidence: {run_dir}; inspect run.json and cluster.log before retrying with a new ID.", file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--dataset-kind", required=True, choices=["full-release", "synthetic"])
    parser.add_argument("--cluster-mode", choices=["docker", "client"], default="docker")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(run_part1(args.archive, args.run_id, args.dataset_kind, args.cluster_mode, args.repeats), indent=2))


if __name__ == "__main__":
    main()
