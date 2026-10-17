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

Implemented: [Flask dashboard](TECHNICAL-REFERENCE.md) showing dataset coverage, nutrient summaries and measured
query/storage benchmarks. Validate the local browser demo against the saved development evidence. It should read saved
results or controlled APIs, show data/run provenance, and never display fixture
measurements as full-dataset results. Include architecture, implementation,
functional validation and screenshots in a separate report section.

## Presentation and demonstration

Walk through worker registration, an HDFS operation, a YARN job, a MongoDB
aggregation/index comparison, Pig output, and equivalent Hive queries. Present the
dashboard after the core demo. Keep measured evidence with reproducible commands;
mark pending sections as pending instead of inventing outcomes.

## Where to demonstrate each requirement in the website

Select the correct saved run, then use **Assignment coverage** to open a theme:

| Requirement | Website evidence |
| --- | --- |
| MongoDB ingestion/organization | Theme 1 → collection counts, selected database and recorded parent-import metadata when available. |
| MongoDB indexing | Theme 1 → index definitions and indexed/collection-scan comparisons. |
| All five pipeline operators | Theme 1 → operator explanations and pipeline JSON. |
| `explain("executionStats")` | Theme 1 → equivalent shell query, returned/document/key counts, timings and complete responses. |
| HDFS mkdir/put/get/cat/rm -r | Theme 2 → operation checklist, namespace examples and implementation. |
| Streaming MapReduce on YARN | Theme 2 → job/application IDs, mapper/reducer/launch code and output groups. |
| Pig loading/cleaning/filtering | Theme 3 → input/output/filter counts and Pig Latin. |
| Hive Text and RCFile | Theme 3 → table/load HQL and common Pig input. |
| Identical queries/time/storage | Theme 3 → recorded HQL, equality status, repeated timing medians and size ratio/percentage. |

**Run analysis** also shows live theme checklists. New runs record detailed
activity and source snapshots; older runs remain usable but missing snapshots
are explicitly labelled. A successful subset is not full-data proof. Ingestion
may be verified/reused rather than repeated: present the selected run's scope.

On the three-system master, launch with
`.venv/bin/python -m fdc.dashboard --view-only`. Physical jobs still use the lab
guide's client commands; the UI displays their outputs without Docker controls.
