"""Local, read-only dashboard for recorded Track B evidence."""
import argparse
import json
import statistics
from pathlib import Path
from flask import Flask, abort, jsonify, render_template, request
from .hive_benchmark import read_result

ROOT = Path(__file__).resolve().parent.parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def discover(root):
    found = {}
    for parent, pattern in ((root / 'data', 'realdev_*'), (root / 'results', '*')):
        for folder in sorted(parent.glob(pattern), reverse=True):
            if folder.is_symlink() or not folder.is_dir():
                continue
            if (folder / 'SUCCESS.json').is_file() or (folder / 'run.json').is_file():
                key = folder.relative_to(root).as_posix()
                found[key] = folder
    return found


def evidence(folder, root=ROOT):
    success = read(folder / 'SUCCESS.json') if (folder / 'SUCCESS.json').exists() else None
    context = read(folder / 'run.json') if (folder / 'run.json').exists() else {}
    hive_path = folder / 'hive/benchmark.json'
    hive = read(hive_path) if hive_path.exists() else {}
    manifest = hive.get('source_manifest', {})
    scope = success.get('scope') if success else context.get('dataset_kind', 'unclassified')
    completed = bool(success) or context.get('complete') is True
    if success:
        counts = success.get('counts', {})
        source_hash = success.get('parent_source_sha256', manifest.get('source_sha256', 'Unavailable'))
    else:
        counts = manifest.get('counts', {})
        source_hash = manifest.get('source_sha256', 'Unavailable')
    timings = []
    for query in ('nutrient_summary', 'protein_summary'):
        for table in ('nutrients_text', 'nutrients_rcfile'):
            values = [r['seconds'] for r in hive.get('runs', [])
                      if r['query'] == query and r['table'] == table and not r['warmup']]
            if values:
                timings.append(dict(query=query, table=table, median=statistics.median(values), runs=len(values)))
    rows = []
    execution = next(((i, r) for i, r in enumerate(hive.get('runs', []))
                      if r['query'] == 'nutrient_summary' and r['table'] == 'nutrients_text'), None)
    if execution:
        index, run = execution
        path = folder / 'hive' / f'{index:02d}-nutrient_summary-nutrients_text.tsv'
        for (kind, nutrient, unit), (count, total, mean) in read_result(path.read_text()).items():
            rows.append(dict(food_type=kind, nutrient_id=nutrient, unit=unit,
                             records=count, total=total, mean=mean))
    mongo_stats = []
    food_types = []
    mongo_folder = folder / 'mongo'
    if success and success.get('mongo_results'):
        candidate = (root / success['mongo_results']).resolve()
        if candidate.is_relative_to(root.resolve()):
            mongo_folder = candidate
    profile_path = mongo_folder / 'profile.json'
    if profile_path.is_file():
        profile = read(profile_path)
        if profile.get('source_sha256') == source_hash:
            for mode in ('collection_scan', 'indexed'):
                samples = [r for r in profile.get('profiles', []) if r['mode'] == mode]
                if samples:
                    mongo_stats.append(dict(mode=mode, runs=len(samples),
                        milliseconds=statistics.median(r['explain']['executionStats']['executionTimeMillis'] for r in samples),
                        documents=statistics.median(r['explain']['executionStats']['totalDocsExamined'] for r in samples)))
            food_path = mongo_folder / 'foods_by_type.jsonl'
            if food_path.exists():
                food_types = [json.loads(line) for line in food_path.read_text().splitlines() if line.strip()]
    return dict(mongo_stats=mongo_stats, food_types=food_types, scope=scope, complete=completed, hive_complete=hive.get('complete', False),
                source_sha256=source_hash, subset_sha256=success.get('subset_sha256') if success else None,
                counts=counts, tables=manifest.get('counts', {}), timings=timings,
                storage=hive.get('storage', {}), rows=rows,
                method=hive.get('method', 'No completed benchmark available'),
                topology=context.get('cluster_mode', 'single-host development containers'),
                recorded_at=hive.get('recorded_at', 'Unavailable'))


def create_app(root=ROOT):
    app = Flask(__name__)
    root = Path(root)

    @app.get('/')
    def home():
        runs = discover(root)
        selected = request.args.get('run') or next(iter(runs), None)
        if selected is not None and selected not in runs:
            abort(404)
        data = None
        error = None
        if selected:
            try:
                data = evidence(runs[selected], root)
            except (ValueError, KeyError, OSError, TypeError):
                error = 'The selected evidence is incomplete or malformed. Check the saved run files.'
        query = request.args.get('q', '').strip()[:100]
        if data:
            data['rows'] = [r for r in data['rows'] if query.lower() in
                            (r['food_type'] + ' ' + r['nutrient_id'] + ' ' + r['unit']).lower()]
        return render_template('dashboard.html', runs=runs, selected=selected,
                               data=data, error=error, query=query)

    @app.get('/api/evidence')
    def api():
        runs = discover(root)
        selected = request.args.get('run')
        if selected not in runs:
            abort(404)
        try:
            return jsonify(evidence(runs[selected], root))
        except (ValueError, KeyError, OSError, TypeError):
            return jsonify(error='Evidence incomplete or malformed'), 422

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    create_app().run(host='127.0.0.1', port=args.port, debug=False)
