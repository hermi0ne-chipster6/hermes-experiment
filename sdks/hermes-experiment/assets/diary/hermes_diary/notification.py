"""Opt-in notifications and agent email through Hermes' native sender."""

from email.utils import parseaddr
import json
import os
import subprocess


_DELIVERY_FAILED = 'Native message delivery failed; no delivery confirmation.'
_INVALID_RESULT = 'Native sender returned an invalid result; no delivery confirmation.'


def _deliver(target, text):
    if not isinstance(text, str) or not text.strip() or len(text) > 4096 or 'MEDIA:' in text.upper():
        return json.dumps({'error':'Provide 1–4096 characters of text; attachments are not supported.'})
    if not target:
        return json.dumps({'error':'Operator notification destination is not configured.'})
    try:
        result = subprocess.run(
            ['/usr/local/bin/hermes', 'send', '--json', '--to', target, '--', text],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return json.dumps({'error': _DELIVERY_FAILED})
    if result.returncode:
        return json.dumps({'error': _DELIVERY_FAILED})
    try:
        receipt = json.loads(result.stdout)
    except (ValueError, RecursionError):
        return json.dumps({'error': _INVALID_RESULT})
    if not isinstance(receipt, dict):
        return json.dumps({'error': _INVALID_RESULT})
    success = receipt.get('success')
    if receipt.get('error') or success is False:
        return json.dumps({'error': _DELIVERY_FAILED})
    # Hermes can report both success and skipped for a deduplicated notification.
    skipped = receipt.get('skipped', False)
    if skipped is True:
        return json.dumps({'error': 'Native sender skipped delivery; no delivery confirmation.'})
    if skipped is not False or success is not True:
        return json.dumps({'error': _INVALID_RESULT})
    return json.dumps({'delivered':True, 'financial_authorization':False})


def notify(arguments, **kwargs):
    # Operator notifications have no model-selected destination.
    channel = os.environ.get('BUZZ_HOME_CHANNEL','')
    email = os.environ.get('EMAIL_HOME_ADDRESS','')
    target = 'buzz:'+channel if channel else 'email:'+email if email else ''
    return _deliver(target, arguments.get('text') if isinstance(arguments,dict) else None)


def send_email(arguments, **kwargs):
    if not os.environ.get('EMAIL_ADDRESS'):
        return json.dumps({'error':'The dedicated native email identity is not configured.'})
    recipient = arguments.get('recipient') if isinstance(arguments,dict) else None
    if (not isinstance(recipient,str) or not 1 <= len(recipient) <= 254 or
            any(char.isspace() or char in '\x00<>,;' for char in recipient)):
        return json.dumps({'error':'Provide one plain recipient email address; headers and display names are not accepted.'})
    display, address = parseaddr(recipient)
    if display or address != recipient or address.count('@') != 1 or not all(address.split('@')):
        return json.dumps({'error':'Recipient address is invalid.'})
    return _deliver('email:'+address, arguments.get('text'))


def register(ctx):
    ctx.register_tool(name='notify_operator',toolset='hermes_notifications',schema={
        'name':'notify_operator', 'description':'Send a plain-text notification to the configured operator through native Hermes Buzz/email. This grants no financial authorization.',
        'parameters':{'type':'object','properties':{'text':{'type':'string','maxLength':4096}},'required':['text'],'additionalProperties':False}}, handler=notify)
    ctx.register_tool(name='send_agent_email',toolset='hermes_notifications',schema={
        'name':'send_agent_email', 'description':'Send plain-text email from the operator-configured dedicated agent mailbox through the native Hermes email adapter. Cannot select a From identity, attach files, or grant financial authorization.',
        'parameters':{'type':'object','properties':{'recipient':{'type':'string','maxLength':254},'text':{'type':'string','maxLength':4096}},'required':['recipient','text'],'additionalProperties':False}}, handler=send_email)
