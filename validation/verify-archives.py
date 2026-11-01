"""Verify final SDK payloads against the custom sources that were reviewed."""
from pathlib import Path
import hashlib
import json
import tarfile

ROOT=Path(__file__).resolve().parents[1]
results={}
for role in ('hermes-experiment','hermes-execution','hermes-rea'):
    project=ROOT/'sdks'/role
    archive_path=project/f'{role}_amd64_ubuntu@26.04.sdk'
    expected={}
    for directory in ('assets','services'):
        source=project/directory
        if source.is_dir():
            for file in source.rglob('*'):
                if not file.is_file() or '__pycache__' in file.parts:continue
                target=file.relative_to(source).as_posix()
                if role=='hermes-experiment' and target=='bootstrap/hermes':target='bin/hermes'
                expected[target]=file.read_bytes()
    for file in (project/'hooks').glob('*'):
        if file.is_file():expected['sdk/hooks/'+file.name]=file.read_bytes()
    matched=set()
    unexpected=[]
    with tarfile.open(archive_path,'r|zst') as archive:
        for member in archive:
            if member.name in expected:
                assert member.isfile(),f'{role}: expected regular source {member.name}'
                assert archive.extractfile(member).read()==expected[member.name],f'{role}: stale payload {member.name}'
                matched.add(member.name)
            if '.spread-reuse.yaml' in member.name or member.name.endswith('.sdk'):
                unexpected.append(member.name)
    assert matched==set(expected),f'{role}: missing sources {set(expected)-matched}'
    assert not unexpected,f'{role}: generated SDK/Spread state inside payload'
    digest=hashlib.sha256()
    with archive_path.open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):digest.update(block)
    cache=Path('/home/codex/.local/share/workshop/try')/role/archive_path.name
    cached_digest=hashlib.sha256()
    with cache.open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):cached_digest.update(block)
    assert cached_digest.hexdigest()==digest.hexdigest(),f'{role}: try cache differs from built archive'
    results[role]={'custom_source_files_matched':len(matched),'generated_sdk_or_spread_files':unexpected,
                   'sha256':digest.hexdigest(),'bytes':archive_path.stat().st_size,
                   'artifact':str(archive_path.relative_to(ROOT)), 'try_cache_matches':True}
path=ROOT/'reports/artifacts.json'
path.write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
