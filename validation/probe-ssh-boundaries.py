"""Synthetic real SSH tests against the REA fixture, no private key output."""
from pathlib import Path
import json,subprocess,tempfile
fixture=Path('/tmp/hermes-rea-transport.Zw8Lt4')
base=['ssh','-F','/dev/null','-T','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(fixture/'known_hosts'),'-o','IdentitiesOnly=yes','-i',str(fixture/'key')]
host='rea@10.24.8.107'
retired=subprocess.run(base+[host,'artifact-put '+('0'*64)+' 1'],input=b'x',capture_output=True,timeout=30)
assert retired.returncode==64 and not retired.stdout
command=subprocess.run(base+[host,'uname -a'],input=b'',capture_output=True,timeout=30)
assert command.returncode==64 and b'Linux' not in command.stdout
forward=subprocess.run(base+['-o','ExitOnForwardFailure=yes','-N','-R','0:127.0.0.1:22',host],input=b'',capture_output=True,timeout=30)
assert forward.returncode!=0 and b'forwarding failed' in forward.stderr
with tempfile.TemporaryDirectory() as name:
    known=Path(name)/'known_hosts';known.write_text('10.24.8.107 '+(fixture/'key.pub').read_text())
    wrong=base.copy();wrong[wrong.index('UserKnownHostsFile='+str(fixture/'known_hosts'))]='UserKnownHostsFile='+str(known)
    rejected=subprocess.run(wrong+[host,'rea-mcp'],input=b'',capture_output=True,timeout=30)
    assert rejected.returncode==255 and b'Host key verification failed' in rejected.stderr
print(json.dumps({'retired_artifact_mode_denied':True,'arbitrary_command_rejected':True,'remote_forwarding_denied':True,'wrong_host_identity_denied':True}))
