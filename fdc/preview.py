"""Add document previews to an existing analytical run without rerunning analysis."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from .mongo import capture_previews, connect


def add_previews(results, database=None):
    output = Path(results).resolve(strict=True)
    profile = json.loads((output / 'profile.json').read_text())
    recorded = profile.get('database')
    database = database or recorded
    if not database:
        raise ValueError('This older run did not record its database. Supply --database with the original analytical database.')
    if recorded and recorded != database:
        raise ValueError('Database differs from the saved analytical run')
    if (output / 'previews.json').exists():
        raise FileExistsError('Document previews already exist; existing evidence is kept')
    client, db = connect(database)
    try:
        manifest = db.metadata.find_one({'_id': 'import', 'complete': True})
        if not manifest or any(manifest.get(key) != profile.get(key) for key in ('source_sha256', 'tables', 'selection')):
            raise ValueError('Database source, counts or selection do not match this analytical run')
        # All database operations are reads. Only the new preview artifact is written.
        capture_previews(db, manifest, database, output, derived='foods' in db.list_collection_names())
        path = output / 'previews.json'
        record = json.loads(path.read_text())
        record.update(captured_at=datetime.now(timezone.utc).isoformat(),
                      capture_context='Current matching database; captured after the original analytical run')
        from .progress import save_json
        save_json(path, record)
        return {'previews': str(path), 'database': database, 'analysis_rerun': False}
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True, help='Existing MongoDB analytics output folder')
    parser.add_argument('--database', help='Original analytical database, required for older profiles without a name')
    args = parser.parse_args()
    print(json.dumps(add_previews(args.results, args.database), indent=2))


if __name__ == '__main__':
    main()
