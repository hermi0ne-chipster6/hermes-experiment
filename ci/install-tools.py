"""Download checksum-pinned CI executables; never run archive install scripts."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tarfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    for name, entry in json.loads((ROOT/'ci/tools.json').read_text()).items():
        with urlopen(Request(entry['url'], headers={'User-Agent':'hermes-ci-tools'}), timeout=60) as response:
            payload = response.read(64*1024*1024+1)
        if len(payload) > 64*1024*1024 or hashlib.sha256(payload).hexdigest() != entry['sha256']:
            raise ValueError('CI tool checksum mismatch: '+name)
        with tarfile.open(fileobj=BytesIO(payload), mode='r:gz') as archive:
            member = archive.getmember(name)
            if not member.isfile() or member.size > 64*1024*1024:
                raise ValueError('invalid CI tool archive member: '+name)
            destination = args.directory/name
            destination.write_bytes(archive.extractfile(member).read())
            destination.chmod(0o755)
        print(name+': checksum verified')


if __name__ == '__main__':
    main()
