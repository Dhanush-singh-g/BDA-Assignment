# Local development cluster

This Docker Compose environment provides a master and two workers on **one
physical host**. It is for development; it does not satisfy the college's
three-system requirement. No Hadoop or Hive ports are published to the host;
run cluster clients inside `master`. MongoDB is separate, bound to loopback.

## Prerequisites and versions

- Linux containers, Docker Engine and Docker Compose v2.
- Allow roughly 12 GiB for the three containers plus MongoDB and the OS; more
  memory/storage is needed for the complete dataset. Use at least four CPU cores.
- Python 3.12+ and GnuPG on the host for preparing verified Apache tools.
- Java 8 (Temurin), Hadoop 2.10.2, Pig 0.17.0 and Hive 2.3.9 in shared read-only
  tool directories, mounted into Python 3.11 containers (including procps).

Pig/RCFile are legacy assignment requirements, so this teaching stack uses older
releases. Keep it on a private development network. Do not replace individual
versions without rerunning the cross-tool smoke checks.

## Prepare and start

From the repository root:

```bash
.venv/bin/python infra/prepare_tools.py
docker compose -f infra/compose.yaml up -d --no-build
docker compose -f infra/compose.yaml exec master bash scripts/verify_cluster.sh
```

The fetcher verifies Hadoop SHA-512, Hive SHA-256 and Pig's OpenPGP release
signature against Apache's published KEYS. It extracts verified archives and
exports the JDK from a pinned official image into `data/tools/`. Existing tool
directories are not overwritten. The historical Pig signing key is now expired;
the signature was created during its validity and GnuPG verifies it, with that
expiration note. Downloads are retained in ignored `infra/downloads/`.

The shared tools avoid repeated copies on cloud machines whose Docker daemon uses
the `vfs` storage driver. The Python image includes the `ps` utility used by Hive.
No image build or package installation inside containers
is required. A completed setup has `data/tools/READY.json`.

Both development workers share the host's physical disk; HDFS capacity reports
must not be added together to estimate free space on that host.

Startup initializes a NameNode only when its persisted `VERSION` is absent and
initializes the embedded Derby metastore only on first use. It does not format
an existing NameNode. HDFS defaults to replication 2. Each worker advertises
2.5 GiB of YARN memory and two virtual cores. Startup can take time; inspect
`docker compose ... logs` and files under `data/cluster/*/logs/` on failure.

Check Hive separately before creating tables:

```bash
docker compose -f infra/compose.yaml exec master \
  beeline -u jdbc:hive2://localhost:10000/default -n root -e 'SELECT 1;'
```

An open port or running container is not a readiness check. HDFS/YARN verification
must pass a job, and Hive must answer a query. Follow
[cluster workflow](cluster-workflow.md) from a shell inside the master for actual
assignment commands. Files in this checkout are mounted at `/project`.

## Stop and restart

```bash
docker compose -f infra/compose.yaml stop
docker compose -f infra/compose.yaml up -d --no-build
docker compose -f infra/compose.yaml exec master bash scripts/verify_cluster.sh
```

Service processes must restart after restoring an environment. Persistent HDFS
and metastore state lives in ignored `data/cluster/`, not the running processes.
Docker images may need pulling on another machine. Do not delete
these state directories to solve a startup problem without first preserving data.

This is an amd64 development configuration tested on the cloud host. Other
architectures and laptop resource limits require independent validation.
