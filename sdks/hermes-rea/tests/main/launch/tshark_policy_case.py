#!/usr/bin/env python3
"""Prove actual TShark confinement using owned valid-capture and DAC controls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess
import tempfile
import time


TSHARK = '/usr/bin/tshark'
WORK = Path('/var/lib/hermes-rea/work')


def stop(child):
    if child.poll() is None:
        child.kill()
        child.wait(timeout=10)


def frames(result):
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    rows = result.stdout.decode().splitlines()
    assert rows and all(row.isdecimal() for row in rows), rows
    return rows


def prove(pcap, output, report):
    account = pwd.getpwuid(os.geteuid())
    assert account.pw_name == 'rea' and os.geteuid() != 0, 'Run as the installed rea user'
    home = Path(account.pw_dir)
    assert home == Path('/var/lib/hermes-rea') and not home.is_symlink(), home
    assert output.is_relative_to(WORK), 'Output must be inside the declared REA work directory'
    assert pcap.is_file(), f'Valid caller-owned PCAP is missing: {pcap}'
    payload = pcap.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    report.update(pcap=str(pcap), input_sha256=digest, uid=os.geteuid(), tshark=TSHARK)
    env = dict(os.environ, LC_ALL='C')
    command = [TSHARK, '-r', '-', '-T', 'fields', '-e', 'frame.number']
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=env)
    try:
        deadline = time.monotonic() + 10
        while True:
            assert child.poll() is None, 'TShark exited before confinement could be observed'
            label = Path(f'/proc/{child.pid}/attr/current').read_text().strip()
            if label == 'tshark (enforce)':
                break
            assert time.monotonic() < deadline, f'TShark was not enforced: {label}'
            time.sleep(.05)
        report['confinement'] = label
        stdout, stderr = child.communicate(payload, timeout=30)
        decoded = subprocess.CompletedProcess(command, child.returncode, stdout, stderr)
        original_frames = frames(decoded)
        report['stdin_decode'] = {'exit': child.returncode, 'frames': len(original_frames)}
    finally:
        stop(child)
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream is not None:
                stream.close()

    # Node passes inherited unnamed Unix sockets to providers. Exercise that
    # permission independently of ordinary subprocess pipes and file output.
    receiver, sender = socket.socketpair()
    receiver.settimeout(15)
    child = None
    try:
        child = subprocess.Popen([TSHARK, '--version'], stdout=sender,
                                 stderr=subprocess.PIPE, env=env)
        sender.close()
        chunks = []
        while data := receiver.recv(65536):
            chunks.append(data)
        _, stderr = child.communicate(timeout=15)
        version = b''.join(chunks)
        assert child.returncode == 0 and b'TShark (Wireshark)' in version, stderr
        report['inherited_unix_socket'] = {'exit': child.returncode, 'bytes': len(version)}
    finally:
        sender.close()
        receiver.close()
        if child is not None:
            stop(child)
            if child.stderr is not None:
                child.stderr.close()

    with tempfile.TemporaryDirectory(prefix='policy-positive-', dir=output) as allowed, \
            tempfile.TemporaryDirectory(prefix='.tshark-policy-denial-', dir=home) as outside:
        allowed = Path(allowed)
        outside = Path(outside)
        assert not outside.is_relative_to(WORK) and not outside.is_relative_to(home/'inbox')
        positive = allowed/'allowed.pcapng'
        written = subprocess.run([TSHARK, '-r', '-', '-w', str(positive)], input=payload,
                                 capture_output=True, timeout=30, env=env)
        assert written.returncode == 0 and positive.stat().st_size > 0, written.stderr
        reread = subprocess.run([TSHARK, '-r', str(positive), '-T', 'fields', '-e', 'frame.number'],
                                capture_output=True, timeout=30, env=env)
        assert frames(reread) == original_frames, 'Allowed capture round-trip changed frame inventory'
        report['allowed_capture_roundtrip'] = {'write_exit': written.returncode,
            'read_exit': reread.returncode, 'frames': len(original_frames), 'bytes': positive.stat().st_size}

        denied = outside/'denied.pcapng'
        # Prove DAC allows this exact destination, then remove that control file
        # so the confined process must create it through the same parent.
        denied.write_bytes(payload)
        assert denied.read_bytes() == payload
        denied.unlink()
        rejected = subprocess.run([TSHARK, '-r', '-', '-w', str(denied)], input=payload,
                                  capture_output=True, timeout=30, env=env)
        error = rejected.stderr.decode(errors='replace')
        report['outside_write'] = {'exit': rejected.returncode, 'stderr': error,
            'stdout': rejected.stdout.decode(errors='replace'), 'path': str(denied),
            'exists': denied.exists(), 'dac_exact_path_control': True}
        assert rejected.returncode != 0 and not denied.exists(), report['outside_write']
        permission_error = ('Permission denied' in error or
                            "don't have permission to create or write" in error)
        assert str(denied) in error and permission_error, report['outside_write']
        # A second same-user control rules out intervening ownership/mode changes.
        denied.write_bytes(b'DAC control after the confined refusal\n')
        denied.unlink()
        report['outside_write']['dac_control_after_refusal'] = True
    assert not allowed.exists() and not outside.exists()
    assert hashlib.sha256(pcap.read_bytes()).hexdigest() == digest, 'Caller input changed'
    report['owned_outputs_removed'] = True
    report['scope'] = 'Actual enforced profile, valid owned capture round-trip, inherited Unix socket, and outside-work write denial; no root or policy mutation'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pcap', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(WORK), 'Output must be inside the declared REA work directory'
    output.mkdir(parents=True, exist_ok=True)
    report = {'status': 'running'}
    try:
        prove(args.pcap.resolve(), output, report)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=f'{type(error).__name__}: {error}')
    (output/'confinement-proof.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['status'] == 'pass' else 1)


if __name__ == '__main__':
    main()
