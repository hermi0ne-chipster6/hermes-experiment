"""Use A's actual packaged native SDK against a temporary B service."""
from datetime import timedelta
import hashlib,json,sys
from opensandbox.sync import SandboxSync
from opensandbox.config.connection_sync import ConnectionConfigSync
settings=json.loads(sys.stdin.readline())
image='python@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8'
connection=ConnectionConfigSync(domain=settings['domain'],api_key=settings['api_key'],use_server_proxy=True,request_timeout=timedelta(seconds=180))
box=None
try:
    box=SandboxSync.create(image,timeout=timedelta(minutes=5),ready_timeout=timedelta(seconds=180),resource={'cpu':'1','memory':'256Mi'},connection_config=connection)
    execution=box.commands.run("python3 -c 'print(6*7)'")
    assert not execution.error,'Native execution returned an error'
    output=''.join(line.text for line in execution.logs.stdout)
    assert output.strip()=='42'
    data=b'Hermes synthetic sandbox file\n'
    box.files.write_file('/tmp/hermes-probe.txt',data,mode=600)
    restored=b''.join(box.files.read_bytes_stream('/tmp/hermes-probe.txt'))
    assert restored==data
    print(json.dumps({'image':image,'sandbox_id':box.id,'python_stdout':output.strip(),'file_sha256':hashlib.sha256(restored).hexdigest(),'server_proxy':True}),flush=True)
finally:
    if box:
        try:box.kill()
        finally:box.close()
