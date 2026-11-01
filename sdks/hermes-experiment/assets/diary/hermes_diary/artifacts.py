"""Bounded B→C artifact handoff; native REA remains the only analysis server."""
import hashlib
from contextlib import contextmanager
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time

MAX_BYTES = 32 * 1024 * 1024
INBOX = '/var/lib/hermes-rea/inbox'


def _metadata(sha, size):
    if (not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha) or
            type(size) is not int or not 0 <= size <= MAX_BYTES):
        raise ValueError('Invalid artifact digest or size (maximum 32 MiB).')


def receive_stream(stream, inbox, sha, size):
    """Write a verified immutable input under a pre-created, non-symlink inbox."""
    _metadata(sha, size)
    directory = os.open(inbox, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = '.incoming-' + os.urandom(16).hex()
    target = sha + '.bin'
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory)
        with os.fdopen(fd, 'wb') as output:
            digest = hashlib.sha256()
            remaining = size
            while remaining:
                block = stream.read(min(65536, remaining))
                if not block:
                    raise ValueError('Truncated artifact body.')
                digest.update(block)
                output.write(block)
                remaining -= len(block)
            if stream.read(1) or digest.hexdigest() != sha:
                raise ValueError('Artifact length or checksum mismatch.')
            output.flush()
            os.fchmod(output.fileno(), 0o400)
            os.fsync(output.fileno())
        try:
            # link is atomic and fails if any target already exists; never overwrite.
            os.link(temporary, target, src_dir_fd=directory, dst_dir_fd=directory,
                    follow_symlinks=False)
        except FileExistsError:
            fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=directory)
            with os.fdopen(fd, 'rb') as existing:
                info = os.fstat(existing.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != size:
                    raise ValueError('Existing artifact does not match.')
                actual = hashlib.sha256(existing.read(MAX_BYTES + 1)).hexdigest()
                if actual != sha:
                    raise ValueError('Existing artifact does not match.')
        os.unlink(temporary, dir_fd=directory)
        os.fsync(directory)
        return {'protocol':'artifact-v1', 'sha256':sha, 'size':size,
                'path':os.fspath(inbox) + '/' + target}
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass
        os.close(directory)


def _sandbox(sandbox_id):
    from datetime import timedelta
    from opensandbox.sync import SandboxSync
    from opensandbox.config.connection_sync import ConnectionConfigSync
    domain = os.environ.get('OPEN_SANDBOX_DOMAIN')
    key = os.environ.get('OPEN_SANDBOX_API_KEY')
    if not domain or not key:
        raise ValueError('Execution worker credentials are not configured.')
    config = ConnectionConfigSync(domain=domain, api_key=key, use_server_proxy=True,
                                  request_timeout=timedelta(seconds=10))
    return SandboxSync.connect(sandbox_id, connection_config=config,
                               connect_timeout=timedelta(seconds=10))


def _send(file, sha, size):
    child = subprocess.Popen(['/usr/local/bin/hermes-rea-remote', '--artifact-put', sha, str(size)],
                             stdin=file, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             start_new_session=True)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            body = bytearray()
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if not selector.select(min(1, max(0, deadline - time.monotonic()))):
                    continue
                block = os.read(child.stdout.fileno(), 4097 - len(body))
                body.extend(block)
                if len(body) > 4096:
                    raise ValueError('REA artifact receipt exceeds the protocol limit.')
                if not block:
                    child.wait(timeout=max(0.1, deadline - time.monotonic()))
                    if child.returncode:
                        raise ValueError('REA artifact transfer failed.')
                    return json.loads(body)
            raise ValueError('REA artifact transfer timed out.')
    finally:
        child.stdout.close()
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


def copy_artifact(arguments, factory=_sandbox, sender=_send):
    if (not isinstance(arguments, dict) or set(arguments) != {'sandbox_id', 'remote_path'} or
            not isinstance(arguments['sandbox_id'], str) or
            not re.fullmatch('[A-Za-z0-9][A-Za-z0-9-]{0,127}', arguments['sandbox_id']) or
            not isinstance(arguments['remote_path'], str) or
            not arguments['remote_path'].startswith('/') or
            len(arguments['remote_path']) > 4096 or '\x00' in arguments['remote_path']):
        raise ValueError('Provide only a sandbox ID and an absolute file path inside that sandbox.')
    box = factory(arguments['sandbox_id'])
    stream = None
    try:
        with tempfile.TemporaryFile() as file:
            stream = box.files.read_bytes_stream(arguments['remote_path'], chunk_size=65536,
                                                      limit=MAX_BYTES + 1)
            digest = hashlib.sha256()
            size = 0
            for block in stream:
                size += len(block)
                if size > MAX_BYTES:
                    raise ValueError('Artifact exceeds 32 MiB.')
                digest.update(block)
                file.write(block)
            sha = digest.hexdigest()
            file.seek(0)
            receipt = sender(file, sha, size)
            expected = {'protocol':'artifact-v1', 'sha256':sha, 'size':size,
                        'path':f'{INBOX}/{sha}.bin'}
            if receipt != expected or type(receipt.get('size')) is not int:
                raise ValueError('REA artifact receipt does not match the submitted input.')
            return receipt
    finally:
        if stream is not None and hasattr(stream, 'close'):
            stream.close()
        box.close()  # Native client close does not terminate the remote sandbox.


@contextmanager
def _deadline(seconds):
    def expired(*_):
        raise TimeoutError('Artifact transfer wall-clock limit exceeded.')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def bounded_copy(arguments, factory=_sandbox, sender=_send, seconds=90):
    # Run only in the isolated worker's main thread; interrupts blocked reads,
    # including a response that trickles without yielding an HTTPX chunk.
    with _deadline(seconds):
        return copy_artifact(arguments, factory, sender)


def _isolated_copy(arguments):
    # Hermes invokes tools in threads; a dedicated interpreter owns SIGALRM.
    # It inherits only runtime transport settings, never model/financial keys.
    names = ('HOME','PATH','LANG','XDG_RUNTIME_DIR','OPEN_SANDBOX_DOMAIN',
             'OPEN_SANDBOX_API_KEY','HERMES_REA_HOST')
    env = {key:os.environ[key] for key in names if key in os.environ}
    child = subprocess.Popen([sys.executable,'-I',os.path.realpath(__file__),'copy'],
                             stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL,env=env,start_new_session=True)
    try:
        output, _ = child.communicate(json.dumps(arguments).encode(), timeout=100)
        if child.returncode or len(output) > 4096:
            raise ValueError('Bounded artifact worker failed.')
        return json.loads(output)
    finally:
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait()


def register(ctx):
    def handler(arguments, **kwargs):
        try:
            return json.dumps(_isolated_copy(arguments))
        except Exception:
            # Native HTTP/SSH exceptions can contain credentials. Keep them out of model context.
            return json.dumps({'error':'Artifact transfer failed; no verified REA receipt.'})
    ctx.register_tool(name='artifact_to_rea', toolset='hermes_artifacts', schema={
        'name':'artifact_to_rea',
        'description':'Copy one file (maximum 32 MiB) from an execution sandbox to the REA input inbox. Returns a verified local REA path for its native analysis tools. Does not execute the file.',
        'parameters':{'type':'object', 'properties':{'sandbox_id':{'type':'string'},
                      'remote_path':{'type':'string'}},
                      'required':['sandbox_id','remote_path'], 'additionalProperties':False}}, handler=handler)


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['copy']:
            arguments = json.loads(sys.stdin.buffer.read(8193))
            print(json.dumps(bounded_copy(arguments)), flush=True)
            sys.exit(0)
        if len(sys.argv) != 4 or sys.argv[1] != 'receive' or not re.fullmatch('[0-9]{1,8}', sys.argv[3]):
            raise ValueError('Invalid framed transfer.')
        signal.signal(signal.SIGALRM, lambda *_: sys.exit(124))
        signal.alarm(60)
        result = receive_stream(sys.stdin.buffer, INBOX, sys.argv[2], int(sys.argv[3]))
        print(json.dumps(result), flush=True)
    except (OSError, ValueError, TimeoutError):
        print('Artifact rejected; no receipt.', file=sys.stderr)
        sys.exit(65)
