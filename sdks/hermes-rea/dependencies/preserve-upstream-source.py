#!/usr/bin/env python3
"""Export every pinned Git blob, including recursive submodules, without history.

Git objects are read directly so checkout line-ending filters and export-ignore
attributes cannot alter or omit original tracked content. The manifest is kept
beside the source tree; only documented relative runtime links are added inside.
"""

import hashlib
import gzip
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile


def git(repository, *arguments):
    return subprocess.check_output(["git", "-C", str(repository), *arguments])


def main():
    source = Path(os.environ["CRAFT_PART_SRC"])
    # Some upstream test fixtures intentionally contain invalid symlink targets.
    # Craft's staging collision detector follows those links and raises e.g.
    # ENAMETOOLONG. Stage a deterministic archive, then materialize this exact
    # tree with the official override-prime hook after staging has completed.
    export_root = Path(os.environ["CRAFT_PART_BUILD"]) / "complete-source-export"
    if export_root.exists():
        shutil.rmtree(export_root)
    destination = export_root / "rea"
    install_root = Path(os.environ["CRAFT_PART_INSTALL"]) / "upstream"
    install_root.mkdir(parents=True, exist_ok=True)
    install_root.chmod(0o755)
    # Remove this part's former direct-tree output on incremental builds.
    legacy_tree = install_root / "rea"
    if legacy_tree.is_symlink():
        legacy_tree.unlink()
    elif legacy_tree.exists():
        shutil.rmtree(legacy_tree)
    config = json.loads((Path(os.environ["CRAFT_PROJECT_DIR"]) / "SOURCE.json").read_text())
    expected_commit = config["commit"]
    expected_submodules = {entry["path"]: entry for entry in config["completeSource"]["submodules"]}
    assert git(source, "rev-parse", "HEAD").decode().strip() == expected_commit
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    repositories = []

    def export(repository, prefix, commit, url):
        actual = git(repository, "rev-parse", "HEAD").decode().strip()
        assert actual == commit, f"Wrong checked-out submodule revision at {prefix}: {actual} != {commit}"
        entries = git(repository, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0")
        submodules = []
        count = 0
        batch = subprocess.Popen(["git", "-C", str(repository), "cat-file", "--batch"],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            for entry in entries:
                if not entry:
                    continue
                metadata, raw_path = entry.split(b"\t", 1)
                mode, kind, object_id = metadata.decode().split(" ")
                relative = PurePosixPath(os.fsdecode(raw_path))
                assert not relative.is_absolute() and ".git" not in relative.parts and ".." not in relative.parts
                full_relative = PurePosixPath(prefix) / relative
                if mode == "160000":
                    submodules.append((relative, full_relative, object_id))
                    continue
                assert kind == "blob" and mode in ("100644", "100755", "120000"), entry
                batch.stdin.write(object_id.encode() + b"\n")
                batch.stdin.flush()
                reply_id, reply_kind, size = batch.stdout.readline().decode().strip().split(" ")
                assert reply_id == object_id and reply_kind == "blob"
                content = batch.stdout.read(int(size))
                assert len(content) == int(size) and batch.stdout.read(1) == b"\n"
                target = destination / str(full_relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                # Each tracked path has one owner, and a previous export must agree.
                if target.is_symlink() or target.exists():
                    if mode == "120000":
                        assert target.is_symlink() and os.fsencode(os.readlink(target)) == content
                    else:
                        assert target.is_file() and not target.is_symlink() and target.read_bytes() == content
                elif mode == "120000":
                    target.symlink_to(os.fsdecode(content))
                else:
                    target.write_bytes(content)
                    target.chmod(0o755 if mode == "100755" else 0o644)
                files.append({"path": str(full_relative), "git_mode": mode, "git_object": object_id,
                              "kind": "symlink" if mode == "120000" else "file", "bytes": len(content),
                              "sha256": hashlib.sha256(content).hexdigest()})
                count += 1
        finally:
            batch.stdin.close()
            batch.stdout.close()
            assert batch.wait() == 0
        repositories.append({"path": prefix or ".", "url": url, "commit": commit, "file_count": count})
        for relative, full_relative, submodule_commit in submodules:
            path = str(full_relative)
            if not prefix:
                expected = expected_submodules[path]
                assert submodule_commit == expected["commit"], (path, submodule_commit)
                submodule_url = expected["url"]
            else:
                submodule_url = git(repository / str(relative), "remote", "get-url", "origin").decode().strip()
            export(repository / str(relative), path, submodule_commit, submodule_url)

    export(source, "", expected_commit, config["upstream"] + ".git")
    exported = {item["path"]: item["commit"] for item in repositories}
    assert all(exported.get(path) == entry["commit"] for path, entry in expected_submodules.items())
    runtime_links = [
        {"path": "dist", "target": "../../rea/node_modules/rea-agents/dist"},
        {"path": "node_modules", "target": "../../rea/node_modules"},
        {"path": "skills", "target": "../../rea/node_modules/rea-agents/skills"},
    ]
    for link in runtime_links:
        target = destination / link["path"]
        assert not any(item["path"] == link["path"] or item["path"].startswith(link["path"] + "/") for item in files)
        if target.is_symlink():
            assert os.readlink(target) == link["target"]
        else:
            assert not target.exists()
            target.symlink_to(link["target"])
    manifest = {"schema_version": 1, "upstream_commit": expected_commit,
                "source_root": "rea", "git_history_included": False,
                "repositories": sorted(repositories, key=lambda item: item["path"]),
                "files": sorted(files, key=lambda item: item["path"]), "runtime_links": runtime_links}
    manifest_path = destination.parent / "rea.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    manifest_path.chmod(0o644)
    destination.parent.chmod(0o755)
    for directory, _, _ in os.walk(destination, followlinks=False):
        Path(directory).chmod(0o755)
    # Independent filesystem readback verifies the exported bytes and link targets.
    for entry in files:
        path = destination / entry["path"]
        data = os.fsencode(os.readlink(path)) if entry["kind"] == "symlink" else path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], entry["path"]
    timestamp = int(git(source, "show", "-s", "--format=%ct", expected_commit).strip())

    def normalize(info):
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        info.mtime = timestamp
        info.pax_headers = {}
        return info

    archive_path = install_root / "rea.source.tar.gz"
    with archive_path.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT,
                              dereference=False) as archive:
                archive.add(destination, arcname="rea", filter=normalize)
    archive_path.chmod(0o644)
    archive_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path = install_root / "rea.source.tar.gz.sha256"
    checksum_path.write_text(f"{archive_hash}  rea.source.tar.gz\n")
    checksum_path.chmod(0o644)
    shutil.copyfile(manifest_path, install_root / manifest_path.name)
    (install_root / manifest_path.name).chmod(0o644)
    print(json.dumps({"upstream_commit": expected_commit, "repositories": len(repositories),
                      "tracked_files": len(files), "tracked_bytes": sum(entry["bytes"] for entry in files),
                      "manifest": "upstream/rea.manifest.json", "archive_sha256": archive_hash,
                      "verification": "all exported hashes match"}))


if __name__ == "__main__":
    main()
