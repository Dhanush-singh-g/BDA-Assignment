# Optional technical reference

For the normal demo use [LAPTOP-DEMO.md](LAPTOP-DEMO.md). For college deployment
use [THREE-SYSTEM-RUN.md](THREE-SYSTEM-RUN.md). This page keeps the extra commands
that used to be scattered across several guides.

## Fresh laptop setup

Use Ubuntu 24.04/WSL2, Python 3.12+, GnuPG, and Linux Docker Engine with Compose
v2. Docker Desktop with Ubuntu WSL integration is another option; check that your
terminal and Desktop use the intended Docker engine. Do not run two engines
assuming they share containers. The tested stack is amd64, Java 8, Hadoop 2.10.2,
Pig 0.17.0, Hive 2.3.9 and MongoDB 7.0.16. Keep these legacy services private.

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv gnupg
git clone https://github.com/Dhanush-singh-g/BDA-Assignment.git
cd BDA-Assignment
bash scripts/install.sh
```

The installer creates `.venv`, installs requirements, verifies Apache downloads,
and prepares shared tools in `data/tools/`. It does not start the services. It
exports Java from a pinned image; no custom image build is needed. Pig's historic
release signature was made while its now-expired signing key was valid. Do not
disable checksum, signature or TLS verification to bypass an installation error.

Check RAM and actual Windows drive free space before starting. WSL virtual-disk
capacity is not physical free space. The three containers each have a 4 GiB
limit; actual usage varies, and MongoDB should be stopped during laptop cluster
tests. A 10 GiB WSL limit worked for the user's small test, not a guaranteed
full-data configuration.

## Service checks and troubleshooting

```bash
bash scripts/start_mongo.sh
FDC_MONGO_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
# Stop MongoDB before the laptop Hadoop test:
docker stop fdc-mongo-dev
docker compose -f infra/compose.yaml up -d --no-build
# Wait for startup before checking:
docker compose -f infra/compose.yaml exec master bash scripts/verify_cluster.sh
docker compose -f infra/compose.yaml exec master \
  beeline -u jdbc:hive2://localhost:10000/default -n root -e 'SELECT 1;'
```

Connection refused immediately after startup may mean services are still
initializing. Check logs instead of reinstalling or formatting:

```bash
docker compose -f infra/compose.yaml logs --tail 80 master worker1 worker2
docker stats --no-stream
free -h
```

The tools mount read-only at `/opt`; the checkout mounts at `/project`.
Persistent Docker-cluster state is in `data/cluster/`. Source XML changes are not
automatically copied to the generated `data/tools/` configs. Investigate changes
before refreshing those files/restarting services. Never delete storage blindly.

## Full archive and separate MongoDB commands

The laptop ZIP path is `/mnt/c/Users/dhanu/Downloads/FoodData_Central_csv_2024-10-31.zip`.
Keep it intact. Commands below use a placeholder; substitute the actual ZIP path.

```bash
.venv/bin/python -m fdc.inspect_archive --archive /path/to/full.zip --verify
.venv/bin/python -m fdc prepare --archive /path/to/full.zip --output data/prepared/NEW_NAME
.venv/bin/python -m fdc mongo-import --archive /path/to/full.zip --database fdc_NEW_NAME
.venv/bin/python -m fdc mongo-analytics --database fdc_NEW_NAME --output results/mongo/NEW_NAME --repeats 5
```

Each destination must be new. Do not rerun these just to view existing results.
The complete driver in the college guide creates its own fresh import and outputs.
The downloader `python -m fdc download` is optional; the cloud previously received
HTTP 403 from USDA. Your browser download already passed CRC/fingerprint checks.

MongoDB defaults to `mongodb://127.0.0.1:27017`; override `MONGODB_URI` securely if
needed. It stores every CSV as `raw_<table>` documents with source strings and
synthetic row IDs preserving duplicate rows. A metadata record marks completion.
SQLite is a local `join.sqlite` helper, not a server. Categories retain numeric
IDs or labels as text; missing references/nonfinite amounts are rejected with
reasons. Finite negatives remain prepared, then are filtered from nutrient sums.

## Re-create/export the development subset only if needed

These are not steps required every time you demonstrate. Use new names if the
outputs already exist. Run with Hadoop stopped and MongoDB started:

```bash
.venv/bin/python -m fdc.dev_subset --source fdc_home202410 --destination fdc_dev10k_01 --foods 10000
.venv/bin/python -m fdc mongo-analytics --database fdc_dev10k_01 --output results/mongo/dev10k_01 --repeats 5
.venv/bin/python -m fdc.export_dev --database fdc_dev10k_01 --output data/dev10k_export_01
```

Stop MongoDB, start Hadoop and use the laptop guide's real-subset test. It checks
MongoDB, MapReduce and all Hive result groups against independently calculated
counts/sums/means. The export includes linked records rather than independent
limits on unrelated CSVs. The tiny synthetic alternative is
`.venv/bin/python tests/cluster_smoke.py`; it produces no USDA benchmark claims.

