"""Real Hermes CLI/observer probe against a local synthetic API, never a paid provider.

This uses a built-in-memory profile and an explicit CLI tool selection to
exercise the diary integration and Hermes honoring the fixture's preferences.
"""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

SDK=Path('/var/lib/workshop/sdk/hermes-experiment')
sys.path.insert(0,str(SDK/'diary'))
from hermes_diary.server import DiaryServer
from hermes_diary.client import Client

RUN='a'*32
REQUEST='heartbeat:'+RUN
report={'type':'heartbeat','run_id':RUN,'objectives':['Exercise a synthetic local CLI session'],
        'actions':['Returned this fixture report'],'outcomes':['Local fixture response only'],
        'unfinished':[],'commitments':[]}
requests=[]
agent_requests=[]
class API(BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_GET(self):
        body={'object':'list','data':[{'id':'sdk-fixture','object':'model','owned_by':'local-fixture'}]}
        encoded=json.dumps(body).encode()
        self.send_response(200);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(encoded)));self.end_headers();self.wfile.write(encoded)
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        requests.append({'path':self.path,'body':body})
        content=json.dumps(report)
        is_agent=any(t.get('function',{}).get('name')=='tool_search' for t in body.get('tools',[]))
        if is_agent:agent_requests.append({'path':self.path,'body':body})
        stage=len(agent_requests) if is_agent else 3
        name='tool_search' if stage==1 else 'tool_call'
        arguments=({'queries':['diary','notify_operator','send_agent_email','terminal','read_file','execute_code'],'limit':20} if stage==1 else
                   {'calls':[{'name':'terminal','arguments':{'command':'printf SDK_LOCAL_FALLBACK_TEST'}},
                             {'name':'read_file','arguments':{'path':'/etc/os-release'}}]})
        calls=[{'id':'fixture-'+str(stage),'type':'function','function':{'name':name,'arguments':json.dumps(arguments)}}] if stage<3 else None
        message={'role':'assistant','content':None if calls else content}
        if not is_agent:message['content']='Local fixture session'
        if calls:message['tool_calls']=calls
        finish_reason='tool_calls' if calls else 'stop'
        if self.path.endswith('/responses'):
            raise RuntimeError('Unexpected API mode; fixture supports chat completions only')
        if body.get('stream'):
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
            delta=dict(message)
            if calls:delta['tool_calls']=[dict(calls[0],index=0)]
            for delta,finish in [(delta,None),({},finish_reason)]:
                chunk={'id':'fixture','object':'chat.completion.chunk','created':1,'model':'sdk-fixture',
                       'choices':[{'index':0,'delta':delta,'finish_reason':finish}]}
                self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
        else:
            value={'id':'fixture','object':'chat.completion','created':1,'model':'sdk-fixture',
                   'choices':[{'index':0,'message':message,'finish_reason':finish_reason}],
                   'usage':{'prompt_tokens':100,'completion_tokens':50,'total_tokens':150}}
            encoded=json.dumps(value).encode()
            self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(encoded)));self.end_headers();self.wfile.write(encoded)

