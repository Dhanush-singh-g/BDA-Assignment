# Walk into the lab: what do I do on each computer?

This guide assumes **three separate Ubuntu 24.04 Linux computers**, wired to the
same college network, and permission from the lab administrator. It is a fresh
installation guide, not instructions for changing an existing Hadoop cluster.
The physical-lab steps have not yet been tested on your college machines.

**If the computers run Windows, stop here and ask the lab admin about Linux.**
Do not reinstall their OS. Windows/WSL on three machines needs extra networking
work; the native Linux commands below are not a ready-made Windows setup.

## 0. Before you start

Bring the official October 2024 ZIP on a USB drive. You do not need to extract it
or copy the laptop's MongoDB/HDFS data. Bring this guide too.

Choose these roles and put a label on each monitor:

| Label | What this computer will do |
| --- | --- |
| MASTER | Coordinate Hadoop; run MongoDB, Hive, Pig and project commands |
| WORKER1 | Store HDFS files and execute processing tasks |
| WORKER2 | Store HDFS files and execute processing tasks |

Practical starting targets: 16 GB RAM on master, 8 GB on each worker, and ample
free disk (aim for 100 GB on master and 50 GB per worker, then monitor it). These
are planning targets, not measured full-run requirements. Internet access is
needed to install/download tools. Do not start all jobs on undersized machines.

**Each command block says where to run it.** Use Terminal on Linux; do not paste
these commands into Windows PowerShell. `sudo` asks for the local admin password;
do not share passwords or keys in chat.

## 1. ALL THREE: find out what machines you have

Open Terminal on each computer:

```bash
cat /etc/os-release
hostname -I
free -h
df -h /
```

Write down each machine's LAN IPv4 address, RAM and free disk. Ask the admin for
stable/reserved LAN addresses so the IPs do not change during the experiment.

Example only (replace with your own addresses everywhere):

```text
192.168.1.101 master
192.168.1.102 worker1
192.168.1.103 worker2
```

On **each computer**, open `sudo nano /etc/hosts` and add those three actual
IP/name pairs. Remove conflicting old entries for those names. Save with
Ctrl+O, Enter, Ctrl+X. We use these names to reach the machines; you do not need
to rename their existing OS hostnames.

From each computer, test:

```bash
ping -c 2 master
ping -c 2 worker1
ping -c 2 worker2
```

If the network blocks ping, ask the admin to check connectivity. The admin must
also allow private LAN traffic for SSH and the Hadoop/YARN worker services;
opening SSH alone is not enough. Do not disable the firewall or expose Hadoop
to the public internet.

## 2. ALL THREE: install basics and create the project user

Run as the existing administrator:

```bash
sudo apt-get update
sudo apt-get install -y openssh-server rsync git python3 python3-venv gnupg procps
sudo systemctl enable --now ssh
sudo adduser hadoop
```

If `hadoop` already exists, use that account with the admin's help; do not recreate
it. The home directory must be `/home/hadoop` on all three machines for the paths
below. The admin does installations; Hadoop itself runs as `hadoop`, not root.

Open a shell as that user on **each computer**:

```bash
sudo -iu hadoop
```

Keep using this user for the rest of the guide unless a step explicitly says admin.

## 3. MASTER: arrange passwordless SSH to all three machines

As `hadoop`, check whether `~/.ssh/id_ed25519.pub` already exists. Reuse an
appropriate existing key instead of overwriting it. If there is no key:

```bash
ssh-keygen -t ed25519
```

Accept the default location. For this private teaching setup, an empty key
passphrase allows Hadoop's startup scripts to run without prompts; protect the
account and private key. Alternatively use a passphrase and an SSH agent.

On each computer, the admin can display its host fingerprint with:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

On MASTER, copy the public key and verify the displayed fingerprints when asked:

