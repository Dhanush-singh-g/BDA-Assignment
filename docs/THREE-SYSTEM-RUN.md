# Three physical systems: setup and full run

Use one **master** and two **workers**, on the same college network. Commands
below assume Linux, a dedicated `hadoop` user and a new cluster. Actual IPs,
resource limits and installation paths must match the lab.

## 1. Prepare and configure

| System | Services |
| --- | --- |
| master | NameNode, ResourceManager, JobHistory, HiveServer2, MongoDB, project client |
| worker1 | DataNode, NodeManager, Python Streaming tasks |
| worker2 | DataNode, NodeManager, Python Streaming tasks |

On all nodes: stable IP/name resolution (`master`, `worker1`, `worker2`), trusted
SSH keys from master, synchronized clocks, Java 8, Hadoop 2.10.2 and Python 3.
On master: Python 3.12 + venv, Pig 0.17.0, Hive 2.3.9 and MongoDB 7.0.16.
Install verified distributions; expose services only on the private lab network.
Set `JAVA_HOME`, `HADOOP_HOME`, `HADOOP_CONF_DIR`, `PIG_HOME`, `HIVE_HOME` and `PATH`.

Copy `infra/hadoop/*.xml` into each node's Hadoop configuration directory,
then adapt them:

- `core-site.xml`: master HDFS address; writable local temporary directory;
  remove the Docker-only `hadoop.proxyuser.root.*` properties.
- `hdfs-site.xml`: persistent NameNode/DataNode directories owned by `hadoop`;
  replication **2**; remove the container hostname-check override.
- `yarn-site.xml`: master address; worker memory/CPU limits that fit each machine.
- `mapred-site.xml`: YARN execution and master's JobHistory addresses; task heaps
  and memory requests must fit the YARN limits.
- Both `slaves` (Hadoop 2) and `workers`: one line each for `worker1`, `worker2`.
- `hadoop-env.sh`: set Java 8's `JAVA_HOME` on every node.

Configure Hive's persistent metastore and writable warehouse on master; use the
same HDFS/YARN configuration, `hive.execution.engine=mr` and local auto mode off.
For a single-user demo, embedded Derby must have only one owning HiveServer2
process; use an external metastore for concurrent clients. See
[college configuration details](college-cluster.md) and the
[official Hadoop guide](https://apache.github.io/hadoop/hadoop-project-dist/hadoop-common/ClusterSetup.html).

## 2. Start and verify

As `hadoop` on master, **format only once for a new, empty NameNode**:

```bash
hdfs namenode -format
```

For normal startup (do not format again):

```bash
start-dfs.sh
start-yarn.sh
mr-jobhistory-daemon.sh start historyserver
hdfs dfs -mkdir -p /tmp /user/hive/warehouse /user/hadoop
hdfs dfs -chmod 1777 /tmp
# First-time Derby initialization only, if using that metastore:
# schematool -dbType derby -initSchema
hiveserver2 > "$HOME/hiveserver2.log" 2>&1 &
```

Start the configured MongoDB service. Clone the repository on master, copy the
**entire official ZIP** there, and create `.venv` with `requirements.txt` installed.
From the checkout, verify `scripts/verify_cluster.sh` and Hive `SELECT 1` succeed.

## 3. Execute and show

With the default local MongoDB and HiveServer2 endpoints (configure
`MONGODB_URI`, `HIVE_JDBC_URL`, `HIVE_USER` securely if different):

```bash
.venv/bin/python -m fdc.inspect_archive --archive /path/to/full.zip --verify
.venv/bin/python -m fdc.part1 --archive /path/to/full.zip \
  --run-id college_full01 --dataset-kind full-release \
  --cluster-mode client --repeats 5
.venv/bin/python -m fdc.dashboard
```

Replace `/path/to/full.zip` with the actual October 2024 ZIP. Use a new run ID;
this command creates a fresh full import and outputs. On failure, inspect
`results/college_full01/cluster.log` before retrying. Budget disk on each node.

Show `PART1_REPORT.md`, `reconciliation.json`, benchmark files and dashboard.
Attach machine inventories, configuration snapshots, worker registration and
JobHistory task placement on **both workers**. A successful command alone does
not prove physical separation. Complete the final report and demo evidence.
