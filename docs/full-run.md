# Complete Track B Part 1 execution

This is the workflow for the **entire** October 2024 USDA CSV package. Part 1 is
not submission-complete until full-data results and acceptable college-cluster
evidence exist. The team has confirmed that three college systems can be arranged.

The source-only handoff bundle is `dist/BDA-Assignment-Part1-source.zip`. Extract
its `BDA-Assignment` folder onto the machine used for execution. It intentionally
contains no dataset, database, credentials, virtual environment or generated
benchmark results; install the documented dependencies there before running.

## 1. Download and size the actual archive

Use the official URL:

https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_csv_2024-10-31.zip

Keep the ZIP intact. This cloud's proxy still rejects the official host, despite
the saved allowlist entry. A laptop download is a separate file: sharing a local
file path in chat does not transfer it to the cloud. Copy the ZIP to the machine
that will execute ingestion (normally the college master/client), or run the
project where the ZIP is available.

From the project root, inspect the real file before allocating storage:

```bash
python3 -m fdc.inspect_archive \
  --archive /path/to/FoodData_Central_csv_2024-10-31.zip --verify
```

This reports actual ZIP size, uncompressed CSV sizes, table inventory, source
SHA-256, free disk and optional full CRC validation. It does not extract the
archive. It uses only Python's standard library. The exact release size has not
yet been measured here; do not replace it with fixture sizes.

Budget for every retained representation: ZIP, MongoDB raw/derived documents and
indexes, prepared TSVs, SQLite dimensions, replicated HDFS input and RCFile output.
For physical systems, use each node's actual disk inventory. Container workers
share one physical disk, so their capacity reports must not be summed.

## 2. Configure the chosen cluster

For the final submission, follow [college-cluster.md](college-cluster.md) on one
master and two separate workers. Record hostnames/IPs, OS, CPU/RAM/disk, Java and
Hadoop versions, SSH configuration, worker files, DataNode/NodeManager registration
and actual task placement. Do not format an existing NameNode.

For development only, use [development-cluster.md](development-cluster.md).
Containers on one host do not establish the required physical deployment.

Native execution requires Python dependencies from `requirements.txt`, compatible
Java/Hadoop/Pig/Hive clients and access to MongoDB and HiveServer2. Configure
`MONGODB_URI`, `HIVE_JDBC_URL` and `HIVE_USER` through the supported runtime/secure
settings. Never put credential values into source files or the report.

## 3. Execute all three themes

On the configured college master/client, from the project root:

```bash
.venv/bin/python -m fdc.part1 \
  --archive /path/to/FoodData_Central_csv_2024-10-31.zip \
  --run-id full202410_01 --dataset-kind full-release \
  --cluster-mode client --repeats 5
```

For the Docker development cluster, change `--cluster-mode client` to
`--cluster-mode docker`. Start the services using the documented setup commands
first. Use Linux/WSL2 for the supplied shell-based development instructions;
native Windows deployment has not been validated.

The driver uses a new MongoDB/Hive database and new HDFS namespace per run. It:

1. Checks workers, safe mode and a sample distributed YARN job.
2. Scans all source food/nutrient records and imports every CSV into MongoDB.
3. Executes all MongoDB pipelines and repeated collection/index-scan profiling.
4. Uploads the original ZIP and prepared TSVs, verifies HDFS cat/get bytes, and
   deletes only its own temporary HDFS demo directory.
5. Runs Python Streaming on YARN, then Pig cleaning on MapReduce.
6. Loads Text/RCFile tables and benchmarks two identical query pairs, with one
   warmup and five measured runs per query/table pair by default.
7. Independently scans the prepared TSV and reconciles counts, sums and means
   against MongoDB, MapReduce and every saved Hive result.
8. Generates the report and retains raw evidence.

There is no production row limit or sampling parameter. `--dataset-kind` records
the caller's dataset classification; it is not independent proof of USDA origin.
The full downloaded release and its fingerprint still need provenance review.
The separate `synthetic` classification is only for developer integration tests.

Results appear in `results/<run-id>/`:

| File | Evidence |
| --- | --- |
| `run.json` | Dataset classification/hash, ZIP inventory, client inventory and timed stage outcomes |
| `cluster.log` | Commands, worker checks, HDFS operations, job IDs/counters and diagnostics |
| `mongo/` | All analytical outputs and full executionStats profiles |
| `mapreduce.tsv` | All nutrient-group results |
| `pig.json` | Output-row and filter validation |
| `hive/` | Every query result/log, warmup/measured timings and logical/replicated sizes |
| `reconciliation.json` | Cross-system counts, sums/means, timing summaries and storage ratio |
| `PART1_REPORT.md` | Report generated solely from the run's evidence |

The driver streams uploads, so an archive on another drive need not be copied
into a Docker writable layer. Prepared data and results currently live under the
project directory; place that checkout on adequately sized storage before a full
run. A failed stage stops the driver and preserves diagnostics. Existing run IDs,
databases and HDFS destinations are not silently overwritten or deleted. Inspect
the failure before selecting a new run ID; do not rerun large imports blindly.

## 4. Final submission review

The generated report covers computational evidence. Complete team information,
data interpretation, provenance, physical-node inventory, configuration snapshots,
screenshots where required and the demonstration. A successful container run
remains classified as a container run. A native client run remains physically
unverified until its machine evidence is attached. The report never converts a
synthetic run into full-release results or declares faculty approval automatically.

Part 2's Flask dashboard remains separate from these Part 1 deliverables.
