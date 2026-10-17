"""Fixed, single-job laptop workflows for the local dashboard (Linux/WSL2)."""
import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

SOURCE_DATABASE = 'fdc_home202410'
ARCHIVE_NAME = 'FoodData_Central_csv_2024-10-31.zip'
ACTIONS = {'full_workflow', 'workflow', 'existing', 'start_mongo', 'start_cluster', 'stop_services'}
COMPOSE = ['docker', 'compose', '-f', 'infra/compose.yaml']



def full_archive(root):
    candidates = [Path(root) / 'data/raw' / ARCHIVE_NAME,
                  Path('/mnt/c/Users/dhanu/Downloads') / ARCHIVE_NAME]
    return next((p.resolve() for p in candidates if p.is_file()), None)


def run_path(name):
    return isinstance(name, str) and bool(re.fullmatch(r'(?:data/realdev_[0-9]+|results/[A-Za-z][A-Za-z0-9_]{0,40})', name))


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def exports(root):
    """Offer only existing, complete exports with matching saved MongoDB evidence."""
    found = {}
    for path in sorted((root / 'data').glob('*/subset.json'), reverse=True):
        try:
            folder = path.parent
            if folder.is_symlink() or not (folder / 'prepared/manifest.json').is_file():
                continue
            meta = read(path)
            if meta.get('dataset_kind') != 'development-subset' or not meta.get('complete'):
                continue
            prepared = read(folder / 'prepared/manifest.json')
            if prepared.get('parent_source_sha256') != meta['source_sha256']:
                continue
            for profile in sorted((root / 'results/mongo').glob('*/profile.json')):
                record = read(profile)
                if (record.get('dataset_kind') == 'development-subset' and
                        record['source_sha256'] == meta['source_sha256'] and
                        record['tables'] == meta['tables'] and record.get('selection') == meta.get('selection')):
                    key = folder.relative_to(root).as_posix()
                    found[key] = {'subset': key, 'mongo_results': profile.parent.relative_to(root).as_posix(),
                                  'foods': meta['tables']['food']}
                    break
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return found


class BusyError(Exception):
    pass


