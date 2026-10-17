# Walk into the lab: what do I do on each computer?

This guide assumes **three separate Ubuntu 24.04 Linux computers**, wired to the
same college network, and permission from the lab administrator. It is a fresh
installation guide, not instructions for changing an existing Hadoop cluster.
The physical-lab steps have not yet been tested on your college machines.

**If the computers run Windows, stop here and ask the lab admin about Linux.**
Do not reinstall their OS. Windows/WSL on three machines needs extra networking
work; the native Linux commands below are not a ready-made Windows setup.

## First: where do I type things?

1. Sit at the computer named in the step and log in to Ubuntu.
2. Press **Ctrl+Alt+T** to open Terminal (or search for “Terminal” in Applications).
3. Type/paste the commands inside a `bash` block into Terminal. Press **Enter**.
   Run one command at a time and check for errors before the next one.
4. Do **not** copy the Markdown backticks, the word `bash`, or a prompt such as
   `hadoop@master:~$`. Those are not parts of the command.
5. Blocks labelled `text` show example output or file contents. Do not run them
   as commands. This guide explicitly says when to type text into nano instead.
6. A line ending in `\` continues on the next line. Paste the complete command.
   For a block containing `<<'PY'` or `<<'ENV'`, paste the **whole block**, including
   its closing `PY` or `ENV`. The terminal waits until that closing line arrives.
7. Wait for the prompt to return before continuing, except where a command is
   deliberately left running (HiveServer2 or the dashboard).

No project software is assumed installed: this guide installs the basic packages,
Docker, Python dependencies, Java, Hadoop, Pig, Hive and MongoDB. It does require
Ubuntu itself, a working internet connection and an administrator account.
If you cannot log in or run `sudo`, the lab admin must provide access; you cannot
create administrator privileges by inventing a password.

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

**About passwords:** your existing Ubuntu login/admin password is used for `sudo`.
Later, `sudo adduser hadoop` will create a *new* project account and ask you to
choose its password. These are different accounts. Password characters do not
appear while typing—not even stars. Type the password and press Enter.

## 1. ALL THREE: find out what machines you have

On **each computer**, first use the existing administrator account to install
basic commands, including the nano editor. This is before we try to edit files:

```bash
sudo apt-get update
sudo apt-get install -y nano iproute2 iputils-ping ca-certificates curl
```

If `sudo` says “not in the sudoers file”, stop and ask the lab admin to run the
admin steps. If internet/package installation fails, fix it before proceeding.

Now check the machine:

```bash
cat /etc/os-release
hostname -I
free -h
df -h /
```

Write down each machine's LAN IPv4 address, RAM and free disk. Ask the admin for
stable/reserved LAN addresses so the IPs do not change during the experiment.

### What exactly do I write in `/etc/hosts`?

Suppose the actual addresses you wrote down were:

| Computer you selected | Its LAN IP | Name we want to use |
| --- | --- | --- |
| MASTER | `192.168.1.101` | `master` |
| WORKER1 | `192.168.1.102` | `worker1` |
| WORKER2 | `192.168.1.103` | `worker2` |

**Those numbers are only an example.** If your master is `10.0.0.21`, write
`10.0.0.21 master` instead. Use the LAN address from `hostname -I`, not `127.0.0.1`
and not a Docker/VPN address. Ask the admin if several addresses are printed.

On **ALL THREE computers**, run this in Terminal:

```bash
sudo nano /etc/hosts
```

Nano opens a text editor inside the terminal. You may initially see something
like this (the existing computer name will differ):

```text
127.0.0.1 localhost
127.0.1.1 lab-pc-01

::1 localhost ip6-localhost ip6-loopback
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
```

Use the arrow keys to move to the bottom. Add the following **inside nano**, using
your real addresses. Do not replace the whole file or delete its existing lines.
With the example addresses, the finished file would look like:

```text
127.0.0.1 localhost
127.0.1.1 lab-pc-01

::1 localhost ip6-localhost ip6-loopback
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters

192.168.1.101 master
192.168.1.102 worker1
192.168.1.103 worker2
```

The existing `lab-pc-01` line can be different on each machine. The **three added
LAN lines must be identical on all three computers**. If any of the names
`master`, `worker1` or `worker2` already appears on another line, ask the admin
to resolve that conflict; it must not point to both localhost and a LAN address.

Save and exit nano:

1. Hold **Ctrl** and press **O** (the letter O) to save.
2. At `File Name to Write: /etc/hosts`, press **Enter**.
3. Press **Ctrl+X** to exit back to Terminal.

Check the saved file and name resolution from Terminal:

```bash
cat /etc/hosts
getent hosts master worker1 worker2
```

The names should resolve to the LAN IPs you entered. This file is a small address
book: it lets Hadoop say `worker1` instead of spelling out its IP each time.

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
sudo apt-get install -y openssh-client openssh-server rsync git python3 python3-venv gnupg procps
sudo systemctl enable --now ssh
```

Now create the new project account on each computer:

```bash
sudo adduser hadoop
```

The command will ask for:

- `New password:` → choose a password for this computer's `hadoop` account.
- `Retype new password:` → enter it again (nothing appears while typing).
- Full name/room/phone → press Enter to leave optional fields blank.
- `Is the information correct? [Y/n]` → type `Y`, then Enter.

Record which password belongs to which computer securely. The passwords may be
different. You will use each computer's `hadoop` password for the initial SSH-key
copy. Do not put passwords in commands, GitHub, this guide or chat.

