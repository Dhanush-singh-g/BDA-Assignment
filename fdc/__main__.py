import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="USDA full-release Track B workflows")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("download", help="Download the complete October 2024 ZIP")
    fetch.add_argument("--output", default="data/raw/FoodData_Central_csv_2024-10-31.zip")
    prep = commands.add_parser("prepare", help="Prepare all food and nutrient rows for HDFS")
    prep.add_argument("--archive", required=True)
    prep.add_argument("--output", required=True, help="New output directory")
    ingest = commands.add_parser("mongo-import", help="Ingest every CSV into MongoDB")
    ingest.add_argument("--archive", required=True)
    ingest.add_argument("--database", default="fdc_202410")
    ingest.add_argument("--batch-size", type=int, default=1000)
    analytics = commands.add_parser("mongo-analytics", help="Build views, run aggregations, profile indexes")
    analytics.add_argument("--database", default="fdc_202410")
    analytics.add_argument("--output", required=True, help="New result directory")
    analytics.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.command == "download":
        from .download import download
        result = download(args.output)
    elif args.command == "prepare":
        from .prepare import prepare
        result = prepare(args.archive, args.output)
    elif args.command == "mongo-import":
        from .mongo import ingest
        result = ingest(args.archive, args.database, args.batch_size)
    else:
        from .mongo import analyze
        result = analyze(args.database, args.output, args.repeats)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
