"""Exercise the installed Hermes package with disposable state and local fixtures."""
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from threading import Thread
import time
import traceback
from urllib.parse import parse_qs, urlsplit
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
DEPENDENCY = 'boltons==25.0.0'


def run(*argv, expected=0, timeout=100, **kwargs):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, **kwargs)
    if result.returncode != expected:
        output = (result.stdout + '\n' + result.stderr).strip()
        raise RuntimeError(f'{argv[:3]} exited {result.returncode}: {output[-1600:]}')
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
        'from boltons.iterutils import chunked\n\ndef register(ctx):\n'
        '    assert list(chunked([1, 2, 3], 2)) == [[1, 2], [3]]\n'
    )
    run('git', '-C', str(directory), 'add', 'plugin.yaml', '__init__.py')
    run('git', '-C', str(directory), '-c', 'user.name=SDK Qualification',
        '-c', 'user.email=qualification@example.invalid', 'commit', '-qm', version)
    return run('git', '-C', str(directory), 'rev-parse', 'HEAD').strip()


def probe_plugins():
    assert importlib.util.find_spec('boltons') is None, 'Dependency fixture is already in packaged core'
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
    os.environ['HERMES_RUNTIME_DIR'] = str(PROFILE / 'tools')
    os.environ['HERMES_INSTALL_ROOT'] = str(SDK / 'hermes-src')
    os.environ['HERMES_PYTHON_SRC_ROOT'] = str(SDK / 'hermes-src')
    os.environ['PATH'] = f'{SDK}/bin:{SDK}/node/bin:' + os.environ['PATH']
    # Match assets/bootstrap/hermes when calling the tool implementations directly.
    paths = [str(SDK / 'hermes-src'), str(SDK / 'diary')]
    os.environ['PYTHONPATH'] = os.pathsep.join(paths)
    sys.path[:0] = paths
    import hermes_bootstrap
    from hermes_cli.config import load_config
    from hermes_cli.tools_config import _get_platform_tools
    from tools.browser_use_cli import browser_exec
    from tools.code_execution_tool import execute_code
    from tools.file_tools import read_file_tool, write_file_tool
    from tools.terminal_tool import terminal_tool

    config = load_config()
    native = {'terminal', 'file', 'browser', 'code_execution', 'skills'}
    assert native <= _get_platform_tools(config, 'cli')
    for platform in ('buzz', 'email', 'cron'):
        assert not native & _get_platform_tools(config, platform), platform
    terminal = json.loads(terminal_tool('printf qualification-terminal', timeout=10))
    assert 'qualification-terminal' in terminal.get('output', ''), terminal
    with tempfile.TemporaryDirectory(prefix='hermes-tools-') as temp:
        path = str(Path(temp) / 'probe.txt')
        write = json.loads(write_file_tool(path, MARKER))
        assert 'error' not in write, write
        assert MARKER in json.loads(read_file_tool(path)).get('content', '')
    code = json.loads(execute_code('print(6 * 7)', task_id='sdk-qualification'))
    assert code.get('output', code.get('stdout', '')).strip() == '42', code
    print('Native terminal, file and Python code probes passed.', flush=True)
    class FixturePage(BaseHTTPRequestHandler):
        def do_GET(self):
            content = b'<html><title>qualification-browser</title></html>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(('127.0.0.1', 0), FixturePage) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            # This synthetic profile has no remote browser provider.
            browser = browser_exec(
                f'new_tab("http://127.0.0.1:{server.server_port}/")\n'
                'wait_for_load()\nprint(js("document.title"))',
                session='sdk-qualification', timeout_s=120,
            )
        finally:
            server.shutdown()
            worker.join(timeout=5)
    if isinstance(browser, str):
        browser = json.loads(browser)
    assert 'qualification-browser' in browser.get('output', ''), browser
    print('Native local browser navigation passed.', flush=True)


