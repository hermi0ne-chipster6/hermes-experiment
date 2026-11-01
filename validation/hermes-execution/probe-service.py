"""Synthetic native service fixture controlled over stdin; no credentials logged."""
from pathlib import Path
import json,os,socket,subprocess,sys,tempfile,time,urllib.request,urllib.error
settings=json.loads(sys.stdin.readline())
with socket.socket() as probe:
    if probe.connect_ex(('127.0.0.1',18080)) == 0:
        raise RuntimeError('Synthetic fixture port is already occupied; refusing a misleading health check')
with tempfile.TemporaryDirectory(prefix='hermes-workload-probe-') as directory:
    root=Path(directory)
    config=Path('/project/opensandbox-probe.toml').read_text().replace('port = 8080','port = 18080').replace('/home/workshop/.opensandbox/opensandbox.db',str(root/'store.db'))
    (root/'config.toml').write_text(config)
    env=dict(os.environ,OPENSANDBOX_SERVER_API_KEY=settings['api_key'])
    with (root/'server.log').open('w') as log:
        process=subprocess.Popen(['/var/lib/workshop/sdk/hermes-execution/bin/opensandbox-server','--config',str(root/'config.toml')],env=env,stdout=log,stderr=log)
        try:
            for attempt in range(90):
                if process.poll() is not None:raise RuntimeError('Native server exited')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:18080/health',timeout=2) as response:
                        if response.status==200:break
                except (OSError,urllib.error.URLError):pass
                time.sleep(1)
            else:raise RuntimeError('Native server health deadline exceeded')
            print('{"ready":true}',flush=True)
            sys.stdin.readline()
        finally:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            text=(root/'server.log').read_text()[-3000:].replace(settings['api_key'],'<redacted>')
            print(text,file=sys.stderr)
