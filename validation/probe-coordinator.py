"""Coordinate synthetic A/B native SDK test; private token never printed."""
from pathlib import Path
import json,secrets,selectors,subprocess,time,tempfile,sys
root=Path(__file__).resolve().parent
key=secrets.token_urlsafe(32)
settings={'api_key':key,'domain':'b.hermes-execution.wp:18080'}
if '--rea' in sys.argv:
    fixture=Path('/tmp/hermes-rea-transport.Zw8Lt4')
    settings['rea_key']=(fixture/'key').read_text()
    known=(fixture/'known_hosts').read_text().split(maxsplit=1)[1]
    settings['rea_known_hosts']='c.hermes-rea.wp,10.24.8.107 '+known
    settings['rea_host']='c.hermes-rea.wp'
with (root.parent/'reports/opensandbox-workload-service.log').open('w') as log:
    server=subprocess.Popen(['sudo','-n','lxc','exec','--project','workshop.codex','b-127b97b7','--env','HOME=/home/workshop','--cwd','/project','--','sudo','-u','workshop','--','python3','/project/probe-service.py'],cwd=root/'hermes-execution',stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True)
    try:
        server.stdin.write(json.dumps({'api_key':key})+'\n');server.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(server.stdout,selectors.EVENT_READ)
            if not selector.select(120):raise RuntimeError('Service ready deadline exceeded')
            assert json.loads(server.stdout.readline())=={'ready':True}
        with tempfile.TemporaryFile(mode='w+') as captured:
            client=subprocess.Popen(['sudo','-n','lxc','exec','--project','workshop.codex','a-184ac90e','--env','HOME=/home/workshop','--cwd','/project','--','sudo','-u','workshop','--','/var/lib/workshop/sdk/hermes-experiment/bin/python','-I','/project/probe-workload.py'],cwd=root/'hermes-agent',stdin=subprocess.PIPE,stdout=captured,stderr=captured,text=True)
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
