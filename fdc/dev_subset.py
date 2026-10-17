"""Create a labelled, linked MongoDB development subset from an existing import."""
import argparse
import json
from datetime import datetime, timezone
from .mongo import connect


def create(source, destination, limit):
    if source == destination or limit < 1 or limit > 100000:
        raise ValueError('Use separate databases and 1–100000 foods')
    client, src = connect(source)
    try:
        _, dst = client, client[destination]
        # Apply the same dedicated-database validation as all other commands.
        validator, _ = connect(destination)
        validator.close()
        manifest = src.metadata.find_one({'_id': 'import', 'complete': True})
        if not manifest:
            raise ValueError('Source must have a completed import')
        if dst.list_collection_names():
            raise ValueError('Destination must be empty; use a new database name')
        meta = {'_id': 'import', 'complete': False, 'release': manifest['release'],
                'source_sha256': manifest['source_sha256'],
                'dataset_kind': 'development-subset', 'source_database': source,
                'selection': {'method': 'First foods by source row ordinal; not representative sampling',
                              'food_limit': limit, 'linked_nutrients': True},
                'created_at': datetime.now(timezone.utc).isoformat(), 'tables': {}}
        dst.metadata.insert_one(meta)
        foods = list(src.raw_food.find().sort('_id', 1).limit(limit))
        if not foods:
            raise ValueError('Source has no foods')
        def copy(name, documents):
            dst.create_collection(name)
            batch = []
            count = 0
            for document in documents:
                batch.append(document)
                if len(batch) == 1000:
                    dst[name].insert_many(batch)
                    count += len(batch)
                    batch = []
            if batch:
                dst[name].insert_many(batch)
                count += len(batch)
            meta['tables'][name.removeprefix('raw_')] = count
            print(f'Copied {name}: {count} rows', flush=True)
        copy('raw_food', foods)
        ids = [food['fdc_id'] for food in foods]
        copy('raw_food_nutrient', src.raw_food_nutrient.find({'fdc_id': {'$in': ids}}))
        copy('raw_nutrient', src.raw_nutrient.find())
        meta['complete'] = True
        dst.metadata.replace_one({'_id': 'import'}, meta)
        print(json.dumps(meta, indent=2))
    finally:
        client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--foods', type=int, default=10000)
    args = parser.parse_args()
    create(args.source, args.destination, args.foods)
