# Presentation commands — laptop Docker setup

The dashboard now places these source-verification commands beside the relevant
partial results under Theme 1, Theme 2 and Theme 3. **Copy command** copies text;
it does not execute anything. Commands use the selected run's recorded database
and HDFS path. Missing source names are labelled rather than guessed. Viewing
saved results needs no services; executing a command requires its service.

Run commands in **Ubuntu Terminal**, from `~/BDA-Assignment`. Keep a second
terminal for inspection while the dashboard is open. This guide is for your
laptop containers; use `docs/THREE-SYSTEM-RUN.md` for native lab machines.

## 1. Start the website

```bash
cd ~/BDA-Assignment
git pull --ff-only origin main
sudo service docker start
.venv/bin/python -m fdc.dashboard
```

Open Flask's printed address. Use **View results** for an existing run or **Run
analysis** for a new run. Leave this terminal open. Do not switch/stop services
while an analysis is running. Closing the browser does not stop the worker.

## 2. View MongoDB — original and processed documents

When no analysis is running, use the UI's **Start MongoDB** service button, or:

```bash
cd ~/BDA-Assignment
docker compose -f infra/compose.yaml stop
bash scripts/start_mongo.sh
docker exec -it fdc-mongo-dev mongosh
```

You are now inside **mongosh**, not the Ubuntu shell. Enter:

```javascript
show dbs
use fdc_home202410
show collections
db.raw_food.countDocuments({})
db.raw_food.find().limit(5)
db.raw_food_nutrient.find().limit(5)
db.raw_nutrient.find().limit(5)
```

The full source database contains raw imports. To show derived documents and
aggregation outputs, choose the **analytical database displayed in Theme 1**.
For your earlier manual 50,000-food experiment:

```javascript
use fdc_dev50k_01
db.foods.find({}, {nutrients: {$slice: 5}}).limit(3)
db.foods.aggregate([
  {$match: {data_type: {$ne: ""}}},
  {$group: {_id: "$data_type", foods: {$sum: 1}}},
  {$project: {_id: 0, data_type: "$_id", foods: 1}}
])
```

UI jobs use names like `fdc_ui50000_…`, so use that run's actual database name
instead if needed. The full source database may have no completed derived
`foods` collection. An empty preview there is not proof that raw data is absent.

For one food, first look at its actual `fdc_id`, then query its linked rows.
This example uses a known source ID; choose one present in the selected database:

```javascript
db.raw_food.find({fdc_id: "1105904"})
db.raw_food_nutrient.find({fdc_id: "1105904"}).limit(10)
db.raw_food.find({fdc_id: "1105904"}).hint("idx_fdc_id").explain("executionStats")
```

The last command requires the index created by analytics. Raw CSV IDs are strings.
Type `exit` to leave mongosh. In Windows MongoDB Compass you can instead connect
to `mongodb://localhost:27017` while MongoDB is running.

## 3. Locate and view ordinary local files

### Add the missing BEFORE preview to an older analysis

With MongoDB running and no analysis active, run this in Ubuntu for your earlier
50-food UI experiment:

```bash
cd ~/BDA-Assignment
.venv/bin/python -m fdc.preview \
  --results results/mongo/ui50_7963172fc4cb41e1
```

For the earlier manual 50,000-food experiment, whose older profile may not record
its database name:

```bash
.venv/bin/python -m fdc.preview \
  --results results/mongo/dev50k_01 --database fdc_dev50k_01
```

Choose the command matching the saved result you are showing. This reads the
matching database and saves a new preview file; it does not rerun analytics,
change database records or replace measured results. Existing previews are kept.
Refresh the website afterward. Its BEFORE panel always remains visible, with
an explicit message when an older run has no raw examples. A newly captured
preview is labelled with its capture time and current-database origin.

### Browse the saved files

In Ubuntu Terminal, select an evidence folder. This example is your earlier
50,000-food run; change the value to the folder selected in the dashboard:

