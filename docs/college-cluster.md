# Deployment to the college systems

Final execution requires at least three separate systems: `master`, `worker1`,
`worker2`. The college hostnames, OS and SSH access have not been supplied, so
deployment and physical-node verification remain pending. Use the official
[Hadoop cluster setup guide](https://apache.github.io/hadoop/hadoop-project-dist/hadoop-common/ClusterSetup.html)
alongside the instructions matching the selected Hadoop release.

## Prepare all nodes

1. Record actual hostnames/IPs, OS, CPU, RAM, free disk and network interfaces.
   Confirm stable name resolution in both directions and synchronization of clocks.
2. Use a dedicated non-root `hadoop` user on all nodes. Configure that user's SSH
   access from the master to both workers using keys and trusted host fingerprints.
   Do not disable SSH host-key verification.
3. Install the same verified Java/Hadoop versions everywhere; install Python 3 on
   workers for Streaming. Install the tested Pig/Hive versions on the client/master.
   Use `infra/fetch_tools.py` for verified Apache archives and consult their license
   notices. The Compose configuration is a development reference, not a lab installer.
4. Set `JAVA_HOME`, `HADOOP_HOME`, `HADOOP_CONF_DIR`, `PIG_HOME`, `HIVE_HOME`
   and `PATH` for the dedicated user. Create persistent HDFS storage directories
   owned by that user. Keep NameNode and DataNode storage separate.

## Configure and start

Use `infra/hadoop/*.xml` as examples, replacing `master`, `/state/...`, and resource
limits with the real lab values. Do not copy container-only root impersonation
settings. Keep at least replication 2 with two workers. Configure the same
`core-site.xml`, `hdfs-site.xml`, `yarn-site.xml` and `mapred-site.xml` on every
node. Hadoop 2 uses the `slaves` file; retain the assignment's `workers` inventory
with the same two hostnames. Newer Hadoop releases use `workers` directly.

Format the NameNode **once, only for a new cluster** after confirming its storage
is empty. Never reformat a populated NameNode during normal startup. Start HDFS
and YARN with the release's documented scripts, and capture daemon logs.

Run `scripts/verify_cluster.sh` from the master/client. It checks registered
workers and submits a sample YARN job. Additionally save DataNode/NodeManager
hostnames, machine inventory and task-placement records to prove the physical
deployment. Investigate failed services rather than proceeding with local mode.

## Shared analytics services

Configure HiveServer2 with a persistent metastore. Embedded Derby in the Docker
example is suitable for a single development service; use the lab's supported
metastore deployment for shared concurrent access. Ensure Hive and Pig use the
same HDFS/YARN cluster. Use the shared MongoDB URI available to the team; the core
assignment does not require every MongoDB operation to be a Hadoop job. Do not
claim MongoDB is sharded unless it has actually been configured and verified.

MongoDB 7.0.16 is the tested reference server. The concise `$lookup` form in the
analytics requires MongoDB 5.0 or later; verify the lab server before ingestion.

Run the complete dataset through [the cluster workflow](cluster-workflow.md).
Save source hashes, row counts/rejects, raw result files, query plans, job IDs,
individual timings, HDFS sizes and configuration snapshots before writing the
report. The dashboard can later consume these verified outputs.
