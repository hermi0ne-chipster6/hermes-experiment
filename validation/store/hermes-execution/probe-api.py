"""Local synthetic native-API probe; no image pulls or model calls."""
from pathlib import Path
import json, os, secrets, signal, subprocess, tempfile, time
import urllib.request, urllib.error

def stop(*_):
    raise SystemExit(143)
signal.signal(signal.SIGTERM,stop)

with tempfile.TemporaryDirectory(prefix='hermes-api-probe-') as directory:
    root = Path(directory)
    config = Path('/project/opensandbox-probe.toml').read_text()
    config = config.replace('host = "0.0.0.0"', 'host = "127.0.0.1"').replace('port = 8080', 'port = 18080')
    config = config.replace('/home/workshop/.opensandbox/opensandbox.db', str(root/'store.db'))
    (root/'config.toml').write_text(config)
    token = secrets.token_urlsafe(32)
    env = dict(os.environ, OPENSANDBOX_SERVER_API_KEY=token)
    def request(path, authenticated=False):
        headers = {'OPEN-SANDBOX-API-KEY':token} if authenticated else {}
        try:
            with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18080'+path, headers=headers), timeout=3) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code
    with (root/'server.log').open('w') as log:
        process = subprocess.Popen(['/var/lib/workshop/sdk/hermes-execution/bin/opensandbox-server', '--config', str(root/'config.toml')], env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic()+120
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Native server exited: '+(root/'server.log').read_text()[-1800:].replace(token,'<redacted>'))
                try:
                    if request('/health') == 200: break
                except (OSError, urllib.error.URLError): pass
                time.sleep(1)
            else: raise RuntimeError('Native server health deadline exceeded: '+(root/'server.log').read_text()[-3000:].replace(token,'<redacted>'))
            print('Native API health ready',flush=True)
            result = {'health':request('/health'), 'unauthenticated_list':request('/v1/sandboxes'), 'authenticated_list':request('/v1/sandboxes',True)}
            print(json.dumps(result),flush=True)
            assert result == {'health':200,'unauthenticated_list':401,'authenticated_list':200}, result
        finally:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill();process.wait()
