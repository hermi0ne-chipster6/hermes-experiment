"""Real Linux desktop capture and offline dconf database operations on owned fixtures."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import time

from functional import normalized, terminate


def desktop_build_value(raw):
    """Keep the direct desktop contract, including an action's nested result."""
    value = raw.get('structuredContent')
    if value is None:
        # REA's canonical JSON precedes any forwarded driver text/images.
        texts = [block['text'] for block in raw.get('content', []) if block.get('type') == 'text']
        assert texts, 'Desktop response omitted structured content and JSON text'
        value = json.loads(texts[0])
    # `result` is a domain field of act_on_build_computer, not an envelope.
    assert isinstance(value, dict) and isinstance(value.get('computer_id'), str), value
    return value


X11_FIXTURE = r'''#!/usr/bin/python3
import ctypes as c, os, time
from pathlib import Path
x=c.CDLL('libX11.so.6')
p=c.c_void_p;u=c.c_ulong;i=c.c_int
x.XOpenDisplay.argtypes=[c.c_char_p];x.XOpenDisplay.restype=p
x.XDefaultRootWindow.argtypes=[p];x.XDefaultRootWindow.restype=u
x.XCreateSimpleWindow.argtypes=[p,u,i,i,c.c_uint,c.c_uint,c.c_uint,u,u];x.XCreateSimpleWindow.restype=u
x.XStoreName.argtypes=[p,u,c.c_char_p]
x.XInternAtom.argtypes=[p,c.c_char_p,i];x.XInternAtom.restype=u
x.XChangeProperty.argtypes=[p,u,u,u,i,i,p,i]
x.XMapWindow.argtypes=[p,u];x.XFlush.argtypes=[p];x.XCloseDisplay.argtypes=[p]
class ClassHint(c.Structure):_fields_=[('res_name',c.c_char_p),('res_class',c.c_char_p)]
x.XSetClassHint.argtypes=[p,u,c.POINTER(ClassHint)]
d=x.XOpenDisplay(None)
assert d,'Owned X11 display unavailable'
w=x.XCreateSimpleWindow(d,x.XDefaultRootWindow(d),20,20,400,200,1,0,0xffffff)
x.XStoreName(d,w,b'Hermes SDK desktop fixture')
x.XSetClassHint(d,w,c.byref(ClassHint(b'hermesfixture',b'HermesFixture')))
pid=u(os.getpid())
x.XChangeProperty(d,w,x.XInternAtom(d,b'_NET_WM_PID',0),6,32,0,c.byref(pid),1)
x.XMapWindow(d,w);x.XFlush(d)
time.sleep(2)
state=Path(os.environ['XDG_CONFIG_HOME'])/'hermesfixture/state.ini'
state.write_text('marker=hermes-desktop-after\n')
time.sleep(6)
x.XCloseDisplay(d)
'''


