from copy import deepcopy
from hashlib import sha256, sha3_384
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from ci.sdk_payload import archive_payload, installed_payload, verify_mount
from ci.workshop_archive import verify_attachment, verify_registry


class SDKPayloadTests(unittest.TestCase):
    def test_legacy_tar_symlink_has_linux_mounted_mode(self):
        with tempfile.TemporaryDirectory() as scratch:
            directory = Path(scratch)
            root = directory / 'sdk'
            root.mkdir()
            (root / 'bin').symlink_to('runtime/bin')
            image = directory / 'legacy.tar'

            def sdkcraft_modes(member):
                if member.issym():
                    member.mode = 0o755
                return member

            with tarfile.open(image, 'w') as archive:
                archive.add(root, arcname='.', filter=sdkcraft_modes)
            with tarfile.open(image) as archive:
                self.assertEqual(archive.getmember('./bin').mode, 0o755)
                self.assertEqual(archive_payload(archive), installed_payload(root))

    def test_same_pin_does_not_hide_a_different_installed_tree(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch)
            installed = path / 'sdk'
            installed.mkdir()
            (installed / 'core-pin.json').write_text('{"commit": "unchanged"}')
            launcher = installed / 'hermes'
            launcher.write_text('candidate bytes')
            launcher.chmod(0o755)
            linked = installed / 'launcher-alias'
            linked.symlink_to('hermes')
            hardlink = installed / 'launcher-hardlink'
            os.link(launcher, hardlink)
            archive_path = path / 'archive.tar'
            with tarfile.open(archive_path, 'w') as archive:
                archive.add(installed, arcname='.')
            with tarfile.open(archive_path, 'r|') as archive:
                expected = archive_payload(archive)
            self.assertEqual(installed_payload(installed), expected)

            launcher.write_text('different bytes')
            self.assertNotEqual(installed_payload(installed), expected)
            launcher.write_text('candidate bytes')
            launcher.chmod(0o644)
            self.assertNotEqual(installed_payload(installed), expected)
            launcher.chmod(0o755)
            linked.unlink()
            linked.symlink_to('core-pin.json')
            self.assertNotEqual(installed_payload(installed), expected)
            linked.unlink()
            linked.symlink_to('hermes')
            hardlink.unlink()
            self.assertNotEqual(installed_payload(installed), expected)
            hardlink.write_text('candidate bytes')
            hardlink.chmod(0o755)
            self.assertNotEqual(installed_payload(installed), expected)
            hardlink.unlink()
            os.link(launcher, hardlink)
            (installed / 'extra').touch()
            self.assertNotEqual(installed_payload(installed), expected)

    def test_only_the_exact_read_only_mount_without_overlays_is_accepted(self):
        root = '/var/lib/workshop/sdk/hermes-experiment'
        valid = f'11 1 0:7 / {root} ro,nosuid - ext4 device rw\n'
        verify_mount(valid.splitlines(), root)
        for mountinfo in (
            '', valid.replace(' ro,', ' rw,'), valid + valid,
            valid + f'12 11 0:9 / {root}/bin ro - tmpfs tmpfs rw\n',
        ):
            with self.subTest(mountinfo=mountinfo), self.assertRaises(ValueError):
                verify_mount(mountinfo.splitlines(), root)

    def test_registry_bytes_and_both_sidecars_are_checked(self):
        with tempfile.TemporaryDirectory() as scratch:
            archive = Path(scratch) / 'candidate.sdk'
            checksum = archive.with_name('candidate.sdk.sha3-384')
            metadata = archive.with_name('candidate.sdk.yaml')
            expected = {'archive_sha3_384': sha3_384(b'archive').hexdigest(),
                        'metadata_sha256': sha256(b'name: hermes-experiment\n').hexdigest()}
            files = {archive: b'archive', checksum: (expected['archive_sha3_384'] + '\n').encode(),
                     metadata: b'name: hermes-experiment\n'}
            for path, content in files.items():
                path.write_bytes(content)
            verify_registry(archive, expected)
            for path, content in files.items():
                with self.subTest(path=path.name):
                    path.write_bytes(b'substitute')
                    with self.assertRaises(ValueError):
                        verify_registry(archive, expected)
                    path.write_bytes(content)

    def test_attachment_checks_tree_and_disk_before_accepting_same_pin(self):
        sdk = 'hermes-experiment'
        mounted = {'entries': 150, 'tree_sha256': 'tree digest',
                   'metadata_sha256': sha256(b'name: hermes-experiment\n').hexdigest()}
        expected = {**mounted, 'archive_sha3_384': 'retained sha3', 'archive_sha256': 'retained sha256'}
        device = {'type': 'disk', 'path': f'/var/lib/workshop/sdk/{sdk}', 'readonly': 'true',
                  'pool': 'workshop', 'source': f'{sdk}-x2', 'user.sdk.revision': 'x2',
                  'user.sdk.source': 'try', 'user.sdk.sha3-384': expected['archive_sha3_384']}
        devices = {f'sdk.{sdk}': device}
        instance = {'name': 'hermes-qualification-1234abcd', 'devices': devices, 'expanded_devices': devices,
                    'config': {'user.workshop.project-id': '1234abcd', 'user.workshop.name': 'hermes-qualification'}}
        volume = {'name': f'{sdk}-x2', 'type': 'custom', 'content_type': 'filesystem',
                  'config': {'user.kind': 'sdk', 'user.sdk.name': sdk, 'user.sdk.revision': 'x2',
                             'user.sha3-384': expected['archive_sha3_384'],
                             'user.sdk.meta': 'name: hermes-experiment\n'}}
        with tempfile.TemporaryDirectory() as scratch:
            project = Path(scratch)
            (project / '.workshop.lock').write_text('1234abcd')
            with patch('ci.workshop_archive._lxd_query', side_effect=[instance, volume]):
                self.assertEqual(verify_attachment(project, expected, mounted)['archive_sha256'], 'retained sha256')

            changed_instance = deepcopy(instance)
            changed_instance['devices'][f'sdk.{sdk}']['user.sdk.sha3-384'] = 'different attachment'
            changed_volume = deepcopy(volume)
            changed_volume['config']['user.sha3-384'] = 'different volume'
            for actual_instance, actual_volume, actual_tree in (
                (changed_instance, volume, mounted), (instance, changed_volume, mounted),
                (instance, volume, {**mounted, 'tree_sha256': 'substitute with identical core pin'}),
            ):
                with (patch('ci.workshop_archive._lxd_query', side_effect=[actual_instance, actual_volume]),
                      self.assertRaises(ValueError)):
                    verify_attachment(project, expected, actual_tree)
