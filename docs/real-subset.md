# Real-data subset integration

This development run reuses `fdc_dev10k_01` and its saved analytics, exports the
same linked records, and compares independent prepared-data aggregates against
MongoDB, YARN Streaming and every Hive Text/RCFile query. It does not replace the
required full-data physical-cluster run. Source and exported-subset hashes are
recorded separately. The selection is not representative sampling.

From the project root, temporarily stop the cluster to export with MongoDB alone:

```bash
docker compose -f infra/compose.yaml stop
bash scripts/start_mongo.sh
.venv/bin/python -m fdc.export_dev --database fdc_dev10k_01 --output data/dev10k_export_01
docker stop fdc-mongo-dev
docker compose -f infra/compose.yaml up -d --no-build
```

Wait for services to become ready, then run:

```bash
.venv/bin/python tests/real_subset_cluster.py \
  --subset data/dev10k_export_01 --mongo-results results/mongo/dev10k_01
```

Progress is logged in the printed `data/realdev_<id>/cluster.log`. The runner
checks worker readiness, HDFS operations, MapReduce results, Pig counts/negative
filtering, and Hive result groups/counts/sums/means. One warmup plus one measured
run per query/table pair keeps this development check short (eight executions).
`SUCCESS.json` is written only after all checks pass. Failures retain evidence;
inspect the error and log before rerunning. Export destinations must be new.
