#!/usr/bin/env bash
set -euo pipefail
: "${HADOOP_HOME:?Set HADOOP_HOME}"
[[ $(hdfs getconf -confKey fs.defaultFS) == hdfs://* ]] || { echo 'HDFS is required' >&2; exit 1; }
java -version
hadoop version
printf 'Shared filesystem: %s\n' "$(hdfs getconf -confKey fs.defaultFS)"
report=$(hdfs dfsadmin -report)
printf '%s\n' "$report"
live=$(sed -nE 's/^Live datanodes \(([0-9]+)\):.*/\1/p' <<< "$report")
[[ $live =~ ^[0-9]+$ && $live -ge 2 ]] || { echo 'At least two live DataNodes required' >&2; exit 1; }
nodes=$(yarn node -list -states RUNNING)
printf '%s\n' "$nodes"
running=$(sed -nE 's/^Total Nodes:[[:space:]]*([0-9]+).*/\1/p' <<< "$nodes")
[[ $running =~ ^[0-9]+$ && $running -ge 2 ]] || { echo 'At least two RUNNING NodeManagers required' >&2; exit 1; }
timeout 120 hdfs dfsadmin -safemode wait
shopt -s nullglob
examples=("$HADOOP_HOME"/share/hadoop/mapreduce/hadoop-mapreduce-examples-*.jar)
[[ ${#examples[@]} == 1 ]] || { echo 'Expected one MapReduce examples JAR' >&2; exit 1; }
hadoop jar "${examples[0]}" pi -Dmapreduce.framework.name=yarn 4 1000
echo 'Service and YARN smoke checks passed. Separately record machine inventory and task placement.'