with tempfile.TemporaryDirectory(prefix='hermes-native-hooks-') as name:
    root=Path(name);home=root/'home';home.mkdir()
    work=root/'work';work.mkdir()
    shutil.copyfile('/project/original-charter-fixture.md',work/'.hermes.md')
    plugins=home/'plugins';plugins.mkdir()
    for plugin in ('hermes_diary','hermes_notifications'):
        (plugins/plugin).symlink_to(SDK/'plugins'/plugin)
    config={'_config_version':12,'plugins':{'enabled':['hermes_diary','hermes_notifications']},'memory':{'provider':'builtin'},
            'platform_toolsets':{'cli':['hermes_diary','hermes_notifications']},
            'mcp_servers':{},'terminal':{'cwd':str(work)},
            'model':{'default':'sdk-fixture','provider':'custom'}}
    (home/'config.yaml').write_text(json.dumps(config))
    writer=DiaryServer(root/'agent.sock',root/'journal.db')
    api=ThreadingHTTPServer(('127.0.0.1',0),API)
    threads=[threading.Thread(target=server.serve_forever,daemon=True) for server in (writer,api)]
    for thread in threads:thread.start()
    env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(root),'HERMES_HOME':str(home),
         'HERMES_DIARY_SOCKET':str(root/'agent.sock'),'HERMES_HEARTBEAT_RUN_ID':RUN,
         'HERMES_DIARY_REQUEST_ID':REQUEST,'NO_PROXY':'127.0.0.1,localhost'}
    command=[str(SDK/'bin/hermes'),'chat','--oneshot','--quiet','--provider','custom',
             '--base-url',f'http://127.0.0.1:{api.server_port}/v1','--api-key','synthetic-local-only',
             '--model','sdk-fixture','--max-turns','6','--run-budget','120','-q','Run the local diary fixture.']
    try:
        with tempfile.TemporaryFile(mode='w+') as output:
            child=subprocess.Popen(command,cwd=work,env=env,stdin=subprocess.PIPE,
                                   stdout=output,stderr=output,text=True)
            try:child.wait(timeout=300)
            finally:
                child.stdin.close()
                if child.poll() is None:child.terminate();child.wait(timeout=10)
            output.seek(0);text=output.read()
        if child.returncode:
            print(text[-6000:]);raise RuntimeError('Native Hermes fixture failed')
        receipt=Client(root/'agent.sock').call('receipt',request_id=REQUEST)
        assert receipt,'Native observer did not produce a durable receipt'
        records=Client(root/'agent.sock').call('read')
        assert len(records)==1 and records[0]['payload']==report
        assert requests,'No request reached the local synthetic API'
        names={tool['function']['name'] for request in requests for tool in request['body'].get('tools',[])}
        if names == {'tool_search','tool_describe','tool_call'}:
            results=[message['content'] for request in agent_requests for message in request['body'].get('messages',[]) if message.get('role')=='tool']
            (Path('/project')/'native-hook-tool-results.json').write_text(json.dumps(results,indent=2))
            assert len(agent_requests)>=3 and results,'Progressive discovery did not execute'
            assert all(name in results[0] for name in ('diary_read','diary_search','diary_commitments','diary_append','notify_operator','send_agent_email')),results[0]
            denied=results[-1].lower()
            assert ('error' in denied or 'not available' in denied or 'unknown tool' in denied),denied
            assert 'sdk_local_fallback_test' not in denied and 'ubuntu' not in denied,denied
        else:
            assert {'diary_read','diary_search','diary_commitments','diary_append'} <= names,names
        unselected={'terminal','execute_code','read_file','write_file','delegate_task','browser_navigate'}
        assert not names & unselected,names  # This synthetic profile explicitly selects only integration toolsets.
        messages=json.dumps(agent_requests[0]['body'].get('messages',[]))
        assert RUN in messages and 'choose your own objectives' in messages
        charter_marker=next(line for line in (work/'.hermes.md').read_text().splitlines() if line.startswith('#'))
        assert charter_marker in messages,'Native original-charter context missing'
        pin = json.loads((SDK/'share/hermes/core-pin.json').read_text())
        print(json.dumps({'native_hermes':pin['baseVersion'],'upstream':pin['commit'],
                          'api':'local synthetic chat completions',
                          'memory':'builtin fixture only','durable_receipt':True,
                          'tool_names':sorted(names),'requests':len(requests)}))
    finally:
        for server in (writer,api):server.shutdown();server.server_close()
        for thread in threads:thread.join(timeout=2)
        # The pinned CLI may launch a native session worker. Stop only processes
        # bearing this exact synthetic profile before its temporary home is removed.
        import signal
        owned=[]
        marker=('HERMES_HOME='+str(home)).encode()
        for path in Path('/proc').glob('[0-9]*/environ'):
            try:
                if marker in path.read_bytes().split(b'\0'):
                    pid=int(path.parent.name)
                    if pid != os.getpid():os.kill(pid,signal.SIGTERM);owned.append(pid)
            except (OSError,ValueError):pass
        deadline=time.monotonic()+3
        while owned and time.monotonic()<deadline:
            owned=[pid for pid in owned if Path(f'/proc/{pid}').exists()]
            time.sleep(0.1)
        for pid in owned:
            try:
                if marker in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0'):
                    os.kill(pid,signal.SIGKILL)
            except OSError:pass
