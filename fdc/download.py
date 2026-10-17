"""Download the entire release with TLS verification and a local integrity record."""

import json
import os
import shutil
import urllib.request
from pathlib import Path
from zipfile import ZipFile

from .archive import RELEASE, URL, members, sha256


def download(destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Archive already exists: {destination}; validate or reuse it")
    partial = destination.with_suffix(destination.suffix + ".part")
    if partial.exists():
        raise FileExistsError(f"Unfinished download exists: {partial}; inspect before removing")
    try:
        with urllib.request.urlopen(URL, timeout=120) as response, partial.open("xb") as output:
            length = int(response.headers.get("Content-Length", 0))
            if length and shutil.disk_usage(destination.parent).free < length + 256 * 1024**2:
                raise OSError("Insufficient free space for the complete archive")
            shutil.copyfileobj(response, output, length=8 * 1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        if length and partial.stat().st_size != length:
            raise OSError("Incomplete download: Content-Length does not match")
        with ZipFile(partial) as archive:
            tables = members(archive)
            bad = archive.testzip()
            if bad:
                raise ValueError(f"ZIP CRC validation failed: {bad}")
        record = {
            "release": RELEASE, "url": URL, "bytes": partial.stat().st_size,
            "sha256": sha256(partial), "tables": sorted(tables),
            "integrity": "HTTPS transport and ZIP CRC; SHA-256 is a local fingerprint, not a publisher signature",
        }
        partial.rename(destination)
        destination.with_suffix(".manifest.json").write_text(json.dumps(record, indent=2) + "\n")
        return record
    except Exception:
        # Keep the partial file for diagnosis; never mistake it for a ready archive.
        raise
