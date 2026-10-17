"""Read CSV members without extracting or loading the ZIP into memory."""

import csv
import hashlib
import io
from contextlib import contextmanager
from pathlib import Path
from zipfile import ZipFile

RELEASE = "2024-10-31"
URL = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_csv_2024-10-31.zip"

# Descriptions and ingredients in branded-food rows can exceed Python's default.
csv.field_size_limit(64 * 1024 * 1024)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def members(archive):
    """Reject ambiguous basenames rather than silently choosing a table."""
    result = {}
    for item in archive.infolist():
        if item.is_dir() or not item.filename.lower().endswith(".csv"):
            continue
        name = Path(item.filename).stem
        if name in result:
            raise ValueError(f"Duplicate CSV table: {name}")
        result[name] = item
    if not result:
        raise ValueError("The archive contains no CSV tables")
    return result


@contextmanager
def rows(archive: ZipFile, member):
    with archive.open(member) as binary:
        with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as text:
            reader = csv.DictReader(text)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError(f"Missing or duplicate CSV headers: {member.filename}")
            yield reader


def checked_rows(reader):
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"Malformed CSV record at physical line {reader.line_num}")
        yield row
