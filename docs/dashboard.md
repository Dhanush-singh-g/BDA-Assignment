# Track B Part 2 — Flask dashboard

The practical extension displays saved evidence from the three core themes. It
runs without MongoDB, Hadoop, Pig or Hive services, so viewing results does not
compete with those services for laptop RAM. It does not submit cluster jobs or
change imported data.

## Run on Ubuntu / WSL2

From the project root:

```bash
git pull --ff-only origin main
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m fdc.dashboard
```

Flask prints its local listening address on port 5000. Open that address in your
Windows browser. Leave the terminal running; Ctrl+C stops the dashboard. If the
port is occupied, use `--port 5001`. The server binds to loopback, debug is off,
and this teaching development server is intended for a local demo.

You can stop the Hadoop cluster and MongoDB before viewing:

```bash
docker compose -f infra/compose.yaml stop
docker stop fdc-mongo-dev
```

The supplied fixture tests do not require either service:

```bash
.venv/bin/python -m unittest discover -s tests -p test_dashboard.py -v
```

## Data flow and features

`ZIP → MongoDB / prepared TSV → YARN / Pig / Hive → saved evidence → Flask → browser`

The run selector discovers `data/realdev_*/SUCCESS.json` and
`results/*/run.json`. It renders the recorded scope and completion status, not an
inferred claim of faculty acceptance. A full-release run remains physically
unverified unless separate college-machine evidence is supplied.

- Food-type counts and collection/index-scan median server timings from matching
  MongoDB evidence, with documents examined.
- Nutrient summary search by food type, nutrient ID or unit; observation counts,
  means and totals from the saved Hive result.
- Hive Text/RCFile median elapsed-time bars, excluding warmups; measured run counts
  and timing methodology stay visible. A single measured development run is not
  sufficient for final performance conclusions.
- Logical and replicated storage measurements, source and subset fingerprints,
  recording timestamp, and a JSON evidence endpoint.
- Empty/malformed evidence states; unknown run identifiers return 404. HTML values
  are escaped, and the application has no arbitrary file-download endpoint.

Nutrient IDs remain explicit; no unverified name/unit mapping is invented. Means
are observation averages, not dietary recommendations. Amounts across different
nutrients or units must not be combined. Missing MongoDB results are displayed as
unavailable, never replaced with fabricated timings.

## Part 2 report and demo

Describe the architecture above, result-file contract, filtering, scope labels,
and warmup exclusion in a separate Part 2 report section. Capture screenshots
from your actual laptop run: selected subset with provenance, MongoDB plans, Hive
timings/storage and nutrient search. Record the Git commit and selected run ID.

Validation performed during implementation: dashboard route/API tests for empty
state, traversal rejection, escaping, search, incomplete evidence, full-run scope,
and warmup exclusion; actual saved integration evidence also rendered through
Flask. Windows browser visual verification and your real 10,000-food screenshots
remain to be performed. No full-release benchmark or physical-cluster completion
is implied by the dashboard.
