# USDA FoodData Central — Track B

BCS714D Big Data Analytics, 2026–2027. This repository develops the three mandatory
themes first; the Flask dashboard is the planned 10-mark extension after these
workflows are validated. The final report must cover Parts 1 and 2 separately.

**Dataset:** the complete [October 31, 2024 CSV package](https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_csv_2024-10-31.zip).
[USDA dataset documentation](https://fdc.nal.usda.gov/download-datasets/).
Production commands have no sampling option or row limit. Every CSV table is
preserved in MongoDB, including tables not used by a particular analysis.

## Current evidence

- Python tests pass against a real MongoDB 7.0.16 service using synthetic fixtures.
- Preparation, rejected-record accounting, multiline CSV handling, aggregation
  operators, index plans, and local MapReduce calculations are tested.
- The USDA host currently returns a cloud proxy HTTP 403. The complete archive
  has **not** been downloaded or processed in this environment.
- HDFS operations, YARN Streaming, Pig cleaning and Hive Text/RCFile queries passed
  on a master/two-worker development cluster using synthetic fixtures. Streaming
  task attempts ran on both workers. See [validation](docs/validation.md).
- No full-dataset or college-cluster benchmark results are claimed.

## Install and develop

**Windows laptop:** follow [the WSL2 home-testing guide](docs/windows-home.md)
to clone, verify the full downloaded ZIP and run all three themes locally.

Use Python 3.10 or later. These commands run from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
bash scripts/start_mongo.sh
FDC_MONGO_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
```

The MongoDB script requires Docker, listens only on loopback, and persists data
in ignored `data/mongo/`. The integration test creates and removes only its own
random `fdc_test_*` database. Tests without MongoDB can be run by omitting
`FDC_MONGO_TESTS=1`; the integration test will then be explicitly skipped.

## Obtain and prepare the entire release

```bash
.venv/bin/python -m fdc download
.venv/bin/python -m fdc prepare \
  --archive data/raw/FoodData_Central_csv_2024-10-31.zip \
  --output data/prepared/202410
```

If the cloud cannot reach USDA, download the exact ZIP on a network that can and
place it at the archive path above. The preparation and ingestion commands read
the ZIP directly; there is no need to extract the entire package. The downloader
validates ZIP CRCs and records a SHA-256 fingerprint. This fingerprint identifies
the local artifact; it is not a USDA-published signature.

Preparation scans all `food`, `nutrient`, and `food_nutrient` rows, joining through
an indexed SQLite database on disk. Outputs are headerless UTF-8 TSV:

| Output | Columns / purpose |
| --- | --- |
| `foods.tsv` | food ID, type, description, nullable category ID |
| `food_nutrients.tsv` | food ID, type, nullable category ID, nutrient ID, name, unit, amount |
| `rejected.jsonl` | Every unusable nutrient record, its source ordinal and reason |
| `manifest.json` | Source fingerprint, column definitions and reconciliation counts |
| `join.sqlite` | Disk-backed dimension index; retained for inspection |

Whitespace in analytical TSV strings is collapsed to keep one record per line.
MongoDB retains original CSV strings. Empty category IDs stay null; missing
nutrient amounts are not treated as zero. Nonfinite amounts and missing references
are recorded as rejects. Negative finite amounts are retained during preparation
and explicitly filtered by MapReduce and Pig. Rejected records remain available
in the raw ZIP and raw MongoDB collection. A preparation directory is complete
only when its `manifest.json` exists. Failed or existing destinations are never
silently overwritten.

Check free disk space before a full run: space is needed for the compressed ZIP,
normalized outputs, SQLite indexes, MongoDB data/indexes and replicated HDFS
copies. The archive's expansion and actual row counts are not yet measured here;
do not assume that a laptop or this cloud disk can hold every representation.

## Theme 1 — MongoDB

```bash
.venv/bin/python -m fdc mongo-import \
  --archive data/raw/FoodData_Central_csv_2024-10-31.zip \
  --database fdc_202410
.venv/bin/python -m fdc mongo-analytics \
  --database fdc_202410 --output results/mongo/full-01 --repeats 5
```

Set `MONGODB_URI` in your shell or secure runtime configuration when using another
MongoDB deployment; never commit credentials. A new, empty dedicated database is
required for import. A failed import is marked incomplete; choose a new database
or inspect and explicitly remove your failed development database before retrying.
Batch size controls memory use, not dataset size. All raw field values are strings;
the importer adds a synthetic row-ordinal `_id` so even duplicate source rows survive.

The derived `foods` collection embeds typed nutrient observations using an indexed
`$lookup`. It can be rebuilt from raw collections. The analytical pipelines use
`$match`, `$group`, `$project`, `$unwind`, and `$facet`. Outputs include food counts
by type, nutrient means by type, and a faceted coverage overview. Nutrient amounts
must only be compared within the same nutrient ID/unit; counts refer to observations,
not necessarily distinct foods. USDA table definitions must guide interpretation.

The profiler alternates the identical food-ID query between a forced collection
scan (`$natural`) and the `idx_fdc_id` index. It saves complete
`explain(..., verbosity="executionStats")` responses, including returned rows,
documents/keys examined, execution time, server version and source fingerprint.
These are warmed development measurements, not cold-cache or final cluster results.

## Themes 2 and 3 — distributed execution

See [development cluster](docs/development-cluster.md) for the local Docker
environment and [college deployment](docs/college-cluster.md) for physical systems.
The scripts in [cluster workflow](docs/cluster-workflow.md) cover:

1. HDFS/YARN worker registration and a sample MapReduce smoke job.
2. Full archive upload, prepared-table upload, HDFS get/cat and safe demo deletion.
3. Python Streaming nutrient summaries on YARN.
4. Pig cleaning on the MapReduce backend.
5. Hive Text/RCFile tables and repeated, identical analytical queries.

Three containers on one laptop/cloud host are a development environment. They do
not demonstrate the assignment's requirement for at least three separate lab
systems. Preserve physical-node inventory and task-placement evidence for final
submission. No local result should be relabeled as a college-cluster result.

## Submission

For the integrated full-data execution and generated report, follow
[Complete Part 1 execution](docs/full-run.md). The driver reconciles independent
prepared-data totals with MongoDB, MapReduce and each Hive execution before
generating the report. Actual USDA processing and physical lab evidence remain
pending until the archive and three college systems are available.

[Track B report outline](docs/report-outline.md) lists the required evidence.
Keep generated data, credentials, database files and run outputs outside Git.
Archive final measured results separately with source fingerprints and machine
inventory. Do not fill report tables with invented times or compression ratios.
