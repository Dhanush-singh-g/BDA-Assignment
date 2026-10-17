# Validation record

## Verified in this cloud instance

- Python 3.12.14; pinned PyMongo 4.10.1 and dnspython 2.7.0 installed in `.venv`.
- MongoDB 7.0.16 runs in Docker and responds to an actual database ping.
- Thirteen automated tests passed with MongoDB integration enabled; no tests skipped.
- Tests verify complete fixture ingestion, preservation of an additional CSV,
  long/multiline text, refusal to overwrite an existing database, all analytical
  pipelines and executionStats index/collection-scan behavior.
- Preparation tests reconcile seven nutrient rows into four prepared rows and
  three explicit rejects. Local mapper/reducer subprocesses verify counts and
  means, negative-value filtering and malformed-input failure.
- Hive benchmark result comparison detects changed groups/counts and empty output.
- The development cluster has two registered DataNodes and two RUNNING
  NodeManagers. A YARN Pi job and the Python Streaming nutrient summary passed.
- JobHistory task-attempt records for `job_1792176334803_0002` confirm Streaming
  work executed on both `worker1` and `worker2`. They are containers on one host.
- Pig cleaning executed on YARN and produced the expected three nonnegative
  observations from the four prepared fixture observations.
- HDFS mkdir/put/cat/get/delete and byte-for-byte probe retrieval passed.
- Services restarted with retained HDFS/metastore state. Verification now waits
  for NameNode safe mode to clear before submitting the sample job.
- Hive Text/RCFile loading and both analytical queries executed on YARN. The
  final benchmark CLI completed eight fixture executions (four warmup and four
  measured), with identical groups/counts/amounts between the formats. Every
  execution aggregated the expected three clean observations.
- Logical and replication-adjusted storage sizes were obtained through Hadoop's
  ContentSummary API. The original shell-output parser failed on Hadoop 2;
  after replacing it, the affected benchmark command was rerun successfully.
- The earlier full smoke invocation reached storage reporting after successful
  HDFS/Streaming/Pig/Hive checks; the final validation reran the affected Hive
  benchmark rather than repeating those already verified stages.
- Evidence: `data/smoke_1792176393243843384/cluster.log`,
  `task-placement.json`, and `hive_verified/benchmark.json` under that directory.
  These are retained local outputs, excluded from Git.

## Pending

- Complete USDA release download: cloud proxy rejects the official host with
  HTTP 403 despite the hostname being present in saved environment configuration.
  No source records from the actual dataset have been processed yet.
- Full-dataset reconciliation, scale/resource checks and performance measurements.
- Physical college-cluster deployment, node inventory, task placement and final
  distributed evidence.
- Track B dashboard extension and final report/presentation.

Synthetic fixtures are correctness tests, not dataset samples or submission
benchmarks. This file records capabilities, not a claim that the project or
assignment is complete.

## Integrated Part 1 driver and report

`python -m fdc.part1` completed all ten stages in
`results/validation_1792209548774080999/` with the dataset explicitly classified as
synthetic and the deployment classified as containers on one host. This run
included a source record with an unknown nutrient reference. All eight source
nutrient records were retained in MongoDB; four were prepared and four explicitly
rejected, with one prepared negative observation subsequently excluded.

MongoDB, YARN Streaming and every Hive result reconcile against an independent
scan of the prepared TSV: three clean observations in two analytical groups.
Pig output counts agree. Eight Hive executions completed, including four warmups
and four measured executions. The generated `PART1_REPORT.md` and
`reconciliation.json` were checked; relative prepared-data paths and standalone
report regeneration were also exercised.

The new tests reject mismatched source fingerprints, missing groups, incorrect
counts, invalid timings and unsafe run IDs. The archive inspection utility was
tested with a real ZIP and full CRC verification. The final report keeps all
fixture/container classifications and does not declare submission completion.