class JobManager:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.directory = self.root / 'data/ui_jobs'
        self.directory.mkdir(parents=True, exist_ok=True)

    def path(self, job_id):
        if not re.fullmatch(r'[a-f0-9]{32}', job_id):
            raise ValueError('Invalid job identifier')
        return self.directory / job_id

    def submit(self, payload):
        if not isinstance(payload, dict) or set(payload) - {'action', 'foods', 'export'}:
            raise ValueError('Unsupported job fields')
        action = payload.get('action')
        if not isinstance(action, str) or action not in ACTIONS:
            raise ValueError('Choose a supported action')
        spec = {'action': action}
        if action == 'workflow':
            size = payload.get('foods')
            if type(size) is not int or not 1 <= size <= 100000:
                raise ValueError('Choose 1–100,000 foods, or Entire dataset')
            spec.update(foods=size, source=SOURCE_DATABASE)
        if action == 'full_workflow':
            archive = full_archive(self.root)
            if archive is None:
                raise ValueError('Full ZIP not found. Copy the October 2024 ZIP to data/raw/ or keep it in your Windows Downloads folder.')
            spec.update(source=SOURCE_DATABASE, archive=str(archive), dataset_kind='full-release')
        if action == 'existing':
            name = payload.get('export')
            selected = exports(self.root).get(name) if isinstance(name, str) else None
            if not selected:
                raise ValueError('Select an existing export with matching MongoDB results')
            spec.update(selected)
        lock = (self.directory / 'active.lock').open('a+')
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise BusyError('Another dashboard job is running; wait for it to finish') from None
            if action != 'stop_services':
                for path in self.directory.glob('*/state.json'):
                    previous = read(path)
                    if previous.get('status') in {'queued', 'running', 'interrupted'} and not previous.get('recovered_at'):
                        raise BusyError('A previous worker was interrupted. Inspect logs, then use Stop project services before another job.')
            job_id = uuid.uuid4().hex
            folder = self.path(job_id)
            folder.mkdir()
            state = dict(id=job_id, status='queued', created_at=now(), spec=spec,
                         stages=[], error=None, result=None)
            write(folder / 'state.json', state)
            # The worker inherits the locked descriptor. Closing only our copy
            # keeps the lock held until the worker exits, even after Flask restarts.
            try:
                with (folder / 'worker.log').open('ab') as log:
                    subprocess.Popen([sys.executable, '-u', '-m', 'fdc.dashboard_jobs',
                                      '--root', str(self.root), '--worker', job_id,
                                      '--lock-fd', str(lock.fileno())], cwd=self.root,
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True, pass_fds=(lock.fileno(),))
            except OSError:
                state.update(status='failed', error='Unable to launch worker', finished_at=now())
                write(folder / 'state.json', state)
                raise
            return state
        finally:
            lock.close()

    def jobs(self):
        states = []
        lock = (self.directory / 'active.lock').open('a+')
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                active = False
            except BlockingIOError:
                active = True
            for path in sorted(self.directory.glob('*/state.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
                try:
                    state = read(path)
                    if not active and state['status'] in {'queued', 'running'}:
                        state.update(status='interrupted', error='Worker stopped before reporting completion; inspect logs before rerunning.')
                        write(path, state)
                    marker = path.parent / 'evidence.json'
                    if marker.exists():
                        evidence = read(marker).get('run_directory')
                        if run_path(evidence):
                            state['evidence'] = evidence
                            progress = self.root / evidence / 'hive/progress.json'
                            if progress.is_file():
                                recorded = read(progress)
                                state['hive_progress'] = {'completed': len(recorded.get('runs', [])),
                                                          'expected': 24 if state['spec']['action'] == 'full_workflow' else 8, 'complete': recorded.get('complete', False)}
                    if state.get('evidence', '').startswith('results/'):
                        context = self.root / state['evidence'] / 'run.json'
                        if context.is_file():
                            state['analysis_stages'] = read(context).get('stages', [])
                    from .theme_evidence import live_themes
                    state['themes'] = live_themes(self.root, state)
                    states.append(state)
                except (OSError, ValueError, KeyError):
                    continue
        finally:
            lock.close()
        return states

    def log(self, job_id):
        folder = self.path(job_id)
        if not (folder / 'state.json').is_file():
            raise FileNotFoundError(job_id)
        paths = [folder / 'worker.log']
        marker = folder / 'evidence.json'
        if marker.exists():
            name = read(marker).get('run_directory', '')
            if run_path(name):
                paths.append(self.root / name / 'cluster.log')
        chunks = []
        for path in paths:
            if path.exists():
                with path.open('rb') as stream:
                    stream.seek(max(0, path.stat().st_size - 18000))
                    chunks.append(path.name + '\n' + stream.read().decode('utf-8', errors='replace'))
        return '\n\n'.join(chunks)


class Worker:
    def __init__(self, root, job_id):
        self.root = Path(root)
        self.folder = self.root / 'data/ui_jobs' / job_id
        self.state = read(self.folder / 'state.json')
        self.spec = self.state['spec']

    def save(self):
        write(self.folder / 'state.json', self.state)

    def command(self, args, timeout=None, capture=False):
        # All arguments originate in fixed workflows; no shell or user command text.
        print('Running:', ' '.join(map(str, args)), flush=True)
        result = subprocess.run(list(map(str, args)), cwd=self.root, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE if capture else None,
                                stderr=subprocess.STDOUT if capture else None,
                                text=True, timeout=timeout, check=False)
        if capture and result.stdout:
            print(result.stdout, flush=True)
        result.check_returncode()
        return result.stdout if capture else None

    def stage(self, label, action):
        item = dict(name=label, status='running', started_at=now())
        self.state['stages'].append(item)
        self.save()
        print('\nStage:', label, flush=True)
        try:
            result = action()
            item['status'] = 'passed'
            return result
        except Exception:
            item['status'] = 'failed'
            raise
        finally:
            item['finished_at'] = now()
            self.save()

    def stop_mongo(self):
        listing = self.command(['docker', 'ps', '-a', '--filter', 'name=^/fdc-mongo-dev$',
                                '--format', '{{.Names}}'], timeout=20, capture=True)
        if 'fdc-mongo-dev' not in listing.splitlines():
            return
        owner = self.command(['docker', 'inspect', '--format', '{{index .Config.Labels "project"}}',
                              'fdc-mongo-dev'], timeout=20, capture=True)
        if owner.strip() != 'fdc-track-b':
            raise ValueError('Refusing to stop a MongoDB container not owned by this project')
        self.command(['docker', 'stop', 'fdc-mongo-dev'], timeout=60)

    def check_tools(self):
        if self.spec['action'] != 'stop_services' and not (self.root / 'data/tools/READY.json').is_file():
            raise ValueError('Install project tools first: bash scripts/install.sh')
        self.command(['docker', 'info', '--format', '{{.Driver}}'], timeout=20)

    def start_mongo(self):
        self.command(COMPOSE + ['stop'], timeout=90)
        self.command(['bash', 'scripts/start_mongo.sh'], timeout=120)

    def cluster(self):
        self.stop_mongo()
        self.command(COMPOSE + ['up', '-d', '--no-build'], timeout=120)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            try:
                self.command(COMPOSE + ['exec', '-T', 'master', 'hdfs', 'dfsadmin', '-safemode', 'wait'], timeout=20)
                report = self.command(COMPOSE + ['exec', '-T', 'master', 'hdfs', 'dfsadmin', '-report'], timeout=20, capture=True)
                nodes = self.command(COMPOSE + ['exec', '-T', 'master', 'yarn', 'node', '-list', '-states', 'RUNNING'], timeout=20, capture=True)
                live = re.search(r'Live datanodes \((\d+)\)', report)
                running = re.search(r'Total Nodes:\s*(\d+)', nodes)
                if not live or int(live[1]) < 2 or not running or int(running[1]) < 2:
                    raise ValueError('Waiting for two DataNodes and two YARN workers')
                self.command(COMPOSE + ['exec', '-T', 'master', 'beeline', '-u',
                    'jdbc:hive2://localhost:10000/default', '-n', 'root', '-e', 'SELECT 1;'], timeout=45)
                return
            except (subprocess.SubprocessError, ValueError) as error:
                print('Services not ready yet:', type(error).__name__, flush=True)
                time.sleep(5)
        raise TimeoutError('Cluster not ready after five minutes. Inspect worker.log and Docker logs.')

    def distributed(self, subset, mongo):
        self.stage('Start Hadoop and wait for workers / Hive', self.cluster)
        self.stage('Run and reconcile MapReduce, Pig and Hive', lambda: self.command([
            sys.executable, '-u', 'tests/real_subset_cluster.py', '--subset', subset,
            '--mongo-results', mongo, '--result-file', str(self.folder / 'evidence.json')]))
        evidence = read(self.folder / 'evidence.json')['run_directory']
        if not (self.root / evidence / 'SUCCESS.json').is_file():
            raise ValueError('No integration success evidence was generated')
        self.state['result'] = evidence

    def run(self):
        self.state.update(status='running', pid=os.getpid(), started_at=now())
        self.save()
        try:
            self.stage('Check installed tools and Docker', self.check_tools)
            action = self.spec['action']
            if action == 'start_mongo':
                self.stage('Stop Hadoop and start MongoDB', self.start_mongo)
            elif action == 'start_cluster':
                self.stage('Start Hadoop and wait for workers / Hive', self.cluster)
            elif action == 'stop_services':
                self.stage('Stop Hadoop services', lambda: self.command(COMPOSE + ['stop'], timeout=90))
                self.stage('Stop project MongoDB', self.stop_mongo)
                # A stopped worker can leave server-side work behind. Only a
                # successful explicit service stop clears that recovery block.
                for path in self.folder.parent.glob('*/state.json'):
                    if path.parent == self.folder:
                        continue
                    previous = read(path)
                    if previous.get('status') in {'queued', 'running', 'interrupted'}:
                        previous.update(status='interrupted', recovered_at=now())
                        write(path, previous)
            elif action == 'full_workflow':
                from .part1 import run_part1
                if shutil.disk_usage(self.root).free < 2 * 1024**3:
                    raise ValueError('Less than 2 GiB free; free space before running')
                self.stage('Start MongoDB for full-dataset analysis', self.start_mongo)
                run_id = 'fullui_' + self.state['id'][:20]
                result = 'results/' + run_id
                write(self.folder / 'evidence.json', {'run_directory': result})
                self.stage('Analyze and reconcile the entire dataset', lambda: run_part1(
                    self.spec['archive'], run_id, 'full-release', mode='docker', repeats=5,
                    reuse_database=SOURCE_DATABASE, before_cluster=self.cluster))
                self.state['result'] = result
            elif action == 'existing':
                self.distributed(self.spec['subset'], self.spec['mongo_results'])
            else:
                if shutil.disk_usage(self.root).free < 2 * 1024**3:
                    raise ValueError('Less than 2 GiB free on project filesystem; free space before running')
                tag = 'ui' + str(self.spec['foods']) + '_' + self.state['id'][:16]
                database = 'fdc_' + tag
                output = 'results/mongo/' + tag
                subset = 'data/' + tag
                self.state.update(database=database, mongo_results=output, export=subset)
                self.save()
                self.stage('Stop Hadoop and start MongoDB', self.start_mongo)
                self.stage('Copy linked food subset', lambda: self.command([sys.executable, '-u', '-m',
                    'fdc.dev_subset', '--source', self.spec['source'], '--destination', database,
                    '--foods', str(self.spec['foods'])]))
                self.stage('Run MongoDB analytics and index profiles', lambda: self.command([
                    sys.executable, '-u', '-m', 'fdc', 'mongo-analytics', '--database', database,
                    '--output', output, '--repeats', '5']))
                self.stage('Export the same subset for Hadoop', lambda: self.command([
                    sys.executable, '-u', '-m', 'fdc.export_dev', '--database', database, '--output', subset]))
                self.distributed(subset, output)
            self.state.update(status='succeeded', finished_at=now())
        except Exception as error:
            self.state.update(status='failed', finished_at=now(),
                              error=f'{type(error).__name__}: {error}')
            print(self.state['error'], flush=True)
        finally:
            self.save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--worker', required=True)
    parser.add_argument('--lock-fd', type=int, required=True)
    args = parser.parse_args()
    # Keep the inherited lock open for the worker lifetime, not for child jobs.
    os.set_inheritable(args.lock_fd, False)
    Worker(args.root, args.worker).run()
    os.close(args.lock_fd)