## Which result files matter?

| File | Meaning |
| --- | --- |
| `prepared/manifest.json` | Prepared counts, rejects, columns and source fingerprint. |
| `prepared/rejected.jsonl` | Rejected source rows and reasons. |
| `mongo/profile.json` | Query plans/timings and input scope. |
| `mongo/*.jsonl` | Food-type counts, nutrient summaries and overview. |
| `mapreduce.tsv` | Group counts, sums and means. |
| `hive/benchmark.json` | Completed queries, storage, timings and input manifest. |
| `hive/progress.json` | Benchmark progress while still running. |
| `cluster.log` | Commands, job output and diagnostics. |
| `SUCCESS.json` | Successful subset integration; not full-data acceptance. |
| `run.json` | Full driver's stage outcomes and completion flag. |
| `reconciliation.json`, `PART1_REPORT.md` | Full driver's checked results and generated report. |

Hive's development test uses one warmup and one measured execution per query/
format pair (eight executions). The full driver defaults to five measured
repetitions. Medians exclude warmups; elapsed time includes Beeline/job startup,
with no cache flush. Logical bytes and HDFS replication-adjusted bytes are
separate; the storage measurement uses Hadoop's ContentSummary API.

## Dashboard details

Run `.venv/bin/python -m fdc.dashboard` locally; use `--port 5001` if the default
port is busy. It binds to loopback with debug off and reads saved files without
live services. It discovers `data/realdev_*/SUCCESS.json` and `results/*/run.json`.
Select a run, filter nutrients by ID/type/unit, and inspect plans/timings/storage.
Unknown runs return 404; malformed files show an error rather than made-up data.
The JSON endpoint is `/api/evidence?run=<discovered-run>`.

Dashboard-only tests need no database:

```bash
.venv/bin/python -m unittest discover -s tests -p test_dashboard.py -v
```

Back up generated evidence separately; it is ignored by Git. SHA-256 identifies
the local artifact, not a publisher signature. Keep subset/full-run labels and
capture actual worker task placement for the final physical deployment.

## Local job controls

The dashboard's optional controls execute fixed laptop workflows; the saved
results view remains usable without services. `Run analysis → Start analysis` with a subset size creates a
new linked subset from an existing full MongoDB import, runs profiles, exports,
switches to Hadoop and reconciles MapReduce/Pig/Hive. `Reuse prepared data or manage services → Run distributed checks`
requires matching saved MongoDB scope, selection and table counts. Actions also
start MongoDB (stop Hadoop), start Hadoop (stop MongoDB), or stop project services.

The existing install must include `data/tools/READY.json`, `.venv`, Docker
permissions and the full source database. Installation and full ZIP ingestion
are not automated by these buttons. Processes use the dashboard's Ubuntu account;
no sudo password is requested by the UI. Docker-group access is powerful, so the
server stays loopback-only, debug off, with same-origin request-token checks for
mutations. Do not expose the dashboard to a LAN or public internet.

A detached worker holds a filesystem lock across dashboard reloads. Job metadata
and logs persist under `data/ui_jobs/<id>/`. The API under `/api/control/jobs`
returns recent job states; a second action returns 409 while the lock is held.
No arbitrary command or deletion endpoint exists. Readiness waits up to five
minutes. Failed stages preserve logs/partial outputs and stop subsequent stages.
Worker interruption is shown separately from success. After an interrupted
worker, inspect logs and use **Stop project services** to clear the recovery
block before launching another job. Closing the dashboard does
not cancel a job; keep WSL and the laptop awake. There is no force-cancel button.
Do not launch manual jobs at the same time or retry an interrupted job without
checking for still-running database/YARN work. Disk checks see the Linux virtual
filesystem; also check actual Windows drive free space. No free-space check can
guarantee a larger run will fit.

The UI source is fixed to `fdc_home202410` (including server-side validation).
Custom subset limits are 1–100,000 foods. **Entire dataset** uses the full Part 1
pipeline with the existing import verified against the ZIP's fingerprint,
complete CSV inventory and actual collection counts. The original ZIP is located
at `data/raw/FoodData_Central_csv_2024-10-31.zip` first, then the known Windows
Downloads path. No arbitrary archive path/database is accepted by the UI API.
Full mode rebuilds the derived `foods` collection but leaves raw imports intact.
It runs MongoDB first, switches to Hadoop, creates new Hive/HDFS/results namespaces
and generates the full report. The driver records `mongo_input_mode` as
`verified-existing-import`; it does not claim a new ingestion happened. Five
measured repetitions plus warmups produce 24 Hive executions in this mode.
Full-data progress is read from the driver's `run.json` and Hive progress files.
The fixed database/ZIP must already exist; installation and import remain separate.
