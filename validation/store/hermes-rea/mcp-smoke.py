"""Probe the real REA MCP over stdio (or an operator-supplied SSH argv)."""
import argparse
import json
import selectors
import subprocess
import tempfile
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output')
parser.add_argument('--call')
parser.add_argument('--arguments-file')
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command[1:] if args.command[:1] == ['--'] else args.command
command = command or ['sudo', '-u', 'rea', '/usr/local/bin/hermes-rea-stdio']
with tempfile.TemporaryFile() as errors:
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=errors, text=True)
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ)
    def send(value):
        child.stdin.write(json.dumps(value)+'\n')
        child.stdin.flush()
    def receive(wanted, timeout=90):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            if not selector.select(1):
                continue
            line = child.stdout.readline()
            if not line:
                raise RuntimeError('Native MCP closed before its response; no compatibility pass')
            message = json.loads(line)
            if message.get('id') == wanted:
                if 'error' in message:
                    raise RuntimeError('Native MCP returned a protocol error')
                return message['result']
        raise RuntimeError('Native MCP response deadline exceeded')
    try:
        send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{
            'protocolVersion':'2024-11-05','capabilities':{},
            'clientInfo':{'name':'hermes-sdk-synthetic-probe','version':'1'}}})
        initialized = receive(1)
        send({'jsonrpc':'2.0','method':'notifications/initialized'})
        send({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})
        tools = receive(2)['tools']
        assert tools, 'Native server advertised no tools'
        result = {'initialize':initialized,'tools':tools}
        if args.call:
            arguments = json.loads(Path(args.arguments_file).read_text()) if args.arguments_file else {}
            send({'jsonrpc':'2.0','id':3,'method':'tools/call',
                  'params':{'name':args.call,'arguments':arguments}})
            result['call_result'] = receive(3, 300)
        if args.output:
            Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
        if result.get('call_result', {}).get('isError'):
            raise RuntimeError('Native MCP tool returned isError; see the saved result')
        print(json.dumps({'server':initialized.get('serverInfo'),
                          'protocol':initialized.get('protocolVersion'),
                          'tool_count':len(tools)}))
    finally:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