```bash
cd ~/BDA-Assignment
run_id=realdev_1792244956898668695
ls data/
ls "data/$run_id"
ls "data/$run_id/prepared"
head -n 5 "data/$run_id/prepared/foods.tsv"
head -n 5 "data/$run_id/prepared/food_nutrients.tsv"
cat "data/$run_id/prepared/manifest.json"
cat "data/$run_id/SUCCESS.json"
head -n 10 "data/$run_id/mapreduce.tsv"
ls "data/$run_id/hive"
cat "data/$run_id/hive/benchmark.json"
```

`head` previews a few lines; `cat` displays a small complete file. For larger
text files, use `less "actual/path/to/file"`; press **Q** to leave. The quoted
`actual/path/to/file` is an example: replace it with an existing filename from
`ls`. Use Tab to complete names. `explorer.exe .` opens the project folder in
Windows File Explorer; TSV files open with VS Code or another text editor.

`foods.tsv` contains food details; `food_nutrients.tsv` contains linked nutrient
observations. `manifest.json` records counts/hash. `rejected.jsonl` records
preparation rejects and may be empty. `join.sqlite` is a binary SQLite working
database: inspect it with a SQLite browser, not `cat`. The original ZIP remains
an archive, not a text file.

To inspect the local SQLite lookup file without installing another tool, keep
`run_id` set as above and paste this whole block into Ubuntu Terminal:

```bash
.venv/bin/python - "$run_id" <<'PY_SQLITE'
import sqlite3, sys
path = f"file:data/{sys.argv[1]}/prepared/join.sqlite?mode=ro"
with sqlite3.connect(path, uri=True) as db:
    print("Tables:", db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
    print("Foods:", db.execute("SELECT * FROM food LIMIT 5").fetchall())
    print("Nutrients:", db.execute("SELECT * FROM nutrient LIMIT 5").fetchall())
PY_SQLITE
```

This opens SQLite read-only. For a ZIP, use an archive viewer or the project's
archive inspection command rather than `cat`.

To show any project source file:

```bash
cat mapreduce/mapper.py
cat mapreduce/reducer.py
cat pig/clean_nutrients.pig
cat hive/tables.hql
cat hive/nutrient_summary.hql
cat hive/protein_summary.hql
```

## 4. View Hadoop/HDFS files

When no analysis is running, use the UI's **Start Hadoop** service button. Or,
after leaving mongosh, run these Ubuntu commands:

```bash
cd ~/BDA-Assignment
docker stop fdc-mongo-dev
docker compose -f infra/compose.yaml up -d --no-build
```

Wait for startup. `docker stop` can report the MongoDB container missing on a
fresh machine; install/start it using the setup guide before analysis.
These next commands inspect the running cluster:

```bash
docker compose -f infra/compose.yaml ps
docker compose -f infra/compose.yaml exec -T master hdfs dfsadmin -report
docker compose -f infra/compose.yaml exec -T master yarn node -list -states RUNNING
docker compose -f infra/compose.yaml exec -T master hdfs dfs -ls /user/root/fdc
```

Set the run ID for **this terminal**, then list that run's HDFS files:

```bash
run_id=realdev_1792244956898668695
docker compose -f infra/compose.yaml exec -T master \
  hdfs dfs -ls -R "/user/root/fdc/$run_id"
```

To browse any HDFS directory, replace the final path with the real path shown by
`-ls`. To inspect one small text result, use `hdfs dfs -cat` through the container:

```bash
docker compose -f infra/compose.yaml exec -T master \
  hdfs dfs -cat "/user/root/fdc/$run_id/mapreduce/part-*"
```

For a **large** text dataset, download a readable copy rather than dumping all
rows into Terminal. Choose a fresh output folder each time:

```bash
view_dir="data/hdfs-view-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$view_dir"
docker compose -f infra/compose.yaml exec -T master \
  hdfs dfs -get "/user/root/fdc/$run_id/pig_clean" "/project/$view_dir/"
ls "$view_dir/pig_clean"
```

