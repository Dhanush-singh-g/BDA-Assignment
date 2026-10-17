# Test the complete dataset at home on Windows

Use Ubuntu 24.04 under WSL2 and Docker Desktop with Linux containers. This runs
one master and two worker containers on your laptop. Final submission still
requires the three college systems. Full-data execution on Windows/WSL2 has not
yet been validated; the same container workflow passed integration in the cloud.

## 1. Prepare Windows

In PowerShell as Administrator:

```powershell
wsl --install -d Ubuntu-24.04
```

Restart if Windows requests it and finish Ubuntu's username/password setup.
Install Docker Desktop from https://www.docker.com/products/docker-desktop/.
Enable its WSL2 engine and Ubuntu integration in Settings, then start Docker.
The three Hadoop containers have 4 GiB limits each; allow roughly 12 GiB for
them, with additional RAM for MongoDB, Windows and the full dataset. Check your
actual available memory before starting. Archive size alone does not determine
RAM or storage requirements.

## 2. Clone and verify the real archive

Run these commands in the **Ubuntu terminal**, not PowerShell. Keep the checkout
inside Ubuntu's home directory for Linux filesystem semantics and performance.

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv gnupg
git clone https://github.com/Dhanush-singh-g/BDA-Assignment.git
cd BDA-Assignment
docker version
docker compose version
ls -lh /mnt/c/Users/dhanu/Downloads/FoodData_Central_csv_2024-10-31*
python3 -m fdc.inspect_archive \
  --archive /mnt/c/Users/dhanu/Downloads/FoodData_Central_csv_2024-10-31.zip \
  --verify
free -h
df -h . /mnt/c
```

Windows may hide the `.zip` extension. If the listing shows a different filename,
use that exact ZIP path. Keep the original archive intact. Inspect the expanded
CSV sizes and available disk before proceeding: MongoDB, prepared data, indexes,
two replicated HDFS copies and Hive outputs all consume additional space. WSL's
virtual disk also occupies space on Windows; its reported virtual capacity does
not guarantee sufficient space on the Windows drive. Share the inspection,
memory and disk outputs if capacity is uncertain. Do not share credentials.

## 3. Install and check services

```bash
bash scripts/install.sh
bash scripts/start_mongo.sh
docker compose -f infra/compose.yaml up -d --no-build
docker compose -f infra/compose.yaml exec master bash scripts/verify_cluster.sh
docker compose -f infra/compose.yaml exec master \
  beeline -u jdbc:hive2://localhost:10000/default -n root -e 'SELECT 1;'
FDC_MONGO_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
```

Wait for Hadoop/Hive startup before verification. On a failure, inspect
`docker compose -f infra/compose.yaml logs --tail 100`; preserve the error rather
than deleting storage or repeatedly starting full imports.

## 4. Execute all three themes on the entire ZIP

Once the capacity and readiness checks pass:

```bash
.venv/bin/python -m fdc.part1 \
  --archive /mnt/c/Users/dhanu/Downloads/FoodData_Central_csv_2024-10-31.zip \
  --run-id home_full202410_01 --dataset-kind full-release \
  --cluster-mode docker --repeats 5
```

There is no sampling or production row limit. Keep the laptop powered and awake.
The driver uploads the archive from its Windows path without requiring a second
host copy. Results and the generated report appear in
`results/home_full202410_01/`. A failure retains logs and partial state; diagnose
it before using a new run ID, because a new run creates additional data copies.

To stop services while retaining data:

```bash
docker compose -f infra/compose.yaml stop
docker stop fdc-mongo-dev
```

See [full-run.md](full-run.md) for outputs and final submission requirements.
