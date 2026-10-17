"""Package project source only, excluding datasets, results, databases and credentials."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent


def package(output):
    files = [ROOT / name for name in ("README.md", "requirements.txt", ".gitignore")]
    for name in ("fdc", "hadoop", "hive", "infra", "mapreduce", "pig", "scripts", "tests", "docs"):
        for path in sorted((ROOT / name).rglob("*")):
            relative = path.relative_to(ROOT / name)
            if any(part in {"downloads", "__pycache__"} or part.startswith(".") for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f"Inspect symlink before packaging: {path.relative_to(ROOT)}")
            if path.is_file() and (path.suffix in {".py", ".java", ".sh", ".md", ".xml", ".yaml", ".hql", ".pig", ".txt", ".html"}
                                   or path.name in {"workers", "slaves"}):
                files.append(path)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, "BDA-Assignment/" + path.relative_to(ROOT).as_posix())
        archive.writestr("BDA-Assignment/SOURCE_FILES.json", json.dumps(manifest, indent=2) + "\n")
    return {"source_bundle": str(output), "files": len(files), "bytes": output.stat().st_size,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "dist/BDA-Assignment-Part1-source.zip"))
    args = parser.parse_args()
    print(json.dumps(package(args.output), indent=2))


if __name__ == "__main__":
    main()