```bash
ssh-copy-id hadoop@master
ssh-copy-id hadoop@worker1
ssh-copy-id hadoop@worker2
ssh master 'whoami'
ssh worker1 'whoami'
ssh worker2 'whoami'
```

All three should print `hadoop` without asking for the login password. Do not
bypass host-key checks. Fix SSH before proceeding.

## 4. MASTER: download the code and verified tools

Only master needs Docker for the local MongoDB service and exporting the pinned
Java distribution. Workers run Hadoop directly on Linux, without Docker.

Have the **admin on MASTER** install Docker Engine using its official Ubuntu
instructions: https://docs.docker.com/engine/install/ubuntu/ . Install the Compose
plugin too. To permit the project user's commands, the admin may add `hadoop` to
the Docker group (this grants powerful access; use only on the approved lab host).
Then fully log out/back in as `hadoop` so group membership takes effect.

As `hadoop` on MASTER:

```bash
docker version
docker compose version
cd ~
git clone https://github.com/Dhanush-singh-g/BDA-Assignment.git
cd ~/BDA-Assignment
bash scripts/install.sh
```

If already cloned, use `git pull --ff-only origin main` in that checkout instead.
The installer downloads verified Hadoop 2.10.2, Pig 0.17.0, Hive 2.3.9 and Java 8,
plus Python dependencies and images. Wait for `Dependencies prepared`. Stop on
an error. This is an older teaching stack required for Pig/RCFile compatibility;
keep it on the isolated lab network.

**Do not start Docker Compose here.** We will use the physical workers.

Put the installed tools at identical paths on all three machines:

```bash
mkdir -p ~/fdc-tools
cp -a data/tools/java data/tools/hadoop data/tools/pig data/tools/hive ~/fdc-tools/
```

## 5. MASTER: create the physical-cluster configuration

Run this block on MASTER, from the checkout. It changes only generated tool
configuration under your home, not the source templates:

```bash
cd ~/BDA-Assignment
/usr/bin/python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET
home = Path.home()
conf = home / 'fdc-tools/hadoop/etc/hadoop'
for name in ('core-site.xml', 'hdfs-site.xml', 'yarn-site.xml', 'mapred-site.xml'):
    tree = ET.parse(Path('infra/hadoop') / name)
    root = tree.getroot()
    for prop in list(root):
        key = prop.findtext('name', '')
        if key.startswith('hadoop.proxyuser.root.') or key == 'dfs.namenode.datanode.registration.ip-hostname-check':
            root.remove(prop)
            continue
        value = prop.find('value')
        if value is not None and value.text:
            value.text = value.text.replace('/state/', str(home / 'hadoop-state') + '/')
    if name == 'hdfs-site.xml':
        prop = ET.SubElement(root, 'property')
        ET.SubElement(prop, 'name').text = 'dfs.namenode.secondary.http-address'
        ET.SubElement(prop, 'value').text = 'master:50090'
    tree.write(conf / name, encoding='utf-8', xml_declaration=True)
for name in ('slaves', 'workers'):
    (conf / name).write_text('worker1\nworker2\n')
with (conf / 'hadoop-env.sh').open('a') as f:
    f.write('\nexport JAVA_HOME=/home/hadoop/fdc-tools/java\n')
tree = ET.parse('infra/hive-site.xml')
for prop in tree.getroot():
    key = prop.findtext('name')
    if key == 'javax.jdo.option.ConnectionURL':
        prop.find('value').text = 'jdbc:derby:;databaseName=/home/hadoop/hadoop-state/metastore;create=true'
    if key == 'hive.server2.thrift.bind.host':
        prop.find('value').text = '127.0.0.1'
tree.write(home / 'fdc-tools/hive/conf/hive-site.xml', encoding='utf-8', xml_declaration=True)
PY
```

Defaults advertise 2.5 GB of YARN task memory and two cores per worker. The admin
should adjust `yarn-site.xml` and `mapred-site.xml` together if needed; leave RAM
for Linux and Hadoop's own daemons. Keep the same versions on all nodes.

