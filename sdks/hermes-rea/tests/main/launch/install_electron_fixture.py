#!/usr/bin/env python3
"""Fetch a checksum-verified test-only Electron target, never an SDK dependency."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

VERSION = "45.3.3"
ARCHIVE = f"electron-v{VERSION}-linux-x64.zip"
BASE = f"https://github.com/electron/electron/releases/download/v{VERSION}"
SHA256 = "0a63ce0e2b6a69d6ced7194949934b8414a6dadeca82910f88dc8720a1433269"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    sums = urllib.request.urlopen(BASE + "/SHASUMS256.txt", timeout=60).read().decode()
    wanted = next(line.split()[0] for line in sums.splitlines() if line.split()[-1].lstrip("*") == ARCHIVE)
    assert wanted == SHA256, "Published fixture checksum differs from the reviewed pin"
    archive = root / ARCHIVE
    try:
        urllib.request.urlretrieve(BASE + "/" + ARCHIVE, archive)
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        assert actual == wanted, f"Electron fixture checksum mismatch: {actual} != {wanted}"
        with zipfile.ZipFile(archive) as zipped:
            for item in zipped.infolist():
                target = (root / item.filename).resolve()
                assert target.is_relative_to(root), "Unsafe archive path"
                zipped.extract(item, root)
                mode = item.external_attr >> 16
                if mode and not item.is_dir():
                    target.chmod(mode & 0o777)
        (root / "fixture-provenance.json").write_text(json.dumps({"version": VERSION, "url": BASE + "/" + ARCHIVE,
            "sha256": actual, "checksum_source": BASE + "/SHASUMS256.txt", "scope": "Test-only caller-owned Electron application runtime"}, indent=2) + "\n")
        print(json.dumps({"version": VERSION, "sha256": actual, "executable": str(root / "electron")}))
    finally:
        archive.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
