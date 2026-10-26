"""Translate recorded artifacts into assignment requirements without rerunning jobs."""
import json
import re
import shlex
from pathlib import Path
from .progress import REQUIREMENTS

SOURCE_ROOT = Path(__file__).resolve().parent.parent
FULL_KEYS = {'mongo_full_import': 'mongo_input', 'cluster_verification': 'cluster_verification',
             'hdfs_file_operations': 'hdfs_operations', 'yarn_streaming': 'mapreduce',
             'pig_cleaning': 'pig', 'hive_tables': 'hive_tables', 'hive_benchmark': 'hive_benchmark'}
TITLES = {1: 'MongoDB processing and analytics', 2: 'HDFS and MapReduce on YARN', 3: 'Pig and Hive Text / RCFile'}


def read(path, default=None):
    if not Path(path).is_file():
        return default
    return json.loads(Path(path).read_text())


def inside(root, name):
    if not isinstance(name, str):
        return None
    path = (Path(root) / name).resolve()
    return path if path.is_relative_to(Path(root).resolve()) else None


def collect_statuses(folder, mongo):
    statuses = {}
    context = read(folder / 'run.json', {})
    for stage in context.get('stages', []):
        key = FULL_KEYS.get(stage['name'])
        if key:
            statuses[key] = stage['status']
    for path in (mongo / 'activity.json', folder / 'activity.json'):
        for stage in read(path, {}).get('stages', []):
            if stage.get('key') in REQUIREMENTS:
                statuses[stage['key']] = stage['status']
    return statuses


def cards(statuses, pending='not_recorded'):
    result = []
    for theme, title in TITLES.items():
        requirements = [{'key': k, 'label': label, 'description': desc, 'status': statuses.get(k, pending)}
                        for k, (number, label, desc) in REQUIREMENTS.items() if number == theme]
        values = [r['status'] for r in requirements]
        status = ('failed' if 'failed' in values else 'running' if 'running' in values else
                  'passed' if all(v in {'passed', 'reused'} for v in values) else
                  'incomplete' if any(v in {'passed', 'reused'} for v in values) else pending)
        result.append({'number': theme, 'title': title, 'status': status, 'requirements': requirements})
    return result


def live_themes(root, state):
    if state['spec']['action'] not in {'workflow', 'existing', 'full_workflow'}:
        return []
    statuses = {}
    mongo = inside(root, state.get('mongo_results') or state['spec'].get('mongo_results'))
    if state['spec']['action'] == 'existing' and mongo and (mongo / 'profile.json').is_file():
        statuses.update({key: 'reused' for key in REQUIREMENTS if key.startswith('mongo_')})
    for stage in state.get('stages', []):
        if stage['name'] == 'Copy linked food subset':
            statuses['mongo_input'] = stage['status']
    folder = inside(root, state.get('evidence'))
    if folder:
        if state['spec']['action'] == 'full_workflow':
            mongo = folder / 'mongo'
        statuses.update(collect_statuses(folder, mongo or folder / 'mongo'))
    elif mongo:
        for stage in read(mongo / 'activity.json', {}).get('stages', []):
            statuses[stage['key']] = stage['status']
    if state['spec']['action'] == 'existing':
        for key in REQUIREMENTS:
            if key.startswith('mongo_') and statuses.get(key) == 'passed':
                statuses[key] = 'reused'
    return cards(statuses, pending='pending')


def command_log(text, script):
    pattern = r'COMMAND[^\n]*' + re.escape(script) + r'[^\n]*\n(.*?)(?=\nCOMMAND|\Z)'
    match = re.search(pattern, text, re.S)
    return match[1] if match else ''


def source_programs(folder):
    archived = read(folder / 'programs.json', {})
    names = {'pig': 'pig/clean_nutrients.pig', 'mapper': 'mapreduce/mapper.py',
             'reducer': 'mapreduce/reducer.py', 'hive_ddl': 'hive/tables.hql',
             'hdfs': 'fdc/part1.py' if (folder / 'run.json').exists() else 'scripts/hdfs_demo.sh', 'streaming': 'scripts/run_mapreduce.sh'}
    return {key: {**(archived[key] if key in archived else
                    {'path': path, 'text': (SOURCE_ROOT / path).read_text()}),
                  'recorded': key in archived} for key, path in names.items()}