Now use `less` with an actual `part-*` filename printed by `ls`. `/project` inside
the container is your `~/BDA-Assignment` folder on the laptop. Downloads persist
in the new local folder. HDFS internal worker block directories are not ordinary
TSV folders; do not change their permissions or edit their files.

## 5. View Hive Text and RCFile records

With Hadoop and Hive running, the following opens an interactive SQL terminal:

```bash
docker compose -f infra/compose.yaml exec master \
  beeline -u jdbc:hive2://localhost:10000/default -n root
```

Inside **Beeline**, run:

```sql
SHOW DATABASES;
USE fdc_realdev_1792244956898668695;
SHOW TABLES;
DESCRIBE nutrients_text;
DESCRIBE FORMATTED nutrients_rcfile;
SELECT * FROM nutrients_text LIMIT 5;
SELECT * FROM nutrients_rcfile LIMIT 5;
SELECT COUNT(*) FROM nutrients_text;
SELECT COUNT(*) FROM nutrients_rcfile;
```

Use the Hive database matching your actual run ID. `DESCRIBE FORMATTED` includes
the underlying HDFS location and storage information. To show the same protein
question on both tables:

```sql
SELECT data_type, COUNT(*), SUM(amount), AVG(amount)
FROM nutrients_text WHERE nutrient_id = 1003 AND LOWER(unit) = 'g'
GROUP BY data_type;
SELECT data_type, COUNT(*), SUM(amount), AVG(amount)
FROM nutrients_rcfile WHERE nutrient_id = 1003 AND LOWER(unit) = 'g'
GROUP BY data_type;
```

Enter `!quit` to leave Beeline. RCFile is binary; reading it with `cat` will not
produce a readable table. Hive decodes it. The Text and RCFile datasets are built
once per pipeline run and reused by repeated queries. Their answers must match.
Recorded benchmark timings/sizes are in the run's `hive/benchmark.json`; these
interactive demonstration queries are separate from those saved measurements.

## 6. Docker shells, files and logs

These are **Ubuntu Terminal** commands:

```bash
docker ps
docker exec fdc-mongo-dev ls -lh /data/db
docker compose -f infra/compose.yaml logs --tail 50 master worker1 worker2
docker compose -f infra/compose.yaml exec master bash
```

The last command opens a shell **inside master**. There you can enter:

```bash
pwd
ls /project
ls /state/logs
ls /opt/hadoop/etc/hadoop
cat /opt/hadoop/etc/hadoop/core-site.xml
```

For another readable file, use `less` if installed, or `head -n 20 /actual/path`.
Use `ls` to discover the actual name first. Type `exit` to leave the container.
From Ubuntu you can copy a particular container file out with
`docker cp CONTAINER:/actual/path ./new-local-name`; replace CONTAINER/path with
names returned by `docker ps` and `ls`. Choose a new local filename.

MongoDB `/data/db` contains internal database files: inspect records through
mongosh/Compass. HDFS worker storage contains internal blocks: inspect logical
files through HDFS/Hive. Neither internal storage directory should be edited
for the presentation.

## What should I show if asked…?

| Faculty asks | Show |
| --- | --- |
| Original ingested food documents | MongoDB `raw_food`, five-row preview |
| How foods connect to nutrients | Same fdc_id in raw_food and raw_food_nutrient |
| Data after linking/aggregation | `foods` preview and aggregation outputs in Theme 1 |
| Mapper/reducer/Pig/Hive code | Section 3's source-file commands |
| Stored Hadoop input or output | HDFS listing and a selected text file/download |
| RCFile contents | Hive `SELECT … LIMIT 5`, not a text editor |
| Query/storage comparison | Dashboard and saved benchmark.json |
| Execution failure/progress | Selected run's cluster.log and UI job's worker.log |

The new UI document previews are archived during analytics, so results remain
viewable while MongoDB is stopped. Older runs can show saved aggregation output,
but raw examples are labelled as unavailable if no preview was captured. Their
actual databases remain inspectable with section 2; no fabricated records are used.
