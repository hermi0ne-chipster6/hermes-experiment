"""Native, temporary OpenSandbox command/file probe, no model or account calls."""
from datetime import timedelta
from pathlib import Path
import hashlib,json,os,secrets,subprocess,tempfile,time,urllib.request,urllib.error
from opensandbox.sync import SandboxSync
from opensandbox.config.connection_sync import ConnectionConfigSync
IMAGE='python@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8'
with tempfile.TemporaryDirectory(prefix='hermes-workload-probe-') as directory:
    root=Path(directory)
    config=Path('/project/opensandbox-probe.toml').read_text().replace('host = "0.0.0.0"','host = "127.0.0.1"').replace('port = 8080','port = 18080').replace('/home/workshop/.opensandbox/opensandbox.db',str(root/'store.db'))
    (root/'config.toml').write_text(config)
    token=secrets.token_urlsafe(32)
    env=dict(os.environ,OPENSANDBOX_SERVER_API_KEY=token)
    box=None
    with (root/'server.log').open('w') as log:
        process=subprocess.Popen(['/var/lib/workshop/sdk/hermes-execution/bin/opensandbox-server','--config',str(root/'config.toml')],env=env,stdout=log,stderr=log)
        try:
            for attempt in range(90):
                if process.poll() is not None: raise RuntimeError('Native server exited')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:18080/health',timeout=2) as response:
                        if response.status==200:break
                except (OSError,urllib.error.URLError):pass
                time.sleep(1)
            else:raise RuntimeError('Native server health deadline exceeded')
            connection=ConnectionConfigSync(domain='127.0.0.1:18080',api_key=token,use_server_proxy=True,request_timeout=timedelta(seconds=30))
            box=SandboxSync.create(IMAGE,timeout=timedelta(minutes=5),ready_timeout=timedelta(seconds=180),resource={'cpu':'1','memory':'256Mi'},connection_config=connection)
            execution=box.commands.run(['python3','-c','print(6*7)'])
            if execution.error:raise RuntimeError('Native sandbox execution failed')
            output=''.join(line.text for line in execution.logs.stdout)
            assert output.strip()=='42', output
            data=b'Hermes synthetic sandbox file\n'
            box.filesystem.write_file('/tmp/hermes-probe.txt',data,mode=600)
            restored=b''.join(box.filesystem.read_bytes_stream('/tmp/hermes-probe.txt'))
            assert restored==data
            print(json.dumps({'image':IMAGE,'sandbox_id':box.id,'python_stdout':output.strip(),'file_sha256':hashlib.sha256(restored).hexdigest(),'server_proxy':True}),flush=True)
        except Exception:
            # Synthetic token is never printed, including native exception URLs/headers.
            text=(root/'server.log').read_text()[-3500:].replace(token,'<redacted>')
            print(text)
            raise RuntimeError('Native workload probe failed; inspect redacted log') from None
        finally:
            if box:
                try:box.kill()
                finally:box.close()
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
