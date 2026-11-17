"""Exercise the unchanged exported-environment CLI through real loopback HTTP MCP."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
from urllib.parse import urlparse


def verify_environment_http(bundle, package_root, expected_body):
    root = Path(package_root).resolve()
    node = root.parents[2] / 'node/bin/node'
    inputs = bundle / 'envs/hermes-fixture'
    manifest_path, evidence_path = inputs/'manifest.json', inputs/'evidence.json'
    manifest = json.loads(manifest_path.read_text())['normalized_result']
    case = bundle.parent / (bundle.name+'-http-proof')
    case.mkdir()
    env = dict(os.environ, REA_LOG_LEVEL='info')
    # Explicit loopback endpoint and dynamic port never expose the fixture.
    arguments = [str(node),str(root/'scripts/rea.mjs'),'environment-serve',str(manifest_path),
                 '--evidence',str(evidence_path),'--host','127.0.0.1','--port','0','--json']
    child = None
    endpoint = None
    completed = False
    with (case/'server.stdout').open('wb') as stdout, (case/'server.stderr').open('wb') as stderr:
        try:
            child = subprocess.Popen(arguments,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr)
            deadline=time.monotonic()+35
            while endpoint is None:
                assert child.poll() is None, f'Environment CLI exited early: {(case/"server.stderr").read_text()[-2000:]}'
                for line in (case/'server.stderr').read_text(errors='replace').splitlines():
                    try:entry=json.loads(line)
                    except ValueError:continue
                    if entry.get('msg')=='MCP transport listening':endpoint=entry.get('url')
                assert time.monotonic()<deadline,'Environment listener did not announce its endpoint'
                if endpoint is None:time.sleep(.1)
            address=urlparse(endpoint)
            assert address.hostname=='127.0.0.1' and address.path=='/mcp' and address.port
            headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
            sequence=0
            # No proxy or capture-origin request is involved, only owned loopback.
            http=urllib.request.build_opener(urllib.request.ProxyHandler({}))

            def request(method,params,notify=False):
                nonlocal sequence
                sequence+=1
                message={'jsonrpc':'2.0','method':method,'params':params}
                if not notify:message['id']=sequence
                req=urllib.request.Request(endpoint,data=json.dumps(message).encode(),headers=headers,method='POST')
                with http.open(req,timeout=20) as response:
                    body=response.read()
                    session=response.headers.get('Mcp-Session-Id')
                    if session:headers['Mcp-Session-Id']=session
                    media=response.headers.get('Content-Type','')
                    status=response.status
                (case/f'{sequence:03d}-{method.replace("/","-")}.wire').write_bytes(body)
                if notify:
                    assert status in [200,202,204],status
                    return None
                if 'text/event-stream' in media:
                    messages=[json.loads(line[5:].strip()) for line in body.decode().splitlines() if line.startswith('data:') and line[5:].strip()]
                    reply=next((entry for entry in messages if entry.get('id')==sequence),None)
                else:reply=json.loads(body)
                assert reply is not None and reply.get('id')==sequence and 'error' not in reply,reply
                return reply['result']

            initialized=request('initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'hermes-environment-http-proof','version':'1'}})
            headers['MCP-Protocol-Version']=initialized['protocolVersion']
            request('notifications/initialized',{},notify=True)
            tools=[]
            cursor=None
            while True:
                page=request('tools/list',{'cursor':cursor} if cursor else {})
                tools.extend(page['tools']);cursor=page.get('nextCursor')
                if not cursor:break
            assert {tool['name'] for tool in tools}=={tool['name'] for tool in manifest['tools']}
            tool=next(entry for entry in manifest['tools'] if entry['method']=='GET' and entry['path_template']=='/api/items')
            called=request('tools/call',{'name':tool['name'],'arguments':{}})
            assert not called.get('isError'),called
            answer=called['structuredContent']
            assert answer['status']==200 and answer['body']==expected_body,answer
            assert called['_meta']['provenance']['untrusted_content'] is True,called
            assert called['_meta']['provenance']['source']=='analysis_target',called
            with http.open(f'http://127.0.0.1:{address.port}/.well-known/agent-env.json',timeout=10) as response:
                assert response.status==200
                card=json.load(response)
            (case/'agent-env-card.json').write_text(json.dumps(card,indent=2)+'\n')
            child.terminate()
            code=child.wait(timeout=20)
            assert code==143,f'Expected graceful SIGTERM exit143, got {code}'
            stopped=json.loads((case/'server.stdout').read_text())
            assert stopped['status']=='stopped' and stopped['url']==endpoint and stopped['tools']==len(tools),stopped
            assert stopped['state']['served'] is True,stopped
            try:
                connection=socket.create_connection(('127.0.0.1',address.port),timeout=1)
            except OSError:pass
            else:
                connection.close()
                raise AssertionError('Environment HTTP listener remained reachable after exit')
            completed=True
            return {'transport':'Real loopback HTTP MCP initialized and invoked exported fixture tool',
                    'tools':len(tools),'called_tool':tool['name'],'response_body':answer['body'],
                    'served_state':stopped['state'],'shutdown_exit':code,'listener_closed':True,'evidence_directory':str(case)}
        finally:
            if child is not None and child.poll() is None:
                child.terminate()
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill();child.wait()
            (case/'lifecycle.json').write_text(json.dumps({'completed':completed,'exit_code':None if child is None else child.returncode,'endpoint':endpoint},indent=2)+'\n')
