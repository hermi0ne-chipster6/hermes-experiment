#!/usr/bin/env python3
"""Strict, streaming SDK reuse provenance check. See docs/rebuild-provenance.md."""

import argparse
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tarfile

import yaml

BASE_SHA256 = "c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5"
NPM_SHA256 = "81c475d3425a3748007efdc80ebd2c747a44694627e2aab11999675536f9ec04"
NATIVE_SHA256 = "28f6bf3a8926288ffe79f415777256a37213c2d217cdab4ee81b225b096854bb"
FRIDA = "rea/node_modules/frida"
META = "meta/sdk.yaml"
HOOKS = "sdk/hooks/"
COMPAT = FRIDA + "/hermes-rea-compatibility.json"


def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalize(name):
    while name.startswith("./"):
        name = name[2:]
    name = name.rstrip("/")
    if name in ("", "."):
        return "."
    if name.startswith("/") or any(p in ("", ".", "..") for p in name.split("/")):
        raise ValueError(f"unsafe archive member name: {name!r}")
    return name


def inventory_stream(stream, capture=()):
    """Read headers and hash bytes, never extract or dereference any link."""
    entries, content = {}, {}
    with tarfile.open(fileobj=stream, mode="r|*") as archive:
        for member in archive:
            name = normalize(member.name)
            if name in entries:
                raise ValueError(f"duplicate archive member: {name}")
            kind = next((label for predicate, label in [
                (member.isfile, "file"), (member.isdir, "directory"),
                (member.issym, "symlink"), (member.islnk, "hardlink"),
                (member.ischr, "character"), (member.isblk, "block"),
                (member.isfifo, "fifo")] if predicate()), None)
            if kind is None:
                raise ValueError(f"unsupported archive type at {name}: {member.type!r}")
            # Effective paths/owners/sizes are captured separately. Times and
            # textual owner names are non-semantic packaging metadata. Preserve
            # every other PAX field, including ACLs, xattrs and capabilities.
            ignored = {"path", "linkpath", "size", "uid", "gid", "uname", "gname",
                       "mtime", "atime", "ctime"}
            entry = dict(type=kind, mode=member.mode, uid=member.uid, gid=member.gid,
                         size=member.size, link=member.linkname,
                         devmajor=member.devmajor, devminor=member.devminor,
                         pax={k: v for k, v in member.pax_headers.items() if k not in ignored})
            if member.isfile():
                h = hashlib.sha256()
                keep = name in capture or name.startswith(HOOKS)
                if keep and member.size > 8 * 1024 * 1024:
                    raise ValueError(f"oversized metadata/hook: {name}")
                chunks = []
                source = archive.extractfile(member)
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    h.update(chunk)
                    if keep:
                        chunks.append(chunk)
                entry["sha256"] = h.hexdigest()
                if keep:
                    content[name] = b"".join(chunks)
            entries[name] = entry
    return entries, content


