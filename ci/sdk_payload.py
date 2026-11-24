"""Fingerprint the complete immutable SDK payload on the host or in its guest mount."""

import argparse
from collections import defaultdict
from hashlib import file_digest, sha256, sha3_384
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tarfile


def _tree_receipt(entries, regular_files):
    groups = defaultdict(list)
    for name, key in regular_files.items():
        groups[key].append(name)
    first_link = {key: min(names) for key, names in groups.items()}
    digest = sha256()
    for name, entry in sorted(entries.items()):
        representative = first_link[regular_files[name]] if name in regular_files else None
        record = json.dumps((name, entry, representative), separators=(',', ':'))
        digest.update(record.encode('ascii') + b'\n')
    metadata = entries.get('meta/sdk.yaml')
    return {'entries': len(entries), 'tree_sha256': digest.hexdigest(),
            'metadata_sha256': metadata[-1] if metadata and metadata[0] == 'file' else None}


def _archive_name(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError(f'Invalid archive path: {value!r}')
    return path.as_posix()


def archive_payload(archive):
    entries = {}
    regular_files = {}
    links = {}
    for member in archive:
        name = _archive_name(member.name)
        if name == '.' and member.isdir():
            continue  # LXD manages the wrapper directory for the mount.
        if name == '.' or name in entries or name in links:
            raise ValueError(f'Duplicate or invalid archive entry: {member.name!r}')
        attrs = member.mode & 0o7777, member.uid, member.gid
        if member.isfile():
            with archive.extractfile(member) as stream:
                digest = file_digest(stream, 'sha256').hexdigest()
            entries[name] = ('file', *attrs, member.size, digest)
            regular_files[name] = name
        elif member.isdir():
            entries[name] = ('directory', *attrs)
        elif member.issym():
            # Linux always presents ordinary symlinks with mode 0777. Older
            # SDKcraft archives can store a different mode in the tar header.
            entries[name] = ('symlink', 0o777, member.uid, member.gid, member.linkname)
        elif member.islnk():
            links[name] = _archive_name(member.linkname), attrs
        else:
            raise ValueError(f'Unsupported archive entry: {member.name!r}')
    for name, (target, attrs) in links.items():
        seen = {name}
        while target in links:
            if target in seen:
                raise ValueError(f'Archive hardlink cycle: {name!r}')
            seen.add(target)
            target = links[target][0]
        if target not in regular_files or entries[target][1:4] != attrs:
            raise ValueError(f'Invalid archive hardlink: {name!r}')
        entries[name] = entries[target]
        regular_files[name] = target
    return _tree_receipt(entries, regular_files)


def installed_payload(root):
    entries = {}
    regular_files = {}
    inodes = {}
    directories = [root]
    while directories:
        for path in directories.pop().iterdir():
            name = path.relative_to(root).as_posix()
            file = path.lstat()
            attrs = stat.S_IMODE(file.st_mode), file.st_uid, file.st_gid
            if stat.S_ISREG(file.st_mode):
                key = file.st_dev, file.st_ino
                if key not in inodes:
                    with path.open('rb') as stream:
                        digest = file_digest(stream, 'sha256').hexdigest()
                    inodes[key] = ('file', *attrs, file.st_size, digest)
                entries[name] = inodes[key]
                regular_files[name] = key
            elif stat.S_ISDIR(file.st_mode):
                entries[name] = ('directory', *attrs)
                directories.append(path)
            elif stat.S_ISLNK(file.st_mode):
                entries[name] = ('symlink', *attrs, os.readlink(path))
            else:
                raise ValueError(f'Unexpected installed SDK entry: {name!r}')
    return _tree_receipt(entries, regular_files)


def verify_mount(lines, root):
    matches = []
    for line in lines:
        columns = line.split()
        if columns[4] == root:
            matches.append(columns[5].split(','))
        elif columns[4].startswith(root + '/'):
            raise ValueError(f'Unexpected mount inside SDK: {columns[4]}')
    if len(matches) != 1 or 'ro' not in matches[0]:
        raise ValueError(f'Expected exactly one read-only SDK mount at {root}')


def _compressed_payload(path):
    with subprocess.Popen(['zstd', '--decompress', '--stdout', '--', str(path)], stdout=subprocess.PIPE) as decoder:
        try:
            with tarfile.open(fileobj=decoder.stdout, mode='r|') as archive:
                receipt = archive_payload(archive)
            while decoder.stdout.read(1024 * 1024):
                pass
        except BaseException:
            decoder.kill()
            raise
        if decoder.wait() != 0:
            raise ValueError(f'Cannot decode SDK archive: {path}')
    if not receipt['metadata_sha256']:
        raise ValueError(f'SDK archive has no regular meta/sdk.yaml: {path}')
    raw_sha256, raw_sha3 = sha256(), sha3_384()
    with path.open('rb') as archive:
        while block := archive.read(1024 * 1024):
            raw_sha256.update(block)
            raw_sha3.update(block)
    receipt['archive_sha256'] = raw_sha256.hexdigest()
    receipt['archive_sha3_384'] = raw_sha3.hexdigest()
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('archive', 'mounted'))
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    try:
        if args.kind == 'archive':
            receipt = _compressed_payload(args.path)
        else:
            verify_mount(Path('/proc/self/mountinfo').read_text().splitlines(), str(args.path))
            receipt = installed_payload(args.path)
    except (ValueError, OSError, tarfile.TarError) as error:
        parser.exit(1, f'SDK payload rejected: {error}\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