def probe_failed_opensandbox():
    from opensandbox.config.connection_sync import ConnectionConfigSync
    from opensandbox.exceptions import SandboxException
    from opensandbox.sync import SandboxSync

    requests = []

    class DeniedSandbox(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((urlsplit(self.path), self.headers.get('OPEN-SANDBOX-API-KEY')))
            body = b'{"code":"UNAUTHORIZED","message":"synthetic worker refused the request"}'
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(('127.0.0.1', 0), DeniedSandbox) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            settings = ConnectionConfigSync(
                domain=f'127.0.0.1:{server.server_port}', api_key='synthetic-only',
                use_server_proxy=True, request_timeout=timedelta(seconds=3),
            )
            try:
                box = SandboxSync.connect('qualification', connection_config=settings,
                                          connect_timeout=timedelta(seconds=5))
            except SandboxException:
                pass
            else:
                box.close()
                raise AssertionError('Failed remote OpenSandbox operation unexpectedly succeeded')
        finally:
            server.shutdown()
            worker.join(timeout=5)
    assert requests, 'OpenSandbox did not contact the fixture'
    route, api_key = requests[0]
    assert '/sandboxes/qualification/endpoints/' in route.path, route.path
    assert parse_qs(route.query).get('use_server_proxy') == ['true'], route.query
    assert api_key == 'synthetic-only'


def probe_integrations():
    for plugin in ('hindsight', 'hermes_otel', 'rea', 'hermes_diary',
                   'hermes_notifications', 'hermes_artifacts'):
        assert (PROFILE / 'plugins' / plugin).resolve() == SDK / 'plugins' / plugin
    assert 'usage' in run('/usr/local/bin/opensandbox-mcp', '--help').lower()
    probe_failed_opensandbox()
    failed = subprocess.run(
        ['/usr/local/bin/hermes-rea-remote'],
        env={**os.environ, 'HERMES_REA_HOST': '127.0.0.1'},
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert failed.returncode == 78 and 'Pinned REA SSH host identity is missing' in failed.stderr
    print('Bundled plugin links, OpenSandbox loopback rejection and REA missing-host-key failure passed.',
          flush=True)


def probe_catalog_plugins():
    # Verify the two independently managed plugins using the tested core's own
    # immutable catalog records. These installs stay disabled and run no jobs.
    import yaml
    errors = []
    for plugin in ('mandate', 'promise-keeper'):
        print(f'Checking optional catalog plugin {plugin}', flush=True)
        try:
            catalog = SDK / 'hermes-src' / 'plugin-catalog' / f'{plugin}.yaml'
            entry = yaml.safe_load(catalog.read_text())
            hermes('plugins', 'install', entry['repo'], '--ref', entry['sha'],
                   '--no-enable', '--yes-deps', timeout=180)
            candidates = [path for path in (PROFILE / 'plugins').iterdir()
                          if path.is_dir() and (path / '.git').exists()]
            matched = [path for path in candidates
                       if run('git', '-C', str(path), 'rev-parse', 'HEAD').strip() == entry['sha']]
            assert len(matched) == 1, f'Exact installed catalog revision missing for {plugin}'
            hermes('plugins', 'doctor', str(matched[0]), '--ci')
            hermes('plugins', 'remove', matched[0].name)
            print(f'{plugin} pinned install and native doctor passed.', flush=True)
        except Exception as error:
            errors.append(error)
            traceback.print_exc()
    if errors:
        raise ExceptionGroup('Catalog plugin compatibility failures', errors)


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
    errors = []
    for probe in (probe_plugins, probe_native_tools, probe_web_and_tui,
                  probe_integrations, probe_catalog_plugins):
        try:
            probe()
        except Exception as error:
            errors.append(error)
            traceback.print_exc()
    with (PROFILE / 'config.yaml').open('a') as config:
        config.write('\n# qualification-operator-edit\n')
    continuity()
    if errors:
        raise ExceptionGroup('Workshop acceptance failures', errors)


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'exercise':
        exercise()
    elif mode == 'native-tools':
        probe_native_tools()
    elif mode in {'continuity', 'rollback-continuity'}:
        continuity(rollback=mode == 'rollback-continuity')
    else:
        raise SystemExit(f'Unknown qualification probe: {mode}')
