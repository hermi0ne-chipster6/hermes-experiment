#!/usr/bin/env python3
"""Prepare an official SDKcraft build reusing one verified complete SDK payload.

The normal sdkcraft.yaml remains the full source recipe. This generated context
reuses unchanged build products, replacing only the explicitly pinned Frida
provider. Mandatory artifact comparison and clean installation are separate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import yaml

BASE_SHA256 = 'c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-sdk', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    base = args.base_sdk.resolve(strict=True)
    assert digest(base) == BASE_SHA256, 'Only the verified complete build may be reused'
    output = args.output.resolve()
    assert not output.exists(), 'Refuse to overwrite an existing build context'
    config = yaml.safe_load((source / 'sdkcraft.yaml').read_text())
    assert config['name'] == 'hermes-rea' and config['adopt-info'] == 'rea'
    assert (source / 'VERSION').read_text().strip() == '6.9.0'
    original_parts = config['parts']
    output.mkdir(mode=0o755, parents=True)
    (output / 'inputs').mkdir()
    os.link(base, output / 'inputs/base.sdk')
    shutil.copytree(source / 'hooks', output / 'hooks')
    (output / 'dependencies').mkdir()
    shutil.copy2(source / 'dependencies/frida-compatibility.json', output / 'dependencies/frida-compatibility.json')
    shutil.copy2(source / 'VERSION', output / 'VERSION')
    config['parts'] = {
        'rea': {
            'plugin': 'nil', 'source': 'inputs/base.sdk', 'source-type': 'file',
            'source-checksum': 'sha256/' + BASE_SHA256,
            'override-build': """craftctl set version="$(cat "$CRAFT_PROJECT_DIR/VERSION")"
printf '%s  %s\n' c7373502e97f32c34be99ba7fd92e7ea5832caf31121aa79a747badd27cf22c5 "$CRAFT_PART_SRC/base.sdk" | sha256sum --check
# Exclude the intentionally malformed upstream link fixtures until prime.
# Regenerate SDKcraft metadata/hooks; replace the complete matched Frida module.
tar --extract --zstd --file="$CRAFT_PART_SRC/base.sdk" --directory="$CRAFT_PART_INSTALL" --numeric-owner --same-owner --same-permissions --xattrs --xattrs-include='*' --anchored --exclude=meta --exclude=sdk/hooks --exclude=upstream/rea --exclude=rea/node_modules/frida
""",
            'override-prime': """craftctl default
cd "$CRAFT_PRIME/upstream"
sha256sum --check rea.source.tar.gz.sha256
rm -rf -- "$CRAFT_PRIME/upstream/rea"
tar --extract --gzip --file=rea.source.tar.gz --numeric-owner --same-owner --same-permissions
""",
        },
        'frida-runtime': original_parts['frida-runtime'],
        'frida-native': original_parts['frida-native'],
    }
    # The native module's original part requires the unchanged Node runtime,
    # which is now part of the verified base payload staged by its rea dependency.
    assert config['parts']['frida-runtime']['after'] == ['rea']
    assert config['parts']['frida-native']['after'] == ['rea', 'frida-runtime']
    class Dumper(yaml.SafeDumper):
        pass
    def represent_string(dumper, value):
        return dumper.represent_scalar('tag:yaml.org,2002:str', value, style='|' if '\n' in value else None)
    Dumper.add_representer(str, represent_string)
    (output / 'sdkcraft.yaml').write_text(yaml.dump(config, Dumper=Dumper, sort_keys=False))
    proof = {'base_artifact': str(base), 'base_sha256': BASE_SHA256,
             'full_source_recipe': str(source / 'sdkcraft.yaml'), 'full_source_recipe_sha256': digest(source / 'sdkcraft.yaml'),
             'generated_recipe_sha256': digest(output / 'sdkcraft.yaml'),
             'compatibility_manifest_sha256': digest(output / 'dependencies/frida-compatibility.json'),
             'unchanged_identity': {'name': config['name'], 'version': '6.9.0', 'base': config['base'], 'platforms': config['platforms'], 'plugs': config['plugs']},
             'method': 'Official SDKcraft parts consuming verified prebuilt binaries; not a separate SDK identity or replacement source repository',
             'required_acceptance': ['strict bidirectional artifact comparison', 'current hooks/metadata validation', 'matched Frida archive validation', 'clean Workshop install', 'direct Frida lifecycle and mixed MCP sequence', 'complete supported-provider regression and independent reinstall']}
    (output / 'rebuild-inputs.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
