# Validation record

## Earlier cloud fixture validation

- Python 3.12.14; pinned PyMongo 4.10.1 and dnspython 2.7.0 installed in `.venv`.
- MongoDB 7.0.16 runs in Docker and responds to an actual database ping.
- At that stage, 13 automated tests passed with MongoDB integration enabled;
  no tests skipped. Later dashboard implementation validation reached 18 tests.
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

## Current status: user laptop and dashboard

The following laptop outcomes were reported through terminal output in this chat;
they are separate from cloud fixture validation:

- Full ZIP CRC verified; SHA-256
  `85b6268117a8f6b8032d67a06ccd51ed1287a53ebaaeb0b3e262165e2820cb9f`.
- Full preparation: 2,063,876 foods, 477 nutrient definitions and 26,848,323
  nutrient records, with zero preparation rejects.
- Full MongoDB ingestion: all 34 CSVs completed. Full-data analytical
  materialization was interrupted; it is not a completed benchmark.
- Linked 10,000-food subset analytics passed: 9,994 branded and 6 experimental
  foods; both profile plans returned the same row. Collection scans examined
  10,000 documents, indexed scans one document/one key.
- Real-subset cluster integration passed in
  `data/realdev_1792236286088591242/`: HDFS/YARN, MapReduce, Pig and Hive outputs
  checked against independent totals and matching saved MongoDB summaries.
- Dashboard opened on the laptop. Its implementation passed 18 automated tests
  in the cloud (including MongoDB integration), actual saved-evidence rendering
  and HTML/JSON requests to a running local HTTP server.

## Still pending

- Full-data analytics/reconciliation and repeated final performance measurements.
- Three physical college systems, inventory and task placement on both workers.
- Final Part 1/Part 2 report, screenshots and presentation evidence.

Synthetic fixtures and linked subsets are development evidence, not full-release
submission benchmarks. Generated logs/results are excluded from Git; back them up.

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

## Dashboard job controls (cloud implementation validation)

- Added fixed background laptop workflows for new linked subsets, existing-export
  distributed checks, and project service switching/stopping.
- A real dashboard job POST launched a detached worker on a **two-food synthetic
  fixture** (10,000 was a selection ceiling, not a 10,000-row benchmark). It passed
  MongoDB creation/profiling/export, automatic service switching/readiness, HDFS,
  YARN, MapReduce, Pig, all eight Hive executions and result reconciliation.
  Evidence: `data/realdev_1792246691225772507/`; job metadata/logs live under
  `data/ui_jobs/8271b7f4da284381ab965cbb07d1c50a/` and are excluded from Git.
- Chromium checks verified desktop/mobile controls, stage/log polling, no
  JavaScript errors, no mobile horizontal overflow, and disabled concurrent-job
  buttons. A Flask restart retained the worker and its process lock.
- All 26 automated tests passed with MongoDB integration enabled.
- Browser controls opened the completed evidence and successfully stopped the
  project services using a real button-triggered background action.
- Local request-token/origin checks, fixed-action input validation, failure state
  preservation, interrupted-worker recovery blocking, bounded logs and export
  provenance matching have automated coverage.

The existing 50,000-food run was performed on the user's laptop using Terminal
commands; the new controls still need that user's laptop check. No 100,000-food
or full-data performance claim is made by these UI tests.

## Simplified UI and existing-import full mode

- The source database is fixed to `fdc_home202410`; attempts to supply another
  database through the UI API are rejected.
- Separate **View results** and **Run analysis** tabs, custom subsets (1–100,000
  foods), and **Entire dataset** selection passed desktop/mobile Chromium checks.
  Browser POSTs for the full/custom choices were intercepted to verify payloads
  without launching the real release. No JavaScript errors or mobile overflow.
- All 32 automated tests passed with MongoDB integration enabled, including ZIP
  discovery, fixed-source enforcement, full-worker dispatch, input hash/count
  mismatch rejection, and reading full-run stage/log/Hive progress.
- The existing-import full Part 1 path completed on a **two-food synthetic ZIP**
  in `results/reuse_ui_1792247705071815010/`. Raw import verification, preparation,
  MongoDB analytics, HDFS/YARN, Pig, eight Hive executions (one measured run per
  query/format for this test), reconciliation and report all passed. The report
  records reuse of an existing import and retains synthetic/container scope.
