"""Use A's actual packaged native SDK against a temporary B service."""
from datetime import timedelta
import hashlib,json,sys,os,re,subprocess,tempfile,importlib.util
from pathlib import Path
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
    handoff=None
    if settings.get('rea_key'):
        execution=box.commands.run('cp /usr/bin/true /tmp/hermes-analysis-fixture')
        assert not execution.error
        spec=importlib.util.spec_from_file_location('artifact_probe','/project/probe-artifacts.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix='hermes-rea-input-') as name:
            known=Path(name)/'known_hosts';known.write_text(settings['rea_known_hosts'])
            agent=subprocess.run(['ssh-agent','-s','-t','120'],capture_output=True,text=True,check=True)
            agent_env=dict(os.environ)
            for variable in ('SSH_AUTH_SOCK','SSH_AGENT_PID'):
                agent_env[variable]=re.search(variable+r'=([^;]+);',agent.stdout).group(1)
            try:
                subprocess.run(['ssh-add','-t','120','-'],input=settings['rea_key'].encode(),
                               env=agent_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
                def sender(file,sha,size):
                    result=subprocess.run(['ssh','-F','/dev/null','-T','-o','BatchMode=yes',
                        '-o','ConnectTimeout=8','-o','ForwardAgent=no','-o','ClearAllForwardings=yes',
                        '-o','SendEnv=-*','-o','IdentityFile=none','-o','StrictHostKeyChecking=yes',
                        '-o','UserKnownHostsFile='+str(known),'rea@'+settings['rea_host'],
                        f'artifact-put {sha} {size}'],stdin=file,env=agent_env,
                        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=60,check=True)
                    return json.loads(result.stdout)
                handoff=module.bounded_copy({'sandbox_id':box.id,'remote_path':'/tmp/hermes-analysis-fixture'},
                    factory=lambda value:SandboxSync.connect(value,connection_config=connection),sender=sender)
            finally:
                subprocess.run(['ssh-agent','-k'],env=agent_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print(json.dumps({'handoff':handoff,'image':image,'sandbox_id':box.id,'python_stdout':output.strip(),'file_sha256':hashlib.sha256(restored).hexdigest(),'server_proxy':True}),flush=True)
finally:
    if box:
        try:box.kill()
        finally:box.close()
