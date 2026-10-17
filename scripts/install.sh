#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert sys.version_info >= (3,12), "Setup requires Python 3.12+"'
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
if [[ ! -f data/tools/READY.json ]]; then
  .venv/bin/python infra/prepare_tools.py
fi
docker pull mongo:7.0.16@sha256:c630c59342c1493d50345136df2af14a76b9e827dd5316bfabee07a0880a5f3a
docker pull python:3.11-bookworm@sha256:5887f265d8d44d8b4734d3658b21d668edf5aaf92e4945bc0c984afbfab105d3
echo 'Dependencies prepared. Start services separately; see docs/TECHNICAL-REFERENCE.md.'