- UI full mode uses five measured runs per query/format (24 executions including
  warmups), an original ZIP, the fixed full import and serialized service switching.
  This implementation validation is not a successful full USDA/laptop run.

## Requirement-by-requirement theme reporting

- All 40 tests passed with MongoDB integration enabled. New coverage checks
  timeline failures, legacy/missing evidence, live theme state, source-import
  snapshots, index/pipeline capture, native viewing-only mode and correct numeric
  rendering of index keys.
- The theme-aware detached UI job `655cfc79b3b04847a4b139f75b87a078` completed on a
  **two-food synthetic fixture**. Evidence:
  `data/realdev_1792250146887196533/`. Four prepared observations became three
  nonnegative observations; MapReduce, Pig and all eight Hive executions passed
  independent reconciliation. All six distributed activity stages were recorded.
- Real MongoDB checks captured input/parent collection counts, index definitions,
  exact aggregation pipelines, executionStats and four successful Theme 1 stages.
  Parent-import metadata capture was additionally checked on the linked fixture.
- Chromium checks verified all five operators, all five HDFS operation examples,
  mapper/reducer/Pig/HQL evidence, three live theme cards, completed theme status,
  actual recorded Hadoop version, desktop/mobile layout and no JavaScript errors.
- `--view-only` retains theme/result viewing while hiding controls and returning
  403 for control API requests. It does not initialize a job-manager directory.
  The college guide now uses this mode; its physical cluster client commands
  remain unchanged. Physical deployment still awaits the actual lab systems.

Older runs remain readable. Missing source/index snapshots are labelled, not
invented. Current explanatory code is distinguished from archived run code.
Logical Text/RCFile size comparisons show either savings or additional space;
RCFile is not automatically described as better. Native and container topology
remain separately identified. This UI work does not complete final full-data or
physical-cluster submission evidence.

## Interrupted-job recovery controls

- A visible **Stop services and recover** action now appears before a new
  analysis can be submitted. Recovery detection includes older interrupted jobs
  outside the 20-item recent-history list. A live worker's lock still prevents
  service recovery from interrupting active work.
- Successful service stopping clears the interruption block while preserving
  input files and prior job logs; a failed stop leaves the block in place.
  These paths have API/worker regression coverage with service calls mocked.
- The Python suite ran 50 tests: 49 passed and the optional MongoDB integration
  test was skipped. Chromium checks passed, including the visible recovery
  action, disabled analysis controls during recovery, and re-enabled controls
  after success. The browser fixture now fails explicitly if Flask cannot start.

## Current-run status and live operations

- All **46 Python tests passed**, including MongoDB integration. New checks use
  an actual child process to verify its PID is recorded before completion,
  failures/timeouts retain failure status, captured errors keep diagnostics,
  full runs expose inner MongoDB operations, and active Hive log tails are read.
- Chromium regression checks cover fresh Ready state with saved successes,
  explicit history, clearing old logs, starting a new run, live query/output,
  reconnecting to an active job, returning to Ready after a completed-page reload,
  and mobile layout. Run `node tests/dashboard_progress_browser.cjs` from the
  repository with Node, Playwright and Chromium available (override the browser
  path with `CHROMIUM_PATH`). This launches an isolated Flask fixture and mocks
  job requests; it never starts a dataset workflow.
- Live updates poll every two seconds. Stage/operation times, actual child PIDs,
  query names and output timestamps describe recorded activity. No completion
  percentage or remaining-time estimate is invented. Existing history is kept;
  completed history never receives a live-process payload.
- Detached distributed job `92e396cd515042d3a658d2ea57642746` passed on the
  existing **two-food synthetic fixture** in
  `data/realdev_1792251524919313490/`: HDFS/YARN verification, file round trip,
  MapReduce, Pig and all eight Hive executions reconciled. Live MapReduce/Pig
  output, active Hive query/log files, and dashboard restart/reconnection were
  checked during execution. The completed job exposes no live process. This
  checks the progress implementation, not full USDA performance or lab topology.
