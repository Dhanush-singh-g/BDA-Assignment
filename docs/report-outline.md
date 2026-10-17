# Track B report and demo evidence

## Part 1 — three core themes (15 marks)

1. Dataset provenance: official release URL/date, local SHA-256, archive inventory,
   CSV row counts, preparation rejects, and rationale for the selected analyses.
   Explicitly state that the complete package was ingested without sampling.
2. Cluster: one master and at least two workers on separate systems, hostnames,
   OS/CPU/RAM/disk inventory, network topology, Java/Hadoop/Pig/Hive/MongoDB
   versions, SSH setup, HDFS replication and YARN resource configuration.
3. Verification: live DataNodes, running NodeManagers, smoke-job ID and success,
   actual task placement, and HDFS round-trip integrity evidence.
4. MongoDB: raw collections/counts, derived schema, index definitions, all five
   required operators, query results, `executionStats`, repeated-run methodology
   and index size/performance discussion.
5. MapReduce: algorithm, key/value design, mapper/reducer counts, full-input
   counters, negative-value handling, job IDs, representative results and checks.
6. Pig: complete script, quoted CSV normalization rationale, cleaning rules,
   input/output reconciliation and distributed job evidence.
7. Hive: Text/RCFile DDL, identical input row counts, query text, compression
   codec, result equality, individual warmup/measured timings, summary statistics,
   logical/replicated sizes, and limitations of cache/client-startup effects.

## Part 2 — practical extension (10 marks)

Planned: Flask dashboard showing dataset coverage, nutrient summaries and measured
query/storage benchmarks. Build after the core workflows. It should read saved
results or controlled APIs, show data/run provenance, and never display fixture
measurements as full-dataset results. Include architecture, implementation,
functional validation and screenshots in a separate report section.

## Presentation and demonstration

Walk through worker registration, an HDFS operation, a YARN job, a MongoDB
aggregation/index comparison, Pig output, and equivalent Hive queries. Present the
dashboard after the core demo. Keep measured evidence with reproducible commands;
mark pending sections as pending instead of inventing outcomes.
