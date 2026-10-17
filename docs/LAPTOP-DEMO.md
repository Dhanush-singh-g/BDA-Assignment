# How to show the project on your laptop

Everything here runs in your **Ubuntu terminal**. This guide uses the saved
**10,000-food subset**, not the full dataset. You already created these files;
cloning GitHub on another laptop will not include your saved data/results.

## 1. Just want to show the website?

Start here. The website reads saved answers, so MongoDB and Hadoop can stay off.
The commands update your code, install Python packages and start the website.

```bash
cd ~/BDA-Assignment
git pull --ff-only origin main
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m fdc.dashboard
```

Open the address printed by Flask in your Windows browser. Select
`data/realdev_1792236286088591242`. Show these things:

- Search for nutrient ID `1003` (protein).
- Explain that an index found a food by checking one document instead of 10,000.
- Compare Hive's query times and storage sizes; do not assume RCFile always wins.
- Point out the development-subset label and source fingerprint.
Stop the dashboard with **Ctrl+C**. No data is deleted.

## 2. Want to show the jobs actually running?

This starts the master and two worker containers, checks they can communicate,
then reruns the same small real-data test. Each tool's answer must match the
expected counts, totals and averages. It can take several minutes.

Stop the dashboard if memory is tight; keep MongoDB stopped. Dependencies are
already installed on your laptop. For a fresh installation, first follow
[Windows setup](windows-home.md).

```bash
docker stop fdc-mongo-dev
docker compose -f infra/compose.yaml up -d --no-build
```

Wait about a minute, then run:

```bash
docker compose -f infra/compose.yaml exec master bash scripts/verify_cluster.sh
.venv/bin/python tests/real_subset_cluster.py \
  --subset data/dev10k_export_01 --mongo-results results/mongo/dev10k_01
```

Show the two live DataNodes, two RUNNING YARN workers, successful job and final
`Distributed development checks passed`. The printed `data/realdev_<id>/` folder
contains `SUCCESS.json`, `cluster.log`, MapReduce output and Hive evidence.
Each invocation creates a new run; do not repeat unnecessarily.

## 3. Done showing it?

```bash
docker compose -f infra/compose.yaml stop
```

Keep the ZIP, development export and evidence folders. Three containers share
one physical laptop; the required college deployment remains a separate step.