If `hadoop` already exists, use that account with the admin's help; do not recreate
it. The home directory must be `/home/hadoop` on all three machines for the paths
below. The admin does installations; Hadoop itself runs as `hadoop`, not root.

Open a shell as that user on **each computer**:

```bash
sudo -iu hadoop
```

The prompt should now start with `hadoop@...`. Check:

```bash
whoami
pwd
```

Expect `hadoop` and `/home/hadoop`. Keep using this account unless a step says
**admin**. To return to the original admin shell, type `exit` once. Opening a new
Terminal may use the original login account again; use `sudo -iu hadoop` when
needed. The project user does not need sudo privileges.

## 3. MASTER: arrange passwordless SSH to all three machines

As `hadoop`, check whether `~/.ssh/id_ed25519.pub` already exists. Reuse an
appropriate existing key instead of overwriting it. If there is no key:

```bash
ssh-keygen -t ed25519
```

You will see three prompts:

1. `Enter file in which to save the key ...` → press Enter for the default.
2. `Enter passphrase ...` → for this approved private teaching setup, press Enter
   for an empty key passphrase.
3. `Enter same passphrase again` → press Enter again.

If it asks to overwrite an existing key, answer **no** and ask the admin which
key to reuse. A key passphrase is different from the `hadoop` login password.
Protect the private key; a passphrase with an SSH agent is another option.

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

During each `ssh-copy-id` command:

- The first connection may ask `Are you sure you want to continue connecting?`.
  Compare the SHA256 host fingerprint with the one displayed on that target
  computer. If it matches, type `yes`, then Enter.
- At `hadoop@worker1's password:`, enter the `hadoop` password you created on
  **WORKER1**. Use WORKER2's password for worker2, and MASTER's for master.
- Expect a message saying a key was added. Future connections use that key.

The final three `ssh ... 'whoami'` commands should each print `hadoop` without
asking for the login password. Do not
bypass host-key checks. Fix SSH before proceeding.

## 4. MASTER: download the code and verified tools

Only master needs Docker for the local MongoDB service and exporting the pinned
Java distribution. Workers run Hadoop directly on Linux, without Docker.

Switch to the **original admin account on MASTER** (`exit` once if you are
inside the `sudo -iu hadoop` shell). Confirm you are back in that admin account
using `whoami`. On a fresh Ubuntu 24.04 machine, install Docker as follows.
If Docker is already installed, let the admin inspect it instead of replacing it.

Run each command in MASTER's Terminal as the admin:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

Now paste this **whole block**, including the final `EOF_DOCKER` line. It adds
Docker's official Ubuntu 24.04 package repository:

```bash
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<'EOF_DOCKER'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF_DOCKER
```

Then install and start Docker:

```bash
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker hadoop
```

The Docker group gives powerful access, so get the lab admin's agreement first.
Switch into a **fresh** project-user shell to load the new group membership:

```bash
sudo -iu hadoop
id -nG
```

The groups should include `docker`. Do not use an old open `hadoop` shell for
Docker commands. See Docker's official instructions if installation reports a
conflict: https://docs.docker.com/engine/install/ubuntu/ . Do not blindly remove
pre-existing packages or other students' containers.

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
plus Python dependencies and images. Java, Hadoop, Pig, Hive and MongoDB do
**not** need separate manual installations before this command. MongoDB is
installed as a Docker image, not as an Ubuntu database package. Wait for
`Dependencies prepared`. Stop on
an error. This is an older teaching stack required for Pig/RCFile compatibility;
keep it on the isolated lab network.

**Do not start Docker Compose here.** We will use the physical workers.

Put the installed tools at identical paths on all three machines:

```bash
mkdir -p ~/fdc-tools
cp -a data/tools/java data/tools/hadoop data/tools/pig data/tools/hive ~/fdc-tools/
```

## 5. MASTER: create the physical-cluster configuration

This is a Python script launched from Terminal. Paste the entire block through
its final `PY` line into Terminal; do not open a Python console or nano for it.
It fills in the Hadoop/Hive configuration files automatically.

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

Paste the whole block through `ENV`, then run the remaining lines. It writes
settings into `.bashrc`, a file Ubuntu reads when opening your shell. You do not
need to create `.bashrc` in advance; `>>` appends to it. Run this setup once.

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

Also check the installed Python on both workers:

```bash
python3 --version
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

On MASTER, open the file manager using `nautilus /home/hadoop/BDA-Assignment`
from the project user's terminal if available; otherwise use the logged-in desktop
file manager with the admin's help. Desktop apps are optional, not assumed here.
If a USB file is copied by the admin, give the project user read access to it.

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
```

`less` opens the report in the terminal; press **Q** to leave it. Then start the
dashboard with:

```bash
.venv/bin/python -m fdc.dashboard --view-only
```

Look for `complete: true` in `run.json`, successful stages, and passing
reconciliation. Open Flask's printed address in the **master's browser** and
select `results/college_full01`. This shows the newly measured full-data results.
A website opening alone does not prove the jobs passed.

**Why `--view-only` here?** The website's “Run analysis” and service buttons are
for the single-laptop Docker setup. This flag hides them and rejects job-control
requests, so nobody accidentally starts container workers instead of the two
physical workers. The college run is launched by the `fdc.part1 --cluster-mode
client` command above. The dashboard reads its saved outputs, including all three
themes' evidence; it does not need `fdc_home202410` or a separate browser database.
Frontend changes do not change the lab's Hadoop/network configuration.


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
