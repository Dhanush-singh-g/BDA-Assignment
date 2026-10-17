#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
archive=${1:?Usage: hdfs_demo.sh ARCHIVE PREPARED_DIRECTORY NEW_HDFS_ROOT}
prepared=${2:?Specify prepared data directory}
root=${3:?Specify new HDFS root below /user/}
[[ $root =~ ^/user/[A-Za-z0-9_.-]+/fdc/[A-Za-z0-9_-]+$ ]] || {
  echo 'Use /user/USERNAME/fdc/UNIQUE_RUN as the HDFS root' >&2; exit 1;
}
[[ -f $archive && -f $prepared/manifest.json ]] || { echo 'Complete local inputs are required' >&2; exit 1; }
[[ $(hdfs getconf -confKey fs.defaultFS) == hdfs://* ]] || { echo 'An HDFS cluster is required' >&2; exit 1; }
if hdfs dfs -test -e "$root"; then
  echo 'HDFS destination already exists; use a new run name' >&2; exit 1
fi
hdfs dfs -mkdir -p "$root/raw" "$root/prepared" "$root/demo"
hdfs dfs -put "$archive" "$root/raw/"
hdfs dfs -put "$prepared/foods.tsv" "$prepared/food_nutrients.tsv" "$prepared/manifest.json" "$root/prepared/"
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
echo 'Track B HDFS round-trip verification' > "$scratch/probe.txt"
hdfs dfs -put "$scratch/probe.txt" "$root/demo/"
hdfs dfs -cat "$root/demo/probe.txt"
hdfs dfs -get "$root/demo/probe.txt" "$scratch/retrieved.txt"
cmp "$scratch/probe.txt" "$scratch/retrieved.txt"
# Demonstrate deletion only on the temporary demo directory created by this script.
hdfs dfs -rm -r "$root/demo"
hdfs dfs -ls -R "$root"
