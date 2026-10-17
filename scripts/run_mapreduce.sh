#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${HADOOP_HOME:?Set HADOOP_HOME to the installed Hadoop directory}"
input=${1:?Usage: run_mapreduce.sh HDFS_INPUT HDFS_NEW_OUTPUT [REDUCERS]}
output=${2:?Specify a new output directory}
reducers=${3:-2}
[[ $reducers =~ ^[1-9][0-9]*$ ]] || { echo 'REDUCERS must be positive' >&2; exit 1; }
shopt -s nullglob
jars=("$HADOOP_HOME"/share/hadoop/tools/lib/hadoop-streaming-*.jar)
[[ ${#jars[@]} == 1 ]] || { echo 'Expected exactly one Hadoop Streaming JAR' >&2; exit 1; }
[[ $(hdfs getconf -confKey fs.defaultFS) == hdfs://* ]] || { echo 'An HDFS cluster is required' >&2; exit 1; }
hadoop jar "${jars[0]}" \
  -D mapreduce.framework.name=yarn \
  -D mapreduce.job.name=fdc-nutrient-summary \
  -D mapreduce.job.reduces="$reducers" \
  -files mapreduce/mapper.py,mapreduce/reducer.py \
  -mapper 'python3 mapper.py' -reducer 'python3 reducer.py' \
  -input "$input" -output "$output"
hdfs dfs -test -e "$output/_SUCCESS"
