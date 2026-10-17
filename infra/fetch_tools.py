"""Fetch the pinned legacy teaching stack; verify before Docker can consume it."""
import hashlib
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parent / "downloads"


def fetch(url, path):
    if path.exists():
        return
    partial = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as source, partial.open("wb") as target:
        shutil.copyfileobj(source, target, 8 * 1024 * 1024)
    partial.rename(path)


def main():
    DEST.mkdir(exist_ok=True)
    items = [
        ("hadoop/common/hadoop-2.10.2", "hadoop-2.10.2.tar.gz", "sha512"),
        ("hive/hive-2.3.9", "apache-hive-2.3.9-bin.tar.gz", "sha256"),
        ("pig/pig-0.17.0", "pig-0.17.0.tar.gz", None),
    ]
    for directory, filename, algorithm in items:
        url = f"https://archive.apache.org/dist/{directory}/{filename}"
        target = DEST / filename
        fetch(url, target)
        if algorithm:
            checksum = DEST / (filename + "." + algorithm)
            fetch(url + "." + algorithm, checksum)
            length = hashlib.new(algorithm).digest_size * 2
            expected = re.findall(r"(?<![a-fA-F0-9])[a-fA-F0-9]{" + str(length) + r"}(?![a-fA-F0-9])", checksum.read_text())
            digest = hashlib.new(algorithm)
            with target.open("rb") as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                    digest.update(block)
            if len(expected) != 1 or digest.hexdigest() != expected[0].lower():
                raise ValueError(f"{filename}: checksum verification failed")
        else:
            # Pig publishes an MD5 and an OpenPGP signature. Use the signature.
            signature = DEST / (filename + ".asc")
            keys = DEST / "PIG_KEYS"
            fetch(url + ".asc", signature)
            fetch("https://archive.apache.org/dist/pig/KEYS", keys)
            with tempfile.TemporaryDirectory() as keyring:
                subprocess.run(["gpg", "--homedir", keyring, "--batch", "--import", str(keys)],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["gpg", "--homedir", keyring, "--batch", "--verify", str(signature), str(target)], check=True)
        print(f"Verified {filename}", flush=True)


if __name__ == "__main__":
    main()