def mongo_examples(mongo, source_hash, profile=None):
    """Read archived examples without requiring a running MongoDB service."""
    import itertools
    record = read(mongo / 'previews.json', {})
    if (record.get('source_sha256') != source_hash or
            (profile and profile.get('database') and record.get('database') != profile['database'])):
        record = {}
    aggregates = {}
    for name in ('foods_by_type', 'nutrient_summary', 'overview'):
        path = mongo / (name + '.jsonl')
        if path.is_file():
            with path.open() as stream:
                aggregates[name] = [json.loads(line) for line in itertools.islice(stream, 5)]
    return {'documents': record, 'aggregations': aggregates}


def details(folder, root, mongo, profile, hive, source_hash):
    success = read(folder / 'SUCCESS.json', {})
    context = read(folder / 'run.json', {})
    reconciliation = read(folder / 'reconciliation.json', {})
    manifest = hive.get('source_manifest', {})
    counts = success.get('counts') or reconciliation.get('accounting', {})
    statuses = collect_statuses(folder, mongo)
    profile_ok = bool(profile and profile.get('source_sha256') == source_hash)
    input_record = read(mongo / 'input.json', {})
    input_ok = input_record.get('source_sha256') == source_hash
    input_record = profile if profile_ok else input_record if input_ok else {}
    if profile_ok:
        statuses.setdefault('mongo_input', 'passed' if profile.get('tables') else 'not_recorded')
        modes = {r.get('mode') for r in profile.get('profiles', [])}
        if modes >= {'indexed', 'collection_scan'}:
            statuses.setdefault('mongo_indexes', 'passed')
            statuses.setdefault('mongo_profile', 'passed')
        if all((mongo / (name + '.jsonl')).is_file() for name in ('foods_by_type', 'nutrient_summary', 'overview')):
            statuses.setdefault('mongo_pipelines', 'passed')
    log = (folder / 'cluster.log').read_text(errors='replace') if (folder / 'cluster.log').exists() else ''
    # Legacy success markers were written only after all checks. Keep their summary
    # evidence, but never invent per-step timestamps or job details.
    if success:
        if log:
            statuses.setdefault('cluster_verification', 'passed')
            statuses.setdefault('hdfs_operations', 'passed')
        if (folder / 'mapreduce.tsv').exists():
            statuses.setdefault('mapreduce', 'passed')
        if 'clean_rows' in counts:
            statuses.setdefault('pig', 'passed')
    formats = {r['table'] for r in hive.get('runs', [])}
    if hive.get('complete') and formats >= {'nutrients_text', 'nutrients_rcfile'}:
        statuses.setdefault('hive_tables', 'passed')
        statuses.setdefault('hive_benchmark', 'passed')
    definitions = read(mongo / 'pipelines.json') if (profile_ok or input_ok) else None
    if definitions is None:
        from .mongo import pipelines
        definitions = pipelines()
    mr_log = command_log(log, 'scripts/run_mapreduce.sh')
    jobs = list(dict.fromkeys(re.findall(r'(?:job|application)_[0-9]+_[0-9]+', mr_log)))
    samples = []
    path = folder / 'mapreduce.tsv'
    if path.exists():
        with path.open() as stream:
            for _, line in zip(range(10), stream):
                key, count, total, mean = line.rstrip('\n').split('\t')
                kind, nid = key.rsplit('|', 1)
                samples.append(dict(food_type=kind, nutrient_id=nid, records=int(count), total=float(total), mean=float(mean)))
    hdfs = success.get('hdfs') or context.get('hdfs_root')
    operations = []
    if hdfs:
        for verb, label, command in (
            ('mkdir', 'Create directories', f'hdfs dfs -mkdir -p {hdfs}/raw {hdfs}/prepared {hdfs}/demo'),
            ('put', 'Upload files', f'hdfs dfs -put <prepared-files> {hdfs}/prepared/'),
            ('cat', 'Read the round-trip probe', f'hdfs dfs -cat {hdfs}/demo/probe.txt'),
            ('get', 'Download and byte-check the probe', f'hdfs dfs -get {hdfs}/demo/probe.txt <temporary-folder>/retrieved.txt'),
            ('rm -r', 'Delete only this run’s temporary demo directory', f'hdfs dfs -rm -r {hdfs}/demo')):
            operations.append(dict(verb=verb,label=label,command=command,status=statuses.get('hdfs_operations','not_recorded')))
    storage = hive.get('storage', {})
    text_bytes = storage.get('nutrients_text', {}).get('logical_bytes')
    rc_bytes = storage.get('nutrients_rcfile', {}).get('logical_bytes')
    compression = None
    if text_bytes and rc_bytes and text_bytes > 0 and rc_bytes > 0:
        compression = dict(ratio=text_bytes/rc_bytes, change_percent=abs(1-rc_bytes/text_bytes)*100,
                           smaller=rc_bytes <= text_bytes, text_bytes=text_bytes, rcfile_bytes=rc_bytes)
    verify = command_log(log, 'scripts/verify_cluster.sh')
    live = re.search(r'Live datanodes \((\d+)\)', verify)
    running = re.search(r'Total Nodes:\s*(\d+)', verify)
    source_counts = manifest.get('counts', {})
    explain = []
    if profile_ok:
        for execution in profile.get('profiles', []):
            stats = execution['explain']['executionStats']
            explain.append(dict(mode=execution['mode'], iteration=execution['iteration'],
                returned=stats['nReturned'], documents=stats['totalDocsExamined'], keys=stats['totalKeysExamined'],
                milliseconds=stats['executionTimeMillis'], success=stats.get('executionSuccess',False)))
    operator_info = [('$match','Filter food types and usable nutrient values'),('$group','Count records and calculate sums/averages'),
                     ('$project','Choose and rename output fields'),('$unwind','Expand each food’s nutrient array'),
                     ('$facet','Calculate several overview summaries together')]
    from .presentation import commands, input_sample
    examples=mongo_examples(mongo, source_hash, input_record) if (profile_ok or input_ok) else {'documents':{},'aggregations':{}}
    database=input_record.get('database') or examples['documents'].get('database')
    hive_database=success.get('hive_database') or ('fdc_'+context['run_id'] if context.get('run_id') else None)
    verify_commands=commands(database,hdfs,hive_database,native=context.get('deployment_kind','').startswith('cluster-client'),pipeline_definitions=definitions)
    return dict(verify_commands=verify_commands, input_sample=input_sample(folder,root,context,success,source_hash), mongo_examples=examples, themes=cards(statuses), timeline_recorded=(folder/'activity.json').is_file() or bool(context),
        collections=input_record.get('tables',{}), source_import=input_record.get('source_import',{}),
        database=input_record.get('database'),
        preview_command='.venv/bin/python -m fdc.preview --results '+shlex.quote(mongo.relative_to(Path(root)).as_posix())+(' --database '+shlex.quote(input_record['database']) if input_record.get('database') else ''),
        indexes=profile.get('indexes',read(mongo / 'indexes.json',{})) if (profile_ok or input_ok) else {}, operators=operator_info,
        pipelines=json.dumps(definitions,indent=2), pipelines_recorded=(profile_ok or input_ok) and (mongo/'pipelines.json').is_file(),
        explain=explain, explain_json=json.dumps(profile.get('profiles',[]) if profile_ok else [],indent=2),
        shell_query=('db.raw_food.find('+json.dumps(profile.get('query',{}))+').hint("idx_fdc_id").explain("executionStats")') if profile_ok else 'Query not recorded for this run.',
        hdfs=hdfs, operations=operations, jobs=jobs, mr_samples=samples,
        live_datanodes=int(live[1]) if live else None, running_workers=int(running[1]) if running else None,
        software={'MongoDB':profile.get('mongodb_version') if profile_ok else None,
                  'Hadoop client':(re.search(r'Hadoop ([0-9][^\s]+)',verify)[1] if re.search(r'Hadoop ([0-9][^\s]+)',verify) else None)},
        worker_names=list(dict.fromkeys(re.findall(r'Hostname:\s*(\S+)',verify))),
        pig_input=counts.get('prepared_rows',source_counts.get('written')),
        pig_output=counts.get('clean_rows',read(folder/'pig.json',{}).get('output_rows')),
        negative_filtered=counts.get('negative_filtered'), rejected=source_counts.get('rejected'),
        compression=compression, query_equal=hive.get('complete',False) and formats >= {'nutrients_text','nutrients_rcfile'},
        queries=hive.get('queries',{}), programs=source_programs(folder),
        reconciliation_passed=bool(success) or reconciliation.get('computational_checks')=='passed')
