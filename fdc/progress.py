"""Small atomic execution timeline shared by analytics and distributed jobs."""
import json
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

REQUIREMENTS = {
    'mongo_input': (1, 'Document ingestion / organization', 'Store CSV records in raw collections; verify complete input and row counts.'),
    'mongo_indexes': (1, 'Index creation', 'Create food-ID / nutrient-ID indexes and retain their definitions.'),
    'mongo_pipelines': (1, 'Aggregation pipelines', 'Run $match, $group, $project, $unwind and $facet.'),
    'mongo_profile': (1, 'executionStats profiling', 'Compare the same indexed and collection-scan query, including time and documents/keys examined.'),
    'cluster_verification': (2, 'HDFS / YARN readiness', 'Verify two workers and execute a sample YARN job.'),
    'hdfs_operations': (2, 'HDFS file operations', 'mkdir, put, get, cat and rm -r, with a byte-checked round trip.'),
    'mapreduce': (2, 'Python Streaming on YARN', 'Execute mapper/reducers and verify nutrient counts, sums and means.'),
    'pig': (3, 'Pig transformation', 'Load prepared source records, filter invalid/negative values and verify output counts.'),
    'hive_tables': (3, 'Hive Text + RCFile', 'Load the same Pig output into Text and gzip RCFile tables.'),
    'hive_benchmark': (3, 'Identical queries / performance', 'Verify equal HQL answers and measure time and logical/replicated storage.'),
}


def save_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, default=str) + '\n')
    temporary.replace(path)


@contextmanager
def operation(path, label, command=None):
    """Record actual work, including quiet commands, without estimating progress."""
    record = {'label': label, 'status': 'running',
              'started_at': datetime.now(timezone.utc).isoformat()}
    if command is not None:
        record['command'] = list(map(str, command))
    save_json(path, record)
    try:
        yield record
    except BaseException as error:
        record.update(status='failed', error_type=type(error).__name__)
        raise
    else:
        record['status'] = 'passed'
    finally:
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        save_json(path, record)


def tracked_run(path, args, *, display=None, timeout=None, check=False, **kwargs):
    """subprocess.run with a persisted current command and its real child PID."""
    shown = list(map(str, display if display is not None else args))
    with operation(path, ' '.join(shown), shown) as record:
        with subprocess.Popen(args, **kwargs) as process:
            record['pid'] = process.pid
            save_json(path, record)
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except BaseException:
                process.kill()
                process.communicate()
                raise
            result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
            record['returncode'] = result.returncode
            if check:
                result.check_returncode()
            return result


class Timeline:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {'version': 1, 'stages': []}

    def save(self):
        save_json(self.path, self.data)

    def operation(self, label):
        return operation(self.path.with_name('operation.json'), label)

    @contextmanager
    def stage(self, key):
        item = {'key': key, 'theme': REQUIREMENTS[key][0], 'name': REQUIREMENTS[key][1],
                'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat()}
        self.data['stages'].append(item)
        self.save()
        start = time.perf_counter()
        print(f"Theme {item['theme']} · {item['name']}: starting", flush=True)
        try:
            yield
        except Exception as error:
            item.update(status='failed', error_type=type(error).__name__)
            raise
        else:
            item['status'] = 'passed'
        finally:
            item['seconds'] = time.perf_counter() - start
            self.save()
            print(f"Theme {item['theme']} · {item['name']}: {item['status']}", flush=True)


def snapshot(folder, root, full=False):
    paths = {'pig': 'pig/clean_nutrients.pig', 'mapper': 'mapreduce/mapper.py',
             'reducer': 'mapreduce/reducer.py', 'hive_ddl': 'hive/tables.hql',
             'hdfs': 'fdc/part1.py' if full else 'scripts/hdfs_demo.sh', 'streaming': 'scripts/run_mapreduce.sh'}
    record = {key: {'path': path, 'text': (Path(root) / path).read_text()}
              for key, path in paths.items()}
    save_json(Path(folder) / 'programs.json', record)