Copy Java and the configured Hadoop directory to the workers:

```bash
ssh worker1 'mkdir -p /home/hadoop/fdc-tools'
ssh worker2 'mkdir -p /home/hadoop/fdc-tools'
rsync -a ~/fdc-tools/java ~/fdc-tools/hadoop worker1:/home/hadoop/fdc-tools/
rsync -a ~/fdc-tools/java ~/fdc-tools/hadoop worker2:/home/hadoop/fdc-tools/
```

## 6. ALL THREE: set command paths and create storage folders

Run as `hadoop` on **each computer**, once:

```bash
cat >> ~/.bashrc <<'ENV'
export JAVA_HOME=/home/hadoop/fdc-tools/java
export HADOOP_HOME=/home/hadoop/fdc-tools/hadoop
export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
export PIG_HOME=/home/hadoop/fdc-tools/pig
export HIVE_HOME=/home/hadoop/fdc-tools/hive
export PATH=$JAVA_HOME/bin:$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$PIG_HOME/bin:$HIVE_HOME/bin:$PATH
export HIVE_USER=hadoop
export HIVE_JDBC_URL=jdbc:hive2://localhost:10000/default
ENV
source ~/.bashrc
mkdir -p ~/hadoop-state/{name,data,tmp}
java -version
hadoop version
```

Expect Java 8 and Hadoop 2.10.2 everywhere. Pig/Hive paths are used only on master;
workers do not need those packages. Python 3 must work on both workers.

## 7. MASTER: initialize once, then start Hadoop

**Only on a new, empty cluster**, run:

```bash
hdfs namenode -format
```

Never run that again to fix a startup problem. Formatting an existing NameNode
can lose access to its data. If any Hadoop storage already exists, ask the admin
before initialization.

Now start the services from MASTER:

```bash
start-dfs.sh
start-yarn.sh
mr-jobhistory-daemon.sh start historyserver
```

After startup, check daemon processes:

```bash
jps
ssh worker1 '/home/hadoop/fdc-tools/java/bin/jps'
ssh worker2 '/home/hadoop/fdc-tools/java/bin/jps'
```

MASTER should show `NameNode`, `ResourceManager`, `JobHistoryServer` and usually
`SecondaryNameNode`. Each worker should show `DataNode` and `NodeManager`.
If a daemon is missing, inspect `~/fdc-tools/hadoop/logs/` on that machine.

## 8. MASTER: prove Hadoop works before using the dataset

```bash
cd ~/BDA-Assignment
bash scripts/verify_cluster.sh
```

Wait until it finishes. Expected: **two live DataNodes**, **two RUNNING YARN
nodes**, safe mode off and a successful sample MapReduce job. Save the terminal
output/application ID. If any check fails, fix it before going further.

## 9. MASTER: start Hive and MongoDB

Create shared HDFS folders as the `hadoop` user who owns this new cluster:

```bash
hdfs dfs -mkdir -p /tmp /user/hive/warehouse /user/hadoop
hdfs dfs -chmod 1777 /tmp
```

For our single-user demo, HiveServer2 owns one embedded Derby metastore. Initialize
it **once** on this new installation, before starting HiveServer2:

```bash
schematool -dbType derby -initSchema
hiveserver2 > "$HOME/hadoop-state/hiveserver2.log" 2>&1 &
```

Wait about a minute, then test it:

```bash
beeline -u jdbc:hive2://localhost:10000/default -n hadoop -e 'SELECT 1;'
```

Expect one row containing `1`. If it fails, read
`~/hadoop-state/hiveserver2.log`. Do not repeatedly initialize the metastore.
Use an external metastore if multiple Hive services need simultaneous access.

Start MongoDB on MASTER only:

```bash
cd ~/BDA-Assignment
bash scripts/start_mongo.sh
```

