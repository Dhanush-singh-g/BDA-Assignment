"""Prepare shared tool files instead of duplicating full tools into every container."""
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

from fetch_tools import DEST, main as fetch_verified

ROOT = Path(__file__).resolve().parent.parent
JAVA_IMAGE = "eclipse-temurin:8-jdk-jammy@sha256:a42a161e0edc7f0d3815bcfa22ce6d969fb48f69d0d17d4a1affd9800b455385"


def main():
    tools = ROOT / "data/tools"
    if tools.exists():
        raise FileExistsError("data/tools exists; inspect it before replacing tools")
    fetch_verified()
    tools.mkdir(parents=True)
    for filename, dirname, name in (
        ("hadoop-2.10.2.tar.gz", "hadoop-2.10.2", "hadoop"),
        ("apache-hive-2.3.9-bin.tar.gz", "apache-hive-2.3.9-bin", "hive"),
        ("pig-0.17.0.tar.gz", "pig-0.17.0", "pig"),
    ):
        with tarfile.open(DEST / filename) as archive:
            archive.extractall(tools, filter="data")
        (tools / dirname).rename(tools / name)
    subprocess.run(["docker", "pull", JAVA_IMAGE], check=True)
    name = "fdc-java-export"
    subprocess.run(["docker", "create", "--name", name, "--label", "project=fdc-track-b", JAVA_IMAGE], check=True)
    try:
        (tools / "java").mkdir()
        subprocess.run(["docker", "cp", name + ":/opt/java/openjdk/.", str(tools / "java")], check=True)
    finally:
        subprocess.run(["docker", "rm", name], check=True)
    for source in (ROOT / "infra/hadoop").iterdir():
        shutil.copy2(source, tools / "hadoop/etc/hadoop" / source.name)
    shutil.copy2(ROOT / "infra/hive-site.xml", tools / "hive/conf/hive-site.xml")
    (tools / "READY.json").write_text(json.dumps({
        "java_image": JAVA_IMAGE, "hadoop": "2.10.2", "pig": "0.17.0", "hive": "2.3.9"
    }, indent=2) + "\n")
    print("Shared verified tools prepared in data/tools")


if __name__ == "__main__":
    main()
