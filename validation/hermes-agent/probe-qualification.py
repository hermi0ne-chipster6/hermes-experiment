"""Exercise the installed Hermes package with disposable state and local fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

SDK = Path('/var/lib/workshop/sdk/hermes-experiment')
PROFILE = Path.home() / '.hermes'
HERMES = '/usr/local/bin/hermes'
FIXTURE = 'sdk-qualification-plugin'
MARKER = 'synthetic Workshop state'
STATE = (
    PROFILE / 'memories' / 'qualification-marker',
    PROFILE / 'sessions' / 'qualification-marker',
    Path.home() / '.pg0' / 'qualification-marker',
    Path.home() / '.sui' / 'qualification-marker',
    Path.home() / '.link-cli' / 'qualification-marker',
)
DEPENDENCY = (
    'cowsay @ https://files.pythonhosted.org/packages/f1/13/'
    '63c0a02c44024ee16f664e0b36eefeb22d54e93531630bd99e237986f534/'
    'cowsay-6.1-py3-none-any.whl'
    '#sha256=274b1e6fc1b966d53976333eb90ac94cb07a450a700b455af9fbdf882244b30a'
)


def run(*argv, expected=0, timeout=100, **kwargs):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, **kwargs)
    if result.returncode != expected:
        raise RuntimeError(f'{argv[:3]} exited {result.returncode}: {result.stderr[-1200:]}')
    return result.stdout


def hermes(*argv, **kwargs):
    return run(HERMES, *argv, **kwargs)


def plugin_rows():
    return {row['name']: row for row in json.loads(hermes('plugins', 'list', '--json'))}


def plugin_source(directory, version):
    (directory / 'plugin.yaml').write_text(
        f'name: {FIXTURE}\nversion: {version}\ndescription: Disposable SDK verification.\n'
        f'python_dependencies:\n- {json.dumps(DEPENDENCY)}\n'
    )
    (directory / '__init__.py').write_text(
        'import cowsay\n\ndef register(ctx):\n    assert "qualification" in cowsay.get_output_string("cow", "qualification")\n'
    )
    run('git', '-C', str(directory), 'add', 'plugin.yaml', '__init__.py')
    run('git', '-C', str(directory), '-c', 'user.name=SDK Qualification',
        '-c', 'user.email=qualification@example.invalid', 'commit', '-qm', version)
    return run('git', '-C', str(directory), 'rev-parse', 'HEAD').strip()


def probe_plugins():
    assert importlib.util.find_spec('cowsay') is None, 'Dependency fixture is already in packaged core'
    with tempfile.TemporaryDirectory(prefix='qualification-plugin-') as scratch:
        repo = Path(scratch) / FIXTURE
        repo.mkdir()
        run('git', '-C', str(repo), 'init', '-q', '-b', 'main')
        first = plugin_source(repo, '1.0.0')
        hermes('plugins', 'install', repo.as_uri(), '--enable', '--yes-deps', timeout=240)
        installed = PROFILE / 'plugins' / FIXTURE
        assert run('git', '-C', str(installed), 'rev-parse', 'HEAD').strip() == first
        assert plugin_rows()[FIXTURE]['status'] == 'enabled'
        hermes('plugins', 'doctor', FIXTURE, '--ci')
        second = plugin_source(repo, '1.1.0')
        hermes('plugins', 'update', FIXTURE, timeout=240)
        assert run('git', '-C', str(installed), 'rev-parse', 'HEAD').strip() == second
        assert plugin_rows()[FIXTURE]['version'] == '1.1.0'
        hermes('plugins', 'disable', FIXTURE)
        assert plugin_rows()[FIXTURE]['status'] == 'disabled'
        hermes('plugins', 'enable', FIXTURE, '--no-allow-tool-override')
        assert plugin_rows()[FIXTURE]['status'] == 'enabled'
        hermes('plugins', 'doctor', FIXTURE, '--ci')
        hermes('plugins', 'remove', FIXTURE)
        assert FIXTURE not in plugin_rows() and not installed.exists()
        hermes('plugins', 'install', repo.as_uri(), '--enable', '--yes-deps', timeout=240)
    assert not os.access(SDK / 'hermes-src', os.W_OK), 'Installed core must be immutable'
    records = json.loads((PROFILE / 'plugins' / '.install-metadata.json').read_text())
    assert FIXTURE in records
    print('Native plugin install, dependency import, update, activation and removal passed.', flush=True)


def probe_native_tools():
    os.environ['HERMES_HOME'] = str(PROFILE)
    os.environ['PATH'] = f'{SDK}/bin:{SDK}/node/bin:' + os.environ['PATH']
    sys.path.insert(0, str(SDK / 'hermes-src'))
    from tools.browser_use_cli import browser_exec
    from tools.code_execution_tool import execute_code
    from tools.file_tools import read_file_tool, write_file_tool
    from tools.terminal_tool import terminal_tool

    terminal = json.loads(terminal_tool('printf qualification-terminal', timeout=10))
    assert 'qualification-terminal' in terminal.get('output', ''), terminal
    with tempfile.TemporaryDirectory(prefix='hermes-tools-') as temp:
        path = str(Path(temp) / 'probe.txt')
        write = json.loads(write_file_tool(path, MARKER))
        assert 'error' not in write, write
        assert MARKER in json.loads(read_file_tool(path)).get('content', '')
    code = json.loads(execute_code('print(6 * 7)', task_id='sdk-qualification'))
    assert '42' in code.get('output', ''), code
    browser = browser_exec(
        'new_tab("data:text/html,<title>qualification-browser</title>")\n'
        'wait_for_load()\nprint(js("document.title"))',
        session='sdk-qualification', timeout_s=90,
    )
    if isinstance(browser, str):
        browser = json.loads(browser)
    assert 'qualification-browser' in browser.get('output', ''), browser
    print('Native terminal, file, code and local browser probes passed.', flush=True)


def probe_web_and_tui():
    node = SDK / 'node' / 'bin' / 'node'
    bundle = SDK / 'hermes-src' / 'hermes_cli' / 'tui_dist' / 'entry.js'
    # The bundled TUI boots and reports its non-interactive terminal requirement.
    output = run(str(node), '--expose-gc', str(bundle), stdin=subprocess.DEVNULL)
    assert 'tty' in output.lower() or 'terminal' in output.lower(), output

    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    with tempfile.TemporaryFile() as logs:
        with subprocess.Popen(
            [HERMES, 'dashboard', '--no-open', '--host', '127.0.0.1', '--port', str(port)],
            stdout=logs, stderr=logs,
        ) as server:
            try:
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline and server.poll() is None:
                    try:
                        with urlopen(f'http://127.0.0.1:{port}/', timeout=2) as response:
                            assert 'text/html' in response.headers['Content-Type']
                            assert b'<html' in response.read().lower()
                            break
                    except OSError:
                        time.sleep(0.25)
                else:
                    logs.seek(0)
                    raise RuntimeError(f'Dashboard startup failed: {logs.read().decode(errors="replace")[-1200:]}')
            finally:
                if server.poll() is None:
                    server.terminate()
                    server.wait(timeout=10)
    print('Packaged Web UI and TUI bundle startup passed.', flush=True)


def continuity(rollback=False):
    for path in STATE:
        assert path.read_text() == MARKER, f'Lost persistent marker at {path}'
    assert (Path.home() / '.pg0').resolve() == Path.home() / '.hindsight' / 'pg0'
    assert (PROFILE / 'plugins' / FIXTURE / 'plugin.yaml').is_file()
    assert FIXTURE in json.loads((PROFILE / 'plugins' / '.install-metadata.json').read_text())
    config = PROFILE / 'config.yaml'
    if rollback and config.is_symlink():
        config = PROFILE / 'config.yaml.qualification-rollback'
    assert 'qualification-operator-edit' in config.read_text()
    if not rollback:
        assert plugin_rows()[FIXTURE]['status'] == 'enabled'
        hermes('plugins', 'doctor', FIXTURE, '--ci')

    print('Profile, session, memory, pg0, Sui, Link and plugin state survived.', flush=True)


def exercise():
    hermes('update', expected=64)
    secret = subprocess.run(
        ['workshopctl', 'get-secret', 'hermes-experiment.model-key'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False,
    )
    assert secret.returncode != 0, 'Unexpected connected model secret'
    assert (PROFILE / 'config.yaml').is_file() and not (PROFILE / 'config.yaml').is_symlink()
    assert os.access(PROFILE / 'config.yaml', os.W_OK)
    for path in STATE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(MARKER)
    probe_plugins()
    probe_native_tools()
    probe_web_and_tui()
    with (PROFILE / 'config.yaml').open('a') as config:
        config.write('\n# qualification-operator-edit\n')
    continuity()


if __name__ == '__main__':
    if sys.argv[1] == 'exercise':
        exercise()
    else:
        continuity(rollback=sys.argv[1] == 'rollback-continuity')