def inventory(path, sdk=False, capture=()):
    if not sdk:
        with open(path, "rb") as stream:
            return inventory_stream(stream, capture)
    with subprocess.Popen(["zstd", "--decompress", "--stdout", "--", str(path)],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        try:
            result = inventory_stream(process.stdout, capture)
            # Consume trailing padding so zstd completes and validates its frame.
            while process.stdout.read(1024 * 1024):
                pass
            error = process.stderr.read().decode(errors="replace")
            if process.wait() != 0:
                raise ValueError(f"zstd failed for {path}: {error.strip()}")
            return result
        except BaseException:
            process.kill()
            process.wait()
            raise


def is_frida(name):
    return name == FRIDA or name.startswith(FRIDA + "/")


def compare_inventories(base, candidate):
    errors, changes = [], []
    for name in sorted(base.keys() | candidate.keys()):
        old, new = base.get(name), candidate.get(name)
        if old == new:
            continue
        fields = sorted(k for k in (old or {}).keys() | (new or {}).keys()
                        if (old or {}).get(k) != (new or {}).get(k))
        changes.append(dict(path=name, fields=fields,
                            action="added" if old is None else "removed" if new is None else "changed"))
        if is_frida(name):
            continue  # Independently checked against exact official inputs.
        if name == META or name.startswith(HOOKS):
            # Representation/content may change, but only for existing regular
            # files. Metadata semantics and source hook content checked later.
            if (old and new and old["type"] == new["type"] == "file"
                    and set(fields) <= {"sha256", "size", "mode"}
                    and (name != META or old["mode"] == new["mode"])):
                continue
        errors.append(f"unapproved {changes[-1]['action']}: {name} ({', '.join(fields)})")
    return errors, changes


def directory_record():
    return dict(type="directory", mode=0o755, uid=0, gid=0, size=0, link="",
                devmajor=0, devminor=0, pax={})


def expected_frida(npm, native, compatibility):
    expected = {}
    for name, entry in npm.items():
        if not name.startswith("package/") or entry["type"] != "file":
            raise ValueError(f"unexpected official npm member: {name}")
        expected[FRIDA + "/" + name[len("package/"):]] = entry
    if set(native) != {"build/frida_binding.node"}:
        raise ValueError("official native archive must contain exactly build/frida_binding.node")
    # Both full and reuse recipes deliberately install the shared addon 0644.
    # It is loaded by dlopen, not executed; preserve all other official fields.
    expected[FRIDA + "/build/frida_binding.node"] = dict(
        native["build/frida_binding.node"], mode=0o644)
    expected[COMPAT] = dict(type="file", mode=0o644, uid=0, gid=0,
                           size=len(compatibility), link="", devmajor=0, devminor=0,
                           pax={}, sha256=hashlib.sha256(compatibility).hexdigest())
    for name in list(expected):
        for parent in PurePosixPath(name).parents:
            parent = str(parent)
            if is_frida(parent):
                expected.setdefault(parent, directory_record())
    return expected


def validate_frida(candidate, expected):
    actual = {name: entry for name, entry in candidate.items() if is_frida(name)}
    errors = []
    for name in sorted(actual.keys() | expected.keys()):
        if actual.get(name) != expected.get(name):
            errors.append(f"Frida official-input mismatch: {name}; "
                          f"expected={expected.get(name)!r}; actual={actual.get(name)!r}")
    return errors


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate mapping keys instead of silently taking the last."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def metadata_semantics(old, new):
    """Allow only SDKcraft's independently regenerated, canonical UTC timestamp."""
    if not isinstance(old, dict) or not isinstance(new, dict):
        return ["meta/sdk.yaml must contain a mapping"], {}
    old, new = dict(old), dict(new)
    key = "sdkcraft-started-at"
    values = {"base": old.pop(key, None), "candidate": new.pop(key, None)}
    errors, parsed = [], {}
    for label, value in values.items():
        try:
            if not isinstance(value, str):
                raise ValueError("must be a string")
            instant = datetime.fromisoformat(value)
            if instant.utcoffset() != UTC.utcoffset(None) or instant.isoformat() != value:
                raise ValueError("must be canonical ISO 8601 with +00:00 UTC offset")
            parsed[label] = instant
        except (ValueError, TypeError) as error:
            errors.append(f"invalid {label} {key}: {error}")
    if len(parsed) == 2:
        if parsed["candidate"] < parsed["base"]:
            errors.append("candidate sdkcraft-started-at precedes immutable base")
        if parsed["candidate"] > datetime.now(UTC):
            errors.append("candidate sdkcraft-started-at is in the future")
    if json.dumps(old, sort_keys=True) != json.dumps(new, sort_keys=True):
        errors.append("meta/sdk.yaml semantic dictionary differs beyond sdkcraft-started-at")
    return errors, {"field": key, **values}


def validate_metadata(base_content, candidate_content, candidate, sdk_source, timestamp_proof=None):
    errors = []
    old = yaml.load(base_content[META], Loader=UniqueLoader)
    new = yaml.load(candidate_content[META], Loader=UniqueLoader)
    semantic_errors, timestamps = metadata_semantics(old, new)
    errors.extend(semantic_errors)
    if timestamp_proof is not None:
        timestamp_proof.update(timestamps)
    hooks = sdk_source / "hooks"
    source_names = {HOOKS + p.name for p in hooks.iterdir() if p.is_file() or p.is_symlink()}
    candidate_names = {name for name in candidate if name.startswith(HOOKS)}
    if source_names != candidate_names:
        errors.append(f"hook filenames differ from source: {sorted(source_names ^ candidate_names)}")
    for name in sorted(source_names & candidate_names):
        path = hooks / name[len(HOOKS):]
        mode = path.lstat().st_mode
        entry = candidate[name]
        if not stat.S_ISREG(mode) or not stat.S_IMODE(mode) & 0o111:
            errors.append(f"source hook is not an executable regular file: {path}")
        elif (entry["type"] != "file" or entry["mode"] != stat.S_IMODE(mode)
              or candidate_content.get(name) != path.read_bytes()):
            errors.append(f"packaged hook differs from current source bytes/mode: {name}")
    return errors


def run(args):
    report = {"schema_version": 1, "status": "failed", "errors": [], "inputs": {}}
    try:
        for label, path, wanted in [("base_sdk", args.base, BASE_SHA256),
                                    ("candidate_sdk", args.candidate, None),
                                    ("frida_npm", args.frida_npm, NPM_SHA256),
                                    ("frida_native", args.frida_native, NATIVE_SHA256)]:
            actual = digest(path)
            report["inputs"][label] = dict(path=str(path.resolve()), sha256=actual,
                                            bytes=path.stat().st_size)
            if wanted is not None and actual != wanted:
                raise ValueError(f"{label} SHA256 mismatch: expected {wanted}, got {actual}")
        compatibility_path = args.sdk_source / "dependencies/frida-compatibility.json"
        compatibility = compatibility_path.read_bytes()
        disclosure = json.loads(compatibility)
        if disclosure["candidate"]["version"] != "17.25.1":
            raise ValueError("source compatibility disclosure does not identify Frida 17.25.1")
        report["compatibility_source"] = dict(path=str(compatibility_path.resolve()),
                                             sha256=hashlib.sha256(compatibility).hexdigest())
        npm, npm_content = inventory(args.frida_npm, capture={"package/package.json"})
        package = json.loads(npm_content["package/package.json"])
        if package["name"] != "frida" or package["version"] != "17.25.1":
            raise ValueError("official npm package name/version mismatch")
        native, _ = inventory(args.frida_native)
        expected = expected_frida(npm, native, compatibility)
        print("Inventorying base SDK", file=sys.stderr, flush=True)
        base, base_content = inventory(args.base, sdk=True, capture={META})
        report["base_inventory"] = base
        print("Inventorying candidate SDK", file=sys.stderr, flush=True)
        candidate, candidate_content = inventory(args.candidate, sdk=True, capture={META, COMPAT})
        report["candidate_inventory"] = candidate
        report["expected_frida_inventory"] = expected
        errors, report["changes"] = compare_inventories(base, candidate)
        errors.extend(validate_frida(candidate, expected))
        report["metadata_build_timestamps"] = {}
        errors.extend(validate_metadata(base_content, candidate_content, candidate, args.sdk_source,
                                        report["metadata_build_timestamps"]))
        report["errors"] = errors
        report["status"] = "passed" if not errors else "failed"
    except Exception as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "report": str(args.report),
                      "errors": report["errors"]}, indent=2))
    return 0 if report["status"] == "passed" else 1

