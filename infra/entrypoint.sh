#!/usr/bin/env bash
set -euo pipefail
mkdir -p /state/tmp /state/logs /state/pids
export HADOOP_LOG_DIR=/state/logs HADOOP_PID_DIR=/state/pids
export YARN_LOG_DIR=/state/logs YARN_PID_DIR=/state/pids
pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true; wait || true' EXIT
trap 'exit 0' TERM INT
if [[ ${1:?Choose master or worker} == master ]]; then
  if [[ ! -f /state/name/current/VERSION ]]; then
    hdfs namenode -format -nonInteractive
  fi
  hdfs namenode > /state/logs/namenode.log 2>&1 & pids+=("$!")
  yarn resourcemanager > /state/logs/resourcemanager.log 2>&1 & pids+=("$!")
  mapred historyserver > /state/logs/historyserver.log 2>&1 & pids+=("$!")
  for ((i=0; i<60; i++)); do
    if hdfs dfsadmin -safemode get 2>/dev/null | grep -q 'Safe mode is OFF'; then break; fi
    sleep 1
  done
  hdfs dfs -mkdir -p /tmp /user/root /user/hive/warehouse
  hdfs dfs -chmod 1777 /tmp
  if [[ ! -d /state/metastore ]]; then
    schematool -dbType derby -initSchema
  fi
  hiveserver2 > /state/logs/hiveserver2.log 2>&1 &
  pids+=("$!")
else
  hdfs datanode > /state/logs/datanode.log 2>&1 & pids+=("$!")
  yarn nodemanager > /state/logs/nodemanager.log 2>&1 & pids+=("$!")
fi
wait -n "${pids[@]}"
