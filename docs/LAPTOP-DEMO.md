# Laptop: run and demonstrate

Use **Ubuntu/WSL2**, from `~/BDA-Assignment`. Your existing 10,000-food results
are development evidence; they do not establish full-dataset completion.

## 1. Show the dashboard (no cluster needed)

```bash
cd ~/BDA-Assignment
git pull --ff-only origin main
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m fdc.dashboard
```

Open the address printed by Flask in your Windows browser. Select
`data/realdev_1792236286088591242`. Demonstrate scope/source hash, nutrient search,
MongoDB index comparison, Hive timing charts and storage measurements.
Stop the dashboard with **Ctrl+C**. No data is deleted.

## 2. Demonstrate distributed execution on this laptop

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

## 3. Finish

```bash
docker compose -f infra/compose.yaml stop
```

Keep the ZIP, development export and evidence folders. Three containers share
one physical laptop; the required college deployment remains a separate step.
