"""Read/search/append CLI and the separately operated writer service."""

import argparse
import json
import os
import sys

from .client import Client
from .server import DiaryServer
from .store import DiaryError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', default=os.environ.get('HERMES_DIARY_SOCKET', '/run/user/1000/hermes-diary.sock'))
    sub = parser.add_subparsers(dest='method', required=True)
    append = sub.add_parser('append')
    append.add_argument('--request-id', required=True)
    append.add_argument('--file', required=True, help='JSON payload file, or - for stdin')
    read = sub.add_parser('read')
    read.add_argument('--after', type=int, default=0)
    read.add_argument('--limit', type=int, default=100)
    search = sub.add_parser('search')
    search.add_argument('query')
    receipt = sub.add_parser('receipt')
    receipt.add_argument('request_id')
    sub.add_parser('commitments')
    sub.add_parser('health')
    serve = sub.add_parser('serve')
    serve.add_argument('--database', required=True)
    serve.add_argument('--operator-uid', type=int, default=None,
                       help='Allow lifecycle metadata from this UID; use only on a separate host-only socket')
    serve.add_argument('--mode', type=lambda value:int(value, 8), default=0o660)
    args = parser.parse_args()
    try:
        if args.method == 'serve':
            with DiaryServer(args.socket, args.database, operator_uid=args.operator_uid, mode=args.mode) as server:
                server.serve_forever()
            return 0
        client = Client(args.socket)
        if args.method == 'append':
            if args.file == '-':
                payload = json.load(sys.stdin)
            else:
                with open(args.file, encoding='utf-8') as stream:
                    payload = json.load(stream)
            result = client.call('append', request_id=args.request_id, payload=payload)
        elif args.method == 'read':
            result = client.call('read', after=args.after, limit=args.limit)
        elif args.method == 'receipt':
            result = client.call('receipt', request_id=args.request_id)
        elif args.method == 'search':
            result = client.call('search', query=args.query)
        else:
            result = client.call(args.method)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, DiaryError) as exc:
        print(f'diary: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
