# Track B Part 1 demonstration

Use the verified **full-release** run on the college cluster for submission.
Synthetic integration output may demonstrate development only. Keep the actual
run ID, source hash and machine inventory visible when presenting results.

## Prepare before the presentation

- Finish the full run and inspect `run.json`, `reconciliation.json` and
  `PART1_REPORT.md`. Confirm that the archive has the correct provenance.
- Keep three machine inventories, shared configuration files, worker registration,
  job/task-placement evidence and the original benchmark results ready.
- Review preparation rejects and explain the cleaning rules. Missing nutrient
  values are not converted into zeros. Negative finite observations are retained
  in raw storage and excluded from nutrient-amount summaries with recorded counts.
- Keep the official USDA source and dataset documentation as citations.
- Run long CRC scans, ingestion and benchmark repetitions before the demo rather
  than relying on an entire multi-GB download during the presentation.

## Theme 1

Show raw collection row counts and the derived schema, then the saved results for
food types, nutrient means and the faceted overview. Explain where `$match`,
`$group`, `$project`, `$unwind` and `$facet` appear in `fdc/mongo.py`.

Use the actual run's database. This read-only mongosh example profiles the same
food-ID query through both plans:

```javascript
const c = db.getSiblingDB("fdc_full202410_01").raw_food;
const q = {fdc_id: c.findOne().fdc_id};
printjson(c.find(q).hint({$natural: 1}).explain("executionStats"));
printjson(c.find(q).hint("idx_fdc_id").explain("executionStats"));
```

Compare returned rows, documents/keys examined and execution time. Explain why
small warmed queries may report zero server milliseconds, and use the retained
individual measurements rather than inventing an index speedup.

## Theme 2

Show `hdfs dfsadmin -report` and `yarn node -list -states RUNNING`, then the
successful sample-job and Streaming job IDs. Show original/prepared HDFS files,
the probe cat/get integrity result and deletion of only the demo directory in
`cluster.log`. Show actual task placement on the separate worker systems.

Explain the Streaming key `(data_type, nutrient_id)`, partial observations and
the reducer's count/sum/mean. Compare saved output against the independent
prepared-data reference in `reconciliation.json`.

## Theme 3

Show `pig/clean_nutrients.pig`, its YARN job and the input/output accounting.
Explain why a CSV-aware normalization step handles quoted/multiline CSV before
Pig's typed transformation. Display both Hive schemas and run the same selected
query against each table if time permits:

```bash
beeline -u jdbc:hive2://MASTER:10000/default -n hadoop \
  --hivevar DATABASE=fdc_full202410_01 \
  --hivevar TABLE=nutrients_text -f hive/protein_summary.hql
beeline -u jdbc:hive2://MASTER:10000/default -n hadoop \
  --hivevar DATABASE=fdc_full202410_01 \
  --hivevar TABLE=nutrients_rcfile -f hive/protein_summary.hql
```

Replace `MASTER`, username and run database with the real deployment. Show result
equality before discussing performance. Present measured medians and ranges,
excluding warmups, and logical sizes separately from replication-adjusted sizes.
State that Text is uncompressed and RCFile uses gzip, so both format and codec
contribute to the size difference. Do not generalize fixture measurements.

The Flask dashboard belongs to Part 2 and is not required to demonstrate the
three Part 1 themes themselves.
