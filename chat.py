"""A private website conversation bridged to one allowlisted LINE account."""
import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, session

chat = Blueprint('chat', __name__)


def connect():
    path = Path(current_app.config['DATABASE_PATH'])
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def init_db(app):
    with app.app_context(), connect() as db:
        db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            direction TEXT NOT NULL, name TEXT NOT NULL, body TEXT NOT NULL,
            status TEXT NOT NULL, created REAL NOT NULL, request_id TEXT,
            retry_key TEXT, updated REAL NOT NULL,
            UNIQUE(conversation_id, request_id));
        CREATE TABLE IF NOT EXISTS webhook_events (id TEXT PRIMARY KEY, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS rate_events (ip TEXT NOT NULL, created REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS rate_time ON rate_events(created);
        CREATE INDEX IF NOT EXISTS message_thread ON messages(conversation_id, id);
        ''')


def enabled():
    return all(current_app.config.get(k) for k in
               ('LINE_CHANNEL_ACCESS_TOKEN', 'LINE_CHANNEL_SECRET', 'LINE_ADMIN_USER_ID'))


def line_post(endpoint, payload, retry_key=None):
    headers = {'Authorization': 'Bearer ' + current_app.config['LINE_CHANNEL_ACCESS_TOKEN'],
               'Content-Type': 'application/json'}
    if retry_key:
        headers['X-Line-Retry-Key'] = retry_key
    req = urllib.request.Request('https://api.line.me/v2/bot/message/' + endpoint,
                                 data=json.dumps(payload, ensure_ascii=False).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            return response.status
    except urllib.error.HTTPError as error:
        if error.code == 409 and retry_key and error.headers.get('x-line-accepted-request-id'):
            return 200
        raise RuntimeError('LINE request failed') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError('LINE request failed') from None


def error(code, status):
    return jsonify(error=code), status


def valid_csrf():
    token = session.get('csrf', '')
    supplied = request.headers.get('X-CSRF-Token', '')
    return bool(token and hmac.compare_digest(token.encode(), supplied.encode()))


@chat.get('/api/chat/session')
def get_session():
    if not enabled():
        return jsonify(enabled=False)
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    session.permanent = True
    return jsonify(enabled=True, csrf=session['csrf'])


@chat.get('/api/chat/messages')
def get_messages():
    cid = session.get('conversation')
    if not cid:
        return jsonify(messages=[])
    with connect() as db:
        rows = db.execute('SELECT id, direction, name, body, status, created, request_id FROM messages '
                          'WHERE conversation_id=? ORDER BY id DESC LIMIT 100', (cid,)).fetchall()
    return jsonify(messages=[dict(row) for row in reversed(rows)])


@chat.post('/api/chat/messages')
def post_message():
    if not enabled():
        return error('unavailable', 503)
    if not valid_csrf():
        return error('session_expired', 403)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error('invalid_message', 400)
    name, body, request_id = (payload.get(k, '') for k in ('name', 'message', 'request_id'))
    if not all(isinstance(v, str) for v in (name, body, request_id)):
        return error('invalid_message', 400)
    name, body = name.strip(), body.strip()
    if not (1 <= len(name) <= 60 and 1 <= len(body) <= 1500 and re.fullmatch(r'[a-f0-9-]{36}', request_id)):
        return error('invalid_message', 400)
    if payload.get('website'):  # Honeypot, never accept or pretend to send spam.
        return error('invalid_message', 400)
    now = time.time()
    ip = hmac.new(current_app.secret_key.encode(), request.remote_addr.encode(), hashlib.sha256).hexdigest()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        cid = session.get('conversation')
        conversation = db.execute('SELECT * FROM conversations WHERE id=?', (cid,)).fetchone() if cid else None
        previous = db.execute('SELECT * FROM messages WHERE conversation_id=? AND request_id=?',
                              (cid, request_id)).fetchone()
        if previous:
            if previous['body'] != body or previous['name'] != name:
                return error('invalid_message', 409)
            if previous['status'] == 'accepted':
                return jsonify(status='accepted')
            if previous['status'] == 'sending' and now - previous['updated'] < 20:
                return error('sending', 409)
            if now - previous['created'] > 23 * 3600:
                return error('retry_expired', 409)
        # Count every outbound attempt, including retries, before creating storage.
        recent = db.execute('SELECT count(*) FROM rate_events WHERE ip=? AND created>?', (ip, now - 60)).fetchone()[0]
        daily = db.execute('SELECT count(*) FROM rate_events WHERE created>?', (now - 86400,)).fetchone()[0]
        if recent >= 5 or daily >= current_app.config['CHAT_GLOBAL_DAILY_LIMIT']:
            return error('rate_limited', 429)
        db.execute('INSERT INTO rate_events VALUES (?,?)', (ip, now))
        if not conversation:
            cid, code = secrets.token_urlsafe(32), secrets.token_hex(6).upper()
            db.execute('INSERT INTO conversations VALUES (?, ?, ?)', (cid, code, now))
            session['conversation'] = cid
        else:
            code = conversation['code']
        if previous:
            msg_id, retry_key = previous['id'], previous['retry_key']
            db.execute('UPDATE messages SET status=?, updated=? WHERE id=?', ('sending', now, msg_id))
        else:
            retry_key = str(uuid.uuid4())
            cursor = db.execute('INSERT INTO messages (conversation_id,direction,name,body,status,created,request_id,retry_key,updated) '
                                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                (cid, 'student', name, body, 'sending', now, request_id, retry_key, now))
            msg_id = cursor.lastrowid
    text = f'網站留言 [{code}]\n姓名：{name}\n\n{body}\n\n回覆此學生，請傳送：\n/reply {code} 您的回覆內容'
    try:
        line_post('push', {'to': current_app.config['LINE_ADMIN_USER_ID'],
                          'messages': [{'type': 'text', 'text': text}]}, retry_key)
    except RuntimeError:
        with connect() as db:
            db.execute('UPDATE messages SET status=?, updated=? WHERE id=?', ('failed', time.time(), msg_id))
        return error('delivery_failed', 502)
    with connect() as db:
        db.execute('UPDATE messages SET status=?, updated=? WHERE id=?', ('accepted', time.time(), msg_id))
    return jsonify(status='accepted'), 201


@chat.post('/line/webhook')
def webhook():
    if not enabled():
        return error('unavailable', 503)
    raw = request.get_data()
    expected = base64.b64encode(hmac.new(current_app.config['LINE_CHANNEL_SECRET'].encode(), raw, hashlib.sha256).digest()).decode()
    if not hmac.compare_digest(expected.encode(), request.headers.get('X-Line-Signature', '').encode()):
        return error('invalid_signature', 400)
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return error('invalid_payload', 400)
    if not isinstance(payload, dict) or not isinstance(payload.get('events'), list):
        return error('invalid_payload', 400)
    for event in payload['events']:
        if not isinstance(event, dict):
            continue
        source, message = event.get('source') or {}, event.get('message') or {}
        if not isinstance(source, dict) or not isinstance(message, dict):
            continue
        if (source.get('type') != 'user' or source.get('userId') != current_app.config['LINE_ADMIN_USER_ID']
                or event.get('type') != 'message' or message.get('type') != 'text'):
            continue
        body, event_id = message.get('text'), event.get('webhookEventId')
        if not isinstance(body, str) or not isinstance(event_id, str) or not event_id:
            continue
        match = re.fullmatch(r'/reply\s+([A-Fa-f0-9]{12})\s+([\s\S]{1,4000})', body.strip())
        ack = '請使用 /reply 對話代碼 回覆內容；對話代碼位於網站留言通知。'
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM webhook_events WHERE id=?', (event_id,)).fetchone():
                continue
            db.execute('INSERT INTO webhook_events VALUES (?,?)', (event_id, time.time()))
            if match:
                conversation = db.execute('SELECT id FROM conversations WHERE code=?', (match[1].upper(),)).fetchone()
                if conversation and match[2].strip():
                    timestamp = event.get('timestamp')
                    created = timestamp / 1000 if isinstance(timestamp, (float, int)) else time.time()
                    db.execute('INSERT INTO messages (conversation_id,direction,name,body,status,created,updated) VALUES (?,?,?,?,?,?,?)',
                               (conversation['id'], 'professor', 'Wei-Chen Wu', match[2].strip(), 'accepted', created, time.time()))
                    ack = f'已回覆網站對話 {match[1].upper()}。學生回到原瀏覽器即可查看。'
                else:
                    ack = '找不到此對話，可能已超過保存期限；請確認對話代碼。'
        # The website reply is already committed. A failed acknowledgement must not roll it back.
        if event.get('replyToken'):
            try:
                line_post('reply', {'replyToken': event['replyToken'], 'messages': [{'type': 'text', 'text': ack}]})
            except RuntimeError:
                current_app.logger.warning('LINE acknowledgement unavailable; website reply is retained.')
    return jsonify(ok=True)


def cleanup():
    cutoff = time.time() - current_app.config['CHAT_RETENTION_DAYS'] * 86400
    with connect() as db:
        db.execute('DELETE FROM messages WHERE created < ?', (cutoff,))
        db.execute('DELETE FROM conversations WHERE created < ? AND NOT EXISTS '
                   '(SELECT 1 FROM messages WHERE conversation_id=conversations.id)', (cutoff,))
        db.execute('DELETE FROM webhook_events WHERE created < ?', (cutoff,))
        db.execute('DELETE FROM rate_events WHERE created < ?', (time.time() - 86400,))