Expect `MongoDB responds to ping`. Default local MongoDB needs no connection
string. A different approved server requires `MONGODB_URI` set securely.
MongoDB remains local to master; the workers do not need to connect to it.

## 10. MASTER: copy the ZIP and check it

Copy the original ZIP from USB into `~/BDA-Assignment/data/raw/` using the file
manager, or use your actual USB path with `cp`. Create the folder first:

```bash
mkdir -p ~/BDA-Assignment/data/raw
```

Then:

```bash
cd ~/BDA-Assignment
.venv/bin/python -m fdc.inspect_archive \
  --archive data/raw/FoodData_Central_csv_2024-10-31.zip --verify
```

Check `crc_verified: true`. Your laptop's source SHA-256 was:

```text
85b6268117a8f6b8032d67a06ccd51ed1287a53ebaaeb0b3e262165e2820cb9f
```

The copied file should match. Keep the ZIP intact. Check free disk on **each
physical machine**; do not infer it from the compressed file size alone.

## 11. MASTER: run the whole project

Before the large run, execute the small automated Python/MongoDB checks:

```bash
FDC_MONGO_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
```

Then run the full workflow **once**:

```bash
.venv/bin/python -m fdc.part1 \
  --archive data/raw/FoodData_Central_csv_2024-10-31.zip \
  --run-id college_full01 --dataset-kind full-release \
  --cluster-mode client --repeats 5
```

Keep all three computers powered and awake. This takes time. The master prints
stage starts/completions; do not launch another copy because a stage is quiet.
In another MASTER terminal, watch:

```bash
cd ~/BDA-Assignment
tail -f results/college_full01/cluster.log
```

This run makes a **fresh full MongoDB import**, prepares files, uploads them to
HDFS, runs MapReduce/Pig/Hive, compares answers and writes a report. It does not
reuse the laptop's database. `--cluster-mode client` uses the physical Hadoop
cluster; do not change it to `docker` here.

If a stage fails, stop and read its error/log. The run deliberately refuses to
overwrite existing output. Do not repeatedly choose new run IDs without checking
disk use and diagnosing the cause.

## 12. MASTER: check success and show the dashboard

After successful completion:

```bash
cat results/college_full01/run.json
cat results/college_full01/reconciliation.json
less results/college_full01/PART1_REPORT.md
.venv/bin/python -m fdc.dashboard
```

Look for `complete: true` in `run.json`, successful stages, and passing
reconciliation. Open Flask's printed address in the **master's browser** and
select `results/college_full01`. This shows the newly measured full-data results.
A website opening alone does not prove the jobs passed.

## 13. What should we save for the presentation?

- OS, RAM, disk and IP/name details from all three computers.
- Hadoop configuration files and matching Java/Hadoop versions.
- Two registered workers, successful job/application IDs and daemon screenshots.
- Proof that task attempts ran on both workers. On MASTER, use JobHistory at
  `http://master:19888`, select a completed multi-task job, and show its task
  attempts/node addresses. Capture both worker names; rerun with suitable input
  splits if scheduling used only one worker. Registration alone is not proof.
- The entire `results/college_full01/` folder and its source fingerprint.
- Dashboard screenshots, conclusions and limitations in the final report.

Use the official guide for release-specific/admin details:
https://apache.github.io/hadoop/hadoop-project-dist/hadoop-common/ClusterSetup.html

## 14. How do we shut down safely?

After backing up the results, stop the dashboard with Ctrl+C. On MASTER:

```bash
stop-yarn.sh
mr-jobhistory-daemon.sh stop historyserver
stop-dfs.sh
docker stop fdc-mongo-dev
```

HiveServer2 was started in the background. Stop its exact process with `kill PID`
(use `ps -ef | grep '[H]iveServer2'` to identify it), or ask the admin to manage it
as a service. Do not kill every Java process on the machine. Keep storage folders;
normal restart uses service startup commands, **not** formatting or schema init.
