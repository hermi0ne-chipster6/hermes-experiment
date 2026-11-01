"""Durable event storage. Deploy under a separate operator-owned OS identity.

SQL triggers are defense in depth, not a security boundary against the database
owner. Agent processes must have access only to the server socket, never this
file or its directory. A record is an account of events, not proof they happened.
"""

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

MAX_PAYLOAD = 65536
ID = re.compile(r'[A-Za-z0-9_.:-]{1,128}\Z')
STATUSES = {'open', 'in_progress', 'blocked', 'fulfilled', 'cancelled'}


class DiaryError(ValueError):
    """Rejected diary input or inconsistent history."""


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def timestamp(value):
    if not isinstance(value, str):
        raise DiaryError('timestamp must be a string')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise DiaryError('invalid timestamp') from exc
    if result.tzinfo is None:
        raise DiaryError('timestamp needs a timezone')
    return result


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise DiaryError('invalid identifier')
    return value


def string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise DiaryError(f'{field} must be a nonempty string')


def strings(value, field):
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise DiaryError(f'{field} must be a list of nonempty strings')


def commitment_view(records, now=None):
    current = {}
    instant = timestamp(now or utcnow())
    for record in records:
        payload = record['payload']
        if payload.get('type') != 'commitment':
            continue
        item = dict(payload)
        key = item['commitment_id']
        item['created_at'] = current.get(key, {}).get('created_at', record['recorded_at'])
        item['updated_at'] = record['recorded_at']
        item['verification'] = 'reported'
        deadline = item.get('deadline')
        item['overdue'] = bool(deadline and timestamp(deadline) < instant and item['status'] not in {'fulfilled', 'cancelled'})
        current[key] = item
    return list(current.values())


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_symlink():
            raise DiaryError('journal must not be a symlink')
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS entries (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL UNIQUE,
                    recorded_at TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS entries_no_update
                    BEFORE UPDATE ON entries BEGIN SELECT RAISE(ABORT, 'append only'); END;
                CREATE TRIGGER IF NOT EXISTS entries_no_delete
                    BEFORE DELETE ON entries BEGIN SELECT RAISE(ABORT, 'append only'); END;
            ''')
        os.chmod(self.path, 0o600)

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA synchronous=FULL')
        return conn

    @staticmethod
    def _receipt(row):
        return {key: row[key] for key in ('sequence', 'request_id', 'recorded_at', 'sha256')}

    @staticmethod
    def _read(conn, after=0, limit=1000):
        rows = conn.execute('SELECT * FROM entries WHERE sequence > ? ORDER BY sequence LIMIT ?', (after, limit))
        return [{**Journal._receipt(row), 'payload': json.loads(row['payload'])} for row in rows]

    def _history(self, conn):
        # Validation must see every commitment, not merely the first response page.
        return [{**self._receipt(row), 'payload': json.loads(row['payload'])}
                for row in conn.execute('SELECT * FROM entries ORDER BY sequence')]

    def _validate(self, payload, conn):
        if not isinstance(payload, dict):
            raise DiaryError('payload must be an object')
        kind = payload.get('type')
        current = {c['commitment_id']: c for c in commitment_view(self._history(conn))}
        if kind == 'heartbeat':
            identifier(payload.get('run_id'))
            for field in ('objectives', 'actions', 'outcomes', 'unfinished'):
                strings(payload.get(field), field)
            refs = payload.get('commitments')
            if not isinstance(refs, list):
                raise DiaryError('commitments reconciliation is required')
            seen = set()
            for ref in refs:
                if not isinstance(ref, dict):
                    raise DiaryError('invalid commitment reference')
                key = identifier(ref.get('commitment_id'))
                if key in seen or key not in current or ref.get('status') != current[key]['status']:
                    raise DiaryError('commitment reference must match recorded status')
                seen.add(key)
            required = {key for key, value in current.items() if value['status'] not in {'fulfilled', 'cancelled'}}
            if not required <= seen:
                raise DiaryError('outstanding commitments were not reconciled')
        elif kind == 'commitment':
            key = identifier(payload.get('commitment_id'))
            for field in ('description', 'counterparty', 'conditions'):
                string(payload.get(field), field)
            if payload.get('deadline') is not None:
                timestamp(payload['deadline'])
            status = payload.get('status')
            if status not in STATUSES:
                raise DiaryError('invalid commitment status')
            previous = current.get(key)
            if previous is None and status != 'open':
                raise DiaryError('commitment must first be established as open')
            if previous:
                if previous['status'] in {'fulfilled', 'cancelled'}:
                    raise DiaryError('closed commitment cannot be silently reopened')
                for field in ('description', 'counterparty', 'deadline', 'conditions'):
                    if payload.get(field) != previous.get(field):
                        raise DiaryError('status event cannot rewrite the original promise')
            if status in {'fulfilled', 'cancelled'}:
                strings(payload.get('evidence'), 'evidence')
                if not payload['evidence']:
                    raise DiaryError('evidence reference required')
            if status == 'cancelled':
                string(payload.get('authorized_agreement'), 'authorized_agreement')
        elif kind in {'run_started', 'run_incomplete'}:
            identifier(payload.get('run_id'))
            if kind == 'run_incomplete':
                string(payload.get('reason'), 'reason')
        elif kind == 'correction':
            identifier(payload.get('supersedes_request_id'))
            string(payload.get('text'), 'text')
            if not conn.execute('SELECT 1 FROM entries WHERE request_id=?', (payload['supersedes_request_id'],)).fetchone():
                raise DiaryError('correction must reference an existing entry')
        else:
            raise DiaryError('unsupported entry type')

    def append(self, request_id, payload):
        identifier(request_id)
        try:
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        except (ValueError, TypeError) as exc:
            raise DiaryError('payload is not valid JSON') from exc
        if len(encoded.encode()) > MAX_PAYLOAD:
            raise DiaryError('entry exceeds size limit')
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with closing(self._connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                old = conn.execute('SELECT * FROM entries WHERE request_id=?', (request_id,)).fetchone()
                if old:
                    if old['sha256'] != digest or old['payload'] != encoded:
                        raise DiaryError('request identifier already has different content')
                    conn.rollback()
                    return self._receipt(old)
                self._validate(payload, conn)
                cursor = conn.execute('INSERT INTO entries(request_id,recorded_at,sha256,payload) VALUES(?,?,?,?)',
                                      (request_id, utcnow(), digest, encoded))
                row = conn.execute('SELECT * FROM entries WHERE sequence=?', (cursor.lastrowid,)).fetchone()
                conn.commit()
                return self._receipt(row)
            except BaseException:
                conn.rollback()
                raise

    def receipt(self, request_id):
        identifier(request_id)
        with closing(self._connect()) as conn:
            row = conn.execute('SELECT * FROM entries WHERE request_id=?', (request_id,)).fetchone()
            return self._receipt(row) if row else None

    def read(self, after=0, limit=1000):
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 1000:
            raise DiaryError('invalid page bounds')
        with closing(self._connect()) as conn:
            return self._read(conn, after, limit)

    def search(self, query, limit=100):
        string(query, 'query')
        if len(query) > 1000 or type(limit) is not int or not 1 <= limit <= 1000:
            raise DiaryError('invalid search bounds')
        with closing(self._connect()) as conn:
            rows = conn.execute('SELECT * FROM entries WHERE instr(lower(payload),lower(?)) > 0 ORDER BY sequence DESC LIMIT ?', (query, limit))
            return [{**self._receipt(row), 'payload': json.loads(row['payload'])} for row in rows]

    def commitments(self, now=None):
        with closing(self._connect()) as conn:
            return commitment_view(self._history(conn), now)
