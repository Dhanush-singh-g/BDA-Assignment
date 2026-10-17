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

## 2. Run jobs using the website buttons

The dashboard opens in **View results**. Choose a saved analysis and click
**Open results**. To process data, switch to the **Run analysis** tab.

- The source database is fixed to `fdc_home202410`; there is nothing to edit.
- Choose 10,000, 50,000, 100,000, a custom size (1–100,000 foods), or **Entire
  dataset**. Click **Start analysis**. Every food includes linked nutrients.
- Subsets create separate databases/results. **Entire dataset** reuses the full
  database, checks its records/hash against the original ZIP, runs every theme,
  and generates a reconciled report with five measured Hive repetitions. It
  does not duplicate the raw import. It rebuilds derived `foods` in the fixed DB.
- Keep the ZIP in `data/raw/FoodData_Central_csv_2024-10-31.zip` or your existing
  Windows Downloads location. Full-data mode prepares new files and uses extra
  disk; it can take hours and is not yet validated on your full laptop dataset.

To repeat your 50,000-food distributed check without MongoDB reprocessing, expand
**Reuse prepared data or manage services**, select `data/dev50k_export_01`, and
click **Run distributed checks**. Service buttons are in that optional section.

**Analysis progress** shows stages/logs and links to completed results. The app
switches services to save RAM and runs one UI job at a time. Keep Ubuntu running
and the laptop awake; closing a tab does not cancel the job. Do not start Terminal
jobs at the same time. There is no force-cancel button. Inspect failures before
rerunning; old data is not deleted automatically. For physical college systems,
use the separate lab guide; these controls manage the laptop Docker stack only.

## 3. Prefer Terminal commands?

This starts the master and two worker containers, checks they can communicate,
then reruns the same small real-data test. Each tool's answer must match the
expected counts, totals and averages. It can take several minutes.

Stop the dashboard if memory is tight; keep MongoDB stopped. Dependencies are
already installed on your laptop. For a fresh installation, first follow
[fresh laptop setup](TECHNICAL-REFERENCE.md).

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

## 4. Done showing it?

```bash
docker compose -f infra/compose.yaml stop
```

Keep the ZIP, development export and evidence folders. Three containers share
one physical laptop; the required college deployment remains a separate step.
