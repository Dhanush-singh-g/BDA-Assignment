"""Inspect actual ZIP sizes without extracting the dataset."""
import argparse
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

from .archive import members, sha256


def inspect_archive(source, verify=False):
    path = Path(source).resolve(strict=True)
    with ZipFile(path) as archive:
        tables = members(archive)
        if verify:
            bad = archive.testzip()
            if bad:
                raise ValueError(f"ZIP CRC verification failed: {bad}")
        inventory = {name: {"csv_bytes": item.file_size, "compressed_bytes": item.compress_size}
                     for name, item in sorted(tables.items())}
    return {"archive": str(path), "zip_bytes": path.stat().st_size,
            "csv_uncompressed_bytes": sum(item["csv_bytes"] for item in inventory.values()),
            "source_sha256": sha256(path), "crc_verified": verify,
            "free_bytes_on_archive_disk": shutil.disk_usage(path.parent).free,
            "tables": inventory,
            "storage_note": "CSV expansion is not a complete working-storage estimate. Budget separately for MongoDB/indexes, prepared TSV/SQLite, and replicated HDFS/RCFile outputs."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--verify", action="store_true", help="Read all ZIP members and verify their CRCs")
    args = parser.parse_args()
    print(json.dumps(inspect_archive(args.archive, args.verify), indent=2))


if __name__ == "__main__":
    main()
