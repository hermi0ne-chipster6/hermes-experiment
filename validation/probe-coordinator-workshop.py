"""Coordinate synthetic A/B native SDK test; private token never printed."""
from pathlib import Path
import json,secrets,selectors,subprocess,time,tempfile
root=Path(__file__).resolve().parent
key=secrets.token_urlsafe(32)
settings={'api_key':key,'domain':'b.hermes-execution.wp:18080'}
with (root.parent/'reports/opensandbox-workload-service.log').open('w') as log:
    server=subprocess.Popen(['workshop','exec','--timeout','10m','--','python3','/project/probe-service.py'],cwd=root/'hermes-execution',stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True)
    try:
        server.stdin.write(json.dumps(settings)+'\n');server.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(server.stdout,selectors.EVENT_READ)
            if not selector.select(120):raise RuntimeError('Service ready deadline exceeded')
            assert json.loads(server.stdout.readline())=={'ready':True}
        with tempfile.TemporaryFile(mode='w+') as captured:
            client=subprocess.Popen(['workshop','exec','--timeout','8m','--','/var/lib/workshop/sdk/hermes-experiment/bin/python','-I','/project/probe-workload.py'],cwd=root/'hermes-agent',stdin=subprocess.PIPE,stdout=captured,stderr=captured,text=True)
            client.stdin.write(json.dumps(settings)+'\n');client.stdin.flush()
            try:client.wait(timeout=500)
            finally:
                client.stdin.close()
                if client.poll() is None:client.terminate();client.wait(timeout=5)
            captured.seek(0)
            print(captured.read().replace(key,'<redacted>'),flush=True)
            if client.returncode:raise RuntimeError(f'Native workload probe failed (exit {client.returncode})')
    finally:
        try:
            server.stdin.write('stop\n');server.stdin.flush()
        except (OSError,BrokenPipeError):pass
        try:server.wait(timeout=15)
        except subprocess.TimeoutExpired:server.terminate();server.wait(timeout=5)
