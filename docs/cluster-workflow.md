# Distributed workflow

Run from the repository root on a configured cluster client with Python 3, Hadoop,
Pig and Beeline in `PATH`. Use the same commands inside the development master via
`docker compose -f infra/compose.yaml exec master bash`. Ensure MongoDB import
and HDFS preparation refer to the same archive SHA-256.

## Verify services before analytics

```bash
bash scripts/verify_cluster.sh
```

Save its output and the successful YARN application ID. It requires at least two
live DataNodes, two running NodeManagers and a successful YARN Pi job. Record the
three physical machine identities separately; registration alone cannot prove
physical separation or that tasks ran on both workers.

## HDFS operations and MapReduce

Use a fresh run name. This example uploads the whole ZIP as provenance and the
normalized TSVs as the actual streaming-job input:

```bash
bash scripts/hdfs_demo.sh \
  data/raw/FoodData_Central_csv_2024-10-31.zip \
  data/prepared/202410 /user/root/fdc/full01
bash scripts/run_mapreduce.sh \
  /user/root/fdc/full01/prepared/food_nutrients.tsv \
  /user/root/fdc/full01/mapreduce 2
hdfs dfs -cat '/user/root/fdc/full01/mapreduce/part-*'
hdfs dfs -get /user/root/fdc/full01/mapreduce results/mapreduce-full01
```

Replace `root` with the actual lab user. Create local `results/` before `-get`.
The HDFS demo creates and removes only a dedicated probe directory; it never
deletes the full dataset. The job emits `type|nutrient_id`, observation count,
total amount and mean amount. The mapper counts negative amounts excluded from
analysis. The reducer uses `math.fsum` for stable accumulation. Save Hadoop
counters and `_SUCCESS`, and confirm task attempts in YARN. Multiple reducers
produce separate output partitions; their concatenation is not globally sorted.

## Pig transformation

```bash
pig -x mapreduce \
  -param INPUT=/user/root/fdc/full01/prepared/food_nutrients.tsv \
  -param OUTPUT=/user/root/fdc/full01/pig_clean \
  -f pig/clean_nutrients.pig
hdfs dfs -test -e /user/root/fdc/full01/pig_clean/_SUCCESS
```

Pig consumes the full normalized fact table derived from the raw structured CSVs.
The normalization step handles quoted commas/multiline fields that plain
PigStorage cannot parse safely. Pig then applies typed field validation and the
nonnegative-amount filter. Retain Pig's input/output counters and reconcile them
against the preparation manifest and mapper filter counters.

## Hive Text and RCFile

HiveServer2 and its metastore must be running. Default local development JDBC URL:
`jdbc:hive2://localhost:10000/default`. Configure authentication through your lab's
supported mechanism; do not put passwords in Git or saved commands.

```bash
beeline -u jdbc:hive2://localhost:10000/default -n root \
  --hivevar DATABASE=fdc_202410 \
  --hivevar INPUT=/user/root/fdc/full01/pig_clean \
  --hivevar RC_OUTPUT=/user/root/fdc/full01/hive_rc \
  -f hive/tables.hql
python3 -m fdc.hive_benchmark \
  --manifest data/prepared/202410/manifest.json \
  --text-path /user/root/fdc/full01/pig_clean \
  --rc-path /user/root/fdc/full01/hive_rc \
  --output results/hive/full01 --runs 5
```

Tables are external. RCFile output uses gzip compression; the Text input is
uncompressed Pig output. Therefore the storage comparison measures **format plus
configured compression**, not the format alone. Both tables must have exactly the
same rows. Creation fails if tables already exist to avoid silently benchmarking
stale locations. Inspect existing tables before any explicit cleanup; never drop
another group's work. Use a dedicated metastore/database for this project.

The benchmark runs an overall nutrient summary and a protein-only summary. For
each query/table pair it runs one warmup, then five measured executions in a
reproducible shuffled order. It checks each query's results across both tables,
using exact group/count equality and a documented floating-point tolerance. It
saves TSV outputs, stderr, elapsed time, query text and HDFS logical/replicated
bytes. Storage uses Hadoop's ContentSummary API through a small Java helper
(a JDK is required), avoiding differences in Hadoop shell output. Progress is
saved after every query; only `benchmark.json` with `complete=true` is a complete run.
Timings include client startup; use Hive/YARN job logs for engine-only
timings. Do not claim cold-cache behavior. Run on an otherwise idle cluster and
record block size, replication, engine, resource settings, versions and run order.

Do not infer a format's superiority before measuring. Calculate median and spread
from measured runs only (exclude `warmup=true`), and report logical size separately
from replicated disk consumption.