def self_test():
    import tempfile
    import unittest

    class Contract(unittest.TestCase):
        def test_comparator_exists(self):
            self.assertTrue(callable(globals().get("compare_inventories")),
                            "strict bidirectional comparator is not implemented")

        def test_bidirectional_and_each_attribute(self):
            entry = directory_record()
            self.assertEqual(compare_inventories({"x": entry}, {"x": entry})[0], [])
            for key in entry:
                altered = dict(entry, **{key: "different"})
                with self.subTest(key=key):
                    self.assertTrue(compare_inventories({"x": entry}, {"x": altered})[0])
            self.assertTrue(compare_inventories({"x": entry}, {})[0])
            self.assertTrue(compare_inventories({}, {"x": entry})[0])
            self.assertTrue(compare_inventories({}, {FRIDA + "-extra/x": entry})[0])

        def test_stream_hash_and_malformed_links(self):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w") as archive:
                item = tarfile.TarInfo("./file")
                item.size = 3
                item.pax_headers = {"SCHILY.xattr.security.capability": "test"}
                archive.addfile(item, io.BytesIO(b"abc"))
                link = tarfile.TarInfo("broken")
                link.type, link.linkname = tarfile.SYMTYPE, "../../absent"
                archive.addfile(link)
            buffer.seek(0)
            entries, _ = inventory_stream(buffer)
            self.assertEqual(entries["file"]["sha256"], hashlib.sha256(b"abc").hexdigest())
            self.assertEqual(entries["file"]["pax"], {"SCHILY.xattr.security.capability": "test"})
            self.assertEqual(entries["broken"]["link"], "../../absent")

        def test_unsafe_and_duplicate_names(self):
            for name in ("/absolute", "../escape", "x/../escape", "x//y"):
                with self.assertRaises(ValueError):
                    normalize(name)
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w") as archive:
                archive.addfile(tarfile.TarInfo("same"))
                archive.addfile(tarfile.TarInfo("./same"))
            buffer.seek(0)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                inventory_stream(buffer)

        def test_frida_exception_requires_exact_expected(self):
            expected = {FRIDA: directory_record()}
            self.assertEqual(validate_frida(expected, expected), [])
            self.assertTrue(validate_frida({}, expected))
            self.assertTrue(validate_frida({**expected, FRIDA + "/extra": directory_record()}, expected))
            altered = {FRIDA: dict(directory_record(), mode=0o777)}
            self.assertTrue(validate_frida(altered, expected))

        def test_duplicate_yaml_rejected(self):
            with self.assertRaisesRegex(ValueError, "duplicate"):
                yaml.load("name: a\nname: b\n", Loader=UniqueLoader)

        def test_metadata_and_hooks(self):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "hooks").mkdir()
                hook = root / "hooks/setup-base"
                hook.write_bytes(b"#!/bin/sh\ntrue\n")
                hook.chmod(0o755)
                name = HOOKS + "setup-base"
                record = dict(directory_record(), type="file")
                candidate = {name: record}
                old = {META: b"name: hermes-rea\nversion: 6.9.0\nplugs: {state: {}}\nsdkcraft-started-at: '2020-01-01T00:00:00+00:00'\n"}
                new = {META: b"version: 6.9.0\nplugs: {state: {}}\nname: hermes-rea\nsdkcraft-started-at: '2020-01-02T00:00:00+00:00'\n",
                       name: hook.read_bytes()}
                self.assertEqual(validate_metadata(old, new, candidate, root), [])
                for field in (b"name: other", b"version: 7.0.0", b"plugs: {}"):
                    bad = dict(new, **{META: field + b"\n"})
                    self.assertTrue(validate_metadata(old, bad, candidate, root))
                self.assertTrue(validate_metadata(old, dict(new, **{name: b"wrong"}), candidate, root))
                self.assertTrue(validate_metadata(old, new, {}, root))
                self.assertTrue(validate_metadata(old, new, {name: dict(record, mode=0o644)}, root))
                changed_owner = {name: dict(record, uid=1)}
                self.assertTrue(compare_inventories(candidate, changed_owner)[0])

        def test_only_generated_timestamp_may_change(self):
            key = "sdkcraft-started-at"
            base = {"name": "hermes-rea", key: "2020-01-01T00:00:00+00:00"}
            newer = {"name": "hermes-rea", key: "2020-01-02T00:00:00.123456+00:00"}
            errors, proof = metadata_semantics(base, newer)
            self.assertEqual(errors, [])
            self.assertEqual(proof["base"], base[key])
            self.assertEqual(proof["candidate"], newer[key])
            for value in (None, 123, "bad", "2020-01-02", "2020-01-02T00:00:00",
                          "2020-01-02T00:00:00Z", "2020-01-02T01:00:00+01:00",
                          "2019-12-31T23:59:59+00:00", "9999-01-01T00:00:00+00:00"):
                with self.subTest(value=value):
                    self.assertTrue(metadata_semantics(base, {**newer, key: value})[0])
            self.assertTrue(metadata_semantics(base, {"name": "hermes-rea"})[0])
            self.assertTrue(metadata_semantics(base, {**newer, "name": "other"})[0])
            self.assertTrue(metadata_semantics(base, {**newer, "extra": "unexpected"})[0])

        def test_hardlink_target_is_not_dereferenced(self):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w") as archive:
                link = tarfile.TarInfo("hard")
                link.type, link.linkname = tarfile.LNKTYPE, "absent"
                archive.addfile(link)
            buffer.seek(0)
            entries, _ = inventory_stream(buffer)
            self.assertEqual(entries["hard"]["type"], "hardlink")
            self.assertEqual(entries["hard"]["link"], "absent")
            changed = {"hard": dict(entries["hard"], link="different")}
            self.assertTrue(compare_inventories(entries, changed)[0])

        def test_zstd_stream_and_corruption(self):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode="w") as archive:
                archive.addfile(tarfile.TarInfo("empty"))
            compressed = subprocess.run(["zstd", "--compress", "--stdout"],
                                        input=buffer.getvalue(), capture_output=True, check=True).stdout
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "fixture.sdk"
                path.write_bytes(compressed)
                self.assertEqual(set(inventory(path, sdk=True)[0]), {"empty"})
                path.write_bytes(compressed[:-4])
                with self.assertRaises((ValueError, tarfile.TarError)):
                    inventory(path, sdk=True)

        def test_root_metadata_exclusion_preserves_nested_metadata(self):
            # Regression for the first reuse build: GNU tar's unanchored
            # --exclude=meta silently removed AJV schemas and Zig stdlib files.
            payloads = {
                META: b"name: hermes-rea\n",
                "rea/node_modules/ajv/dist/refs/json-schema-2020-12/meta/core.json": b"{}\n",
                "providers/ziglang/lib/std/meta/trailer_flags.zig": b"// fixture\n",
            }
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive_path = root / "base.tar"
                with tarfile.open(archive_path, "w") as archive:
                    for name, body in payloads.items():
                        item = tarfile.TarInfo(name)
                        item.size, item.mode = len(body), 0o644
                        archive.addfile(item, io.BytesIO(body))
                entries, _ = inventory(archive_path)
                wanted = {name: value for name, value in entries.items() if name != META}
                for anchored in (False, True):
                    target = root / ("anchored" if anchored else "unanchored")
                    target.mkdir()
                    subprocess.run(["tar", "--extract", "--file", str(archive_path),
                                    "--directory", str(target),
                                    *(["--anchored"] if anchored else []),
                                    "--exclude=meta"], check=True, capture_output=True)
                    self.assertFalse((target / META).exists())
                    actual = {name: dict(entry, sha256=digest(target / name))
                              for name, entry in wanted.items() if (target / name).is_file()}
                    errors, _ = compare_inventories(wanted, actual)
                    if anchored:
                        self.assertEqual(errors, [])
                        self.assertEqual(set(actual), set(wanted))
                    else:
                        self.assertEqual(len(errors), 2)
                        self.assertTrue(all("unapproved removed:" in e for e in errors))

        def test_binding_mode_follows_sdk_install_policy(self):
            binding = dict(directory_record(), type="file", mode=0o755,
                           sha256="native")
            expected = expected_frida({}, {"build/frida_binding.node": binding}, b"{}")
            self.assertEqual(expected[FRIDA + "/build/frida_binding.node"]["mode"], 0o644)
            self.assertEqual(binding["mode"], 0o755)

    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Contract))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        raise SystemExit(self_test())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--sdk-source", type=Path, required=True)
    parser.add_argument("--frida-npm", type=Path, required=True)
    parser.add_argument("--frida-native", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    raise SystemExit(run(parser.parse_args()))
