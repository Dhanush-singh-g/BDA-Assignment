"""Export only the existing linked development database as a portable CSV ZIP."""
import argparse
import csv
import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from .mongo import connect
from .prepare import prepare


def export(database, output):
    client, db = connect(database)
    try:
        meta = db.metadata.find_one({'_id': 'import', 'complete': True,
                                     'dataset_kind': 'development-subset'})
        if not meta:
            raise ValueError('A completed, labelled development subset is required')
        root = Path(output)
        root.mkdir(parents=True, exist_ok=False)
        archive = root / 'development.zip'
        with ZipFile(archive, 'x', ZIP_DEFLATED) as bundle:
            for table in ('food', 'food_nutrient', 'nutrient'):
                collection = db['raw_' + table]
                first = collection.find_one()
                if not first:
                    raise ValueError('Required subset table is empty: ' + table)
                fields = [key for key in first if key != '_id']
                count = 0
                with bundle.open(table + '.csv', 'w') as raw:
                    with io.TextIOWrapper(raw, encoding='utf-8', newline='') as stream:
                        writer = csv.DictWriter(stream, fields)
                        writer.writeheader()
                        for row in collection.find({}, {'_id': 0}).sort('_id', 1):
                            writer.writerow(row)
                            count += 1
                if count != meta['tables'][table]:
                    raise ValueError('Subset count changed: ' + table)
        (root / 'subset.json').write_text(json.dumps(meta, indent=2, default=str) + '\n')
        manifest = prepare(archive, root / 'prepared')
        manifest.update(dataset_kind='development-subset',
                        parent_source_sha256=meta['source_sha256'], selection=meta['selection'])
        (root / 'prepared/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps(manifest, indent=2))
    finally:
        client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    export(args.database, args.output)