def run_desktop_cases(command, output, work, test, unavailable, package_root, node_command=None):
    node_command = node_command or str(package_root.resolve().parents[2] / 'node/bin/node')
    def desktop_dconf():
        executable = shutil.which('dconf')
        if not executable:
            raise unavailable('SDK runtime dependency dconf-cli is missing')
        case = work / 'desktop-dconf'
        keys = case / 'keyfiles'
        keys.mkdir(parents=True, exist_ok=True)
        (keys / 'fixture').write_text("[org/hermesfixture]\nmarker='sdk-dconf-value'\ncount=42\n")
        database = case / 'fixture.db'
        result = subprocess.run([executable, 'compile', str(database), str(keys)], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        digest = hashlib.sha256(database.read_bytes()).hexdigest()
        script = case / 'read.mjs'
        script.write_text("import {pathToFileURL} from 'node:url';\nconst {dumpDconfDatabase}=await import(pathToFileURL(process.argv[2]));\nconsole.log(JSON.stringify(await dumpDconfDatabase(process.argv[3],process.env)));\n")
        result = subprocess.run([node_command, str(script), str(package_root / 'dist/desktop/DconfDatabaseReader.js'), str(database)], capture_output=True, text=True, timeout=45)
        (case / 'reader.stdout').write_text(result.stdout)
        (case / 'reader.stderr').write_text(result.stderr)
        assert result.returncode == 0, result.stderr
        dump = json.loads(result.stdout)
        assert dump['ok'] is True and '[org/hermesfixture]' in dump['text'] and "marker='sdk-dconf-value'" in dump['text'] and 'count=42' in dump['text'], dump
        assert hashlib.sha256(database.read_bytes()).hexdigest() == digest
        return {'assertion': 'Real dconf compile database decoded by unchanged installed REA DconfDatabaseReader with exact string/integer values',
                'database_sha256': digest, 'scope': 'Offline owned database, no user settings or D-Bus service'}

    def desktop_capture():
        for program in ['Xvfb', 'openbox', 'xprop']:
            if not shutil.which(program):
                raise unavailable(f'Desktop fixture requires {program}; Openbox is test-only window manager')
        case = output / 'desktop-capture'
        case.mkdir(exist_ok=True)
        home = case / 'owned-home'
        config = home / '.config'
        state = config / 'hermesfixture/state.ini'
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text('marker=hermes-desktop-before\n')
        fixture = case / 'hermesfixture'
        fixture.write_text(X11_FIXTURE)
        fixture.chmod(0o755)
        capture = case / 'capture'
        xvfb = wm = None
        try:
            with (case / 'xvfb.stderr').open('wb') as xerrors, (case / 'openbox.stderr').open('wb') as wmerrors:
                xvfb = subprocess.Popen(['Xvfb','-displayfd','1','-screen','0','1024x768x24','-nolisten','tcp'], stdout=subprocess.PIPE, stderr=xerrors)
                with selectors.DefaultSelector() as selector:
                    selector.register(xvfb.stdout, selectors.EVENT_READ)
                    assert selector.select(15), 'Xvfb readiness timed out'
                display = xvfb.stdout.readline().decode().strip()
                assert display.isdigit(), display
                environment = dict(os.environ, DISPLAY=':'+display, HOME=str(home), XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(home/'.local/share'), XDG_CACHE_HOME=str(home/'.cache'))
                wm = subprocess.Popen(['openbox','--sm-disable'], env=environment, stdout=subprocess.DEVNULL, stderr=wmerrors)
                deadline = time.monotonic()+20
                while True:
                    assert wm.poll() is None, 'Openbox exited; see openbox.stderr'
                    listing = subprocess.run(['xprop','-root','-notype','_NET_SUPPORTED'], env=environment, capture_output=True, text=True, timeout=6)
                    if listing.returncode == 0 and '_NET_CLIENT_LIST' in listing.stdout:
                        break
                    assert time.monotonic()<deadline, 'Real EWMH manager did not become ready'
                    time.sleep(.2)
                (case/'xprop-root.txt').write_text(listing.stdout)
                # EOF is an intentional REA stop request. Keep stdin open until
                # the owned application exits naturally, without mock input.
                with (case/'capture.stdout').open('w') as stdout, (case/'capture.stderr').open('w') as stderr:
                    child = subprocess.Popen([*command,'capture-desktop-application','--executable',str(fixture),'--output',str(capture),'--state-path',str(state),'--max-duration-seconds','30','--max-entries','1000','--max-content-bytes','1048576','--json'],
                                             env=environment,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr)
                    try:
                        code = child.wait(timeout=100)
                    finally:
                        child.stdin.close()
                        terminate(child)
                result_text = (case/'capture.stdout').read_text()
                assert code == 0, (case/'capture.stderr').read_text()[-3000:]+result_text[-3000:]
                report = normalized(json.loads(result_text))
                assert report['session']['first_window_ms'] is not None, report['session']
                assert any('Hermes SDK desktop fixture' in json.dumps(window) for window in report['session']['windows']), report['session']
                assert any(window['pid'] == report['session']['launch_pid'] and window['application'] is True for window in report['session']['windows']), report['session']
                assert report['session']['exit'] == {'code': 0, 'signal': None}, report['session']
                assert report['session']['end_reason']=='application_exited' and report['session']['cleanup']['verified'] is True, report['session']
                retained = {entry['sha256'] for cp in report['state']['checkpoints'] for entry in cp['retained'] if entry['path']==str(state)}
                for data in [b'marker=hermes-desktop-before\n',b'marker=hermes-desktop-after\n']:
                    assert hashlib.sha256(data).hexdigest() in retained, report['state']
                inspected = subprocess.run([*command,'inspect-desktop-application-state',str(capture),'--json'],env=environment,capture_output=True,text=True,timeout=60)
                (case/'state.stdout').write_text(inspected.stdout);(case/'state.stderr').write_text(inspected.stderr)
                assert inspected.returncode == 0, inspected.stderr+inspected.stdout
                state_report=normalized(json.loads(inspected.stdout))
                assert 'hermes-desktop-before' in json.dumps(state_report) and 'hermes-desktop-after' in json.dumps(state_report),state_report
                return {'assertion':'Real Xvfb/Openbox EWMH window captured with owning process and changed INI state; both retained versions decoded through CLI',
                        'window_count':len(report['session']['windows']),'cleanup_verified':True,'scope':'Owned local desktop capture/state; no model-driven desktop build'}
        finally:
            if wm:terminate(wm)
            if xvfb:terminate(xvfb)

    test('desktop-dconf',desktop_dconf)
    test('desktop-capture',desktop_capture)


def run_desktop_build_case(command, output, work, test, unavailable, package_root, node_command=None):
    """Model-free real AgentEnv lifecycle; host prerequisites remain visible."""
    from functional import MCP
    import base64
    import uuid
    node_command = node_command or str(package_root.resolve().parents[2] / 'node/bin/node')

    def desktop_build():
        case = output / 'desktop-build'
        case.mkdir(exist_ok=True)
        archive = Path(os.environ.get('REA_BUILD_COMPUTER_REA_ARCHIVE', str(work/'desktop-build-runtime.tar.xz')))
        environment = dict(os.environ, REA_BUILD_COMPUTER_REA_ARCHIVE=str(archive))
        doctor = subprocess.run([*command, 'doctor', '--provider', 'desktop_build', '--json'], env=environment, capture_output=True, text=True, timeout=90)
        (case/'doctor.json').write_text(doctor.stdout)
        (case/'doctor.stderr').write_text(doctor.stderr)
        (case/'doctor.exit').write_text(str(doctor.returncode)+'\n')
        report = json.loads(doctor.stdout)
        checks = {entry['name']:entry for entry in report['checks']}
        for name in ['desktop_build-docker-daemon', 'desktop_build-disk']:
            assert name in checks, f'Desktop doctor omitted required diagnosis {name}'
            if checks[name]['ok'] is not True:
                raise unavailable(f"Actual upstream doctor prerequisite refused: {json.dumps(checks[name])}; no image pull or capacity override attempted")
        if not archive.is_file():
            # Same unchanged producer used by desktop-runtime-pack. A solo case
            # must not rely on another test having executed first.
            env = dict(environment, npm_config_userconfig=os.devnull, npm_config_audit='false', npm_config_fund='false')
            for name in ['npm_execpath','NPM_TOKEN','NODE_AUTH_TOKEN']:
                env.pop(name,None)
            with (case/'runtime-pack.log').open('w') as log:
                packed=subprocess.run([node_command,str(package_root/'scripts/pack-build-computer-runtime.mjs'),str(archive)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
            assert packed.returncode==0, 'Real runtime archive producer failed; see runtime-pack.log'
        archive_digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        server=MCP(['/usr/bin/env',f'REA_BUILD_COMPUTER_REA_ARCHIVE={archive}',*command,'mcp'],case)
        computer=None
        closed=None
        images=[]
        image_python=package_root.resolve().parents[2]/'providers/agentenv-venv/bin/python'
        try:
            server.request('initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'hermes-sdk-real-desktop-build','version':'1'}})
            server.send({'jsonrpc':'2.0','method':'notifications/initialized'})

            def call(name,arguments,timeout=240):
                nonlocal computer
                server.serial+=1
                raw=server.request('tools/call',{'name':name,'arguments':arguments},timeout)
                (case/f'{server.serial:03d}-{name}.json').write_text(json.dumps(raw,indent=2)+'\n')
                if raw.get('isError'):
                    # An upstream failed-start response may retain a computer
                    # for retryable cleanup. Only recover its explicit ID.
                    def identifier(value):
                        if isinstance(value,dict):
                            if isinstance(value.get('computer_id'),str):
                                try:return str(uuid.UUID(value['computer_id']))
                                except ValueError:pass
                            return next((found for child in value.values() if (found:=identifier(child))),None)
                        if isinstance(value,list):return next((found for child in value if (found:=identifier(child))),None)
                        return None
                    payloads=[raw.get('structuredContent')]
                    for block in raw.get('content',[]):
                        if block.get('type')=='text':
                            try:payloads.append(json.loads(block['text']))
                            except (ValueError,KeyError):pass
                    computer=computer or identifier(payloads)
                    raise RuntimeError(f'{name} failed; complete upstream response retained in {case}: '+json.dumps(raw)[:1800])
                value=desktop_build_value(raw)
                if name=='start_build_computer':computer=value['computer_id']
                assert value['computer_id']==computer, value
                returned_images=[]
                for index,block in enumerate(raw.get('content',[])):
                    if block.get('type')=='image':
                        data=base64.b64decode(block['data'],validate=True)
                        assert data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff'), 'Screenshot is not an actual PNG/JPEG'
                        image=case/f'{server.serial:03d}-{index}.image'
                        image.write_bytes(data)
                        decoded=subprocess.run([str(image_python),'-I',str(Path(__file__).with_name('desktop_image.py')),str(image)],capture_output=True,text=True,timeout=30)
                        assert decoded.returncode==0, decoded.stderr
                        metadata=json.loads(decoded.stdout)
                        returned_images.append({'file':str(image),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),**metadata})
                images.extend(returned_images)
                if name in ['start_build_computer','start_build_capture'] or arguments.get('screenshot') is True:
                    assert returned_images, f'{name} returned no actual screenshot'
                return value

            started=call('start_build_computer',{'source':{'kind':'request','desktop_entry':'debian-xterm','window_class':'XTerm','install':{'kind':'archive','package':'xterm'}},'screenshot':{'format':'png'}},timeout=1800)
            assert started['sandbox_id'] and computer
            # The command is the caller-owned xterm target launched by capture,
            # not an invented arbitrary-shell MCP operation.
            script='printf "[fixture]\\nmarker=hermes-build-before\\n" > "$HOME/sdk-build-fixture.ini"; printf "Hermes fixture: enter value\\n"; IFS= read -r fixture_value; printf "[fixture]\\nmarker=%s\\n" "$fixture_value" > "$HOME/sdk-build-fixture.ini"; printf "Recorded %s\\n" "$fixture_value"; sleep 120'
            captured=call('start_build_capture',{'computer_id':computer,'arguments':['-e','/bin/sh','-c',script],'state_paths':['sdk-build-fixture.ini']},timeout=600)
            assert captured['desktop_entry']=='debian-xterm',captured
            seed=call('mark_build_checkpoint',{'computer_id':computer,'name':'seed'})
            assert seed['checkpoint']['name']=='seed',seed
            assert seed['checkpoint']['retained_files']>0 and seed['checkpoint']['retained_bytes']>0,seed
            typed=call('act_on_build_computer',{'computer_id':computer,'action':'type','text':'hermes-build-after\n'})
            assert typed['action']=='type' and type(typed['action_index']) is int and typed['action_index']>=0,typed
            waited=call('act_on_build_computer',{'computer_id':computer,'action':'wait','ms':1000,'screenshot':True})
            assert waited['action']=='wait' and waited['action_index']==typed['action_index']+1,waited
            end=call('mark_build_checkpoint',{'computer_id':computer,'name':'end'})
            assert end['checkpoint']['name']=='end',end
            assert 'sdk-build-fixture.ini' in end['checkpoint']['changed_files'],end
            assert end['checkpoint']['retained_files']>0 and end['checkpoint']['retained_bytes']>0,end
            stopped=call('stop_build_capture',{'computer_id':computer},timeout=600)
            assert stopped['package']['name']=='xterm',stopped
            assert {'seed','end'} <= {checkpoint['name'] for checkpoint in stopped['checkpoints']},stopped
            draft=stopped['draft']
            assert draft is not None and draft['seed_checkpoint']=='seed' and draft['end_checkpoint']=='end',stopped
            changed=next((entry for entry in draft['files'] if entry['file']=='sdk-build-fixture.ini'),None)
            assert changed is not None, draft
            assert any(value['kind']=='changed' and value['before']=='hermes-build-before' and value['after']=='hermes-build-after' for value in changed['values']), changed
            assert images, 'No actual screenshot content was returned by live driver'
            closed=call('close_build_computer',{'computer_id':computer},timeout=300)
            assert closed['computer_id']==computer and closed['teardown'] in ['agentenv','container_label'],closed
            computer=None
            return {'assertion':'Real no-model AgentEnv computer ran owned xterm command; computer typing changed retained INI values; screenshots decoded and teardown confirmed',
                    'sandbox_id':started['sandbox_id'],'runtime_archive_sha256':archive_digest,'screenshots':images,'teardown':closed['teardown'],
                    'scope':'Real local Docker desktop lifecycle and captured state; no external model endpoint or A-side orchestration'}
        finally:
            try:
                if computer:
                    # Preserve any cleanup failure instead of treating process
                    # termination as proof that a Docker container disappeared.
                    result=server.call('close_build_computer',{'computer_id':computer},timeout=300)
                    (case/'cleanup-result.json').write_text(json.dumps(result,indent=2)+'\n')
                    assert result['computer_id']==computer and result['teardown'] in ['agentenv','container_label'],result
            finally:
                server.close()
            if closed and archive==work/'desktop-build-runtime.tar.xz':
                archive.unlink(missing_ok=True)

    test('desktop-build',desktop_build)
