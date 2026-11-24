"""Read-only installed-runtime checks; never sends messages or calls a model."""
from pathlib import Path
import importlib.metadata
import json
import subprocess

SDK_ROOT = Path('/var/lib/workshop/sdk')
SDK = SDK_ROOT / 'hermes-experiment'
def run(argv,expected=0):
    result=subprocess.run(argv,capture_output=True,text=True,timeout=60)
    assert result.returncode==expected,(argv[0:2],result.returncode,result.stderr[:600])
    return result.stdout+result.stderr

run([SDK/'bin/python', '-I', SDK/'wrappers/check-core.py', SDK, '/usr/local/bin/hermes'])
pin = json.loads((SDK/'share/hermes/core-pin.json').read_text())
assert Path('/usr/local/bin/sui').resolve() == SDK_ROOT / 'sui-cli/sui/bin/sui'
assert Path('/usr/local/bin/link-cli').resolve() == SDK_ROOT / 'stripe-link-cli/wrappers/link-cli'
assert not (SDK / 'sui').exists() and not (SDK / 'finance').exists()
sui_version = run(['/usr/local/bin/sui', '--version']).strip()
link_version = run(['/usr/local/bin/link-cli', '--version']).strip()
assert sui_version.startswith('sui 1.82.3')
assert link_version == '1.0.1'
assert 'Usage' in run(['/usr/local/bin/buzz','--help'])
assert 'workshop refresh' in run(['/usr/local/bin/hermes','update'],64)
assert not Path('/etc/hermes-experiment/config.yaml').exists(),'Fixture requires an unconfigured runtime'
run(['/usr/local/bin/hermes','chat','--oneshot','-q','synthetic_not_executed'],78)
assert pin['baseVersion'] in run(['/usr/local/bin/hermes', '--profile', 'default', '--version'])
assert not Path('/var/run/docker.sock').exists()
assert not Path('/run/hermes-diary/control.sock').exists()
assert Path('/home/workshop/.pg0').resolve()==Path('/home/workshop/.hindsight/pg0')
assert Path('/home/workshop/.hermes/SOUL.md').read_bytes()==(SDK/'share/hermes/SOUL.md').read_bytes()
for platform in ('buzz','email'):
    assert (SDK/'hermes-src/plugins/platforms'/platform).is_dir()
assert Path('/var/lib/systemd/linger/workshop').exists()
print(json.dumps({'hermes':pin['baseVersion'],'upstream':pin['commit'],'sui':sui_version,'link_cli':link_version,
                  'opensandbox':importlib.metadata.version('opensandbox'),
                  'buzz_help':True,'native_buzz_email_assets':True,'unchanged_default_soul':True,
                  'runtime_update_rejected':True,'unconfigured_chat_rejected':True,
                  'explicit_default_profile_version_verified':True,'docker_socket_absent':True,
                  'private_diary_control_absent':True,'pg0_state_link':True,'user_linger':True}))
