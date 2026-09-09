import base64
import hashlib
import hmac
import json
import time
import uuid
import urllib.error
from email.message import Message
from unittest.mock import Mock

import pytest

from app import create_app
from chat import connect, cleanup, line_post


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret', 'DATABASE_PATH': str(tmp_path / 'chat.sqlite3'),
                      'LINE_CHANNEL_SECRET': 'line-test-secret', 'LINE_CHANNEL_ACCESS_TOKEN': 'fake-token',
                      'LINE_ADMIN_USER_ID': 'U' + '1' * 32})
    return app


@pytest.fixture
def transport(monkeypatch):
    mock = Mock(return_value=200)
    monkeypatch.setattr('chat.line_post', mock)
    return mock


def post(client, message='您好！我對量子金融有興趣。', rid=None):
    csrf = client.get('/api/chat/session').json['csrf']
    return client.post('/api/chat/messages', json={'name': '同學', 'message': message, 'request_id': rid or str(uuid.uuid4())},
                       headers={'X-CSRF-Token': csrf})


def signed(client, app, events, raw=None, signature=None):
    data = raw if raw is not None else json.dumps({'events': events}, ensure_ascii=False).encode()
    sig = signature or base64.b64encode(hmac.new(app.config['LINE_CHANNEL_SECRET'].encode(), data, hashlib.sha256).digest()).decode()
    return client.post('/line/webhook', data=data, headers={'X-Line-Signature': sig, 'Content-Type': 'application/json'})


def event(app, code, eid='event-1', text='歡迎討論！\n請分享你的想法。'):
    return {'type': 'message', 'webhookEventId': eid, 'timestamp': int(time.time()*1000),
            'source': {'type': 'user', 'userId': app.config['LINE_ADMIN_USER_ID']},
            'replyToken': 'fake-reply-token', 'message': {'type': 'text', 'text': f'/reply {code} {text}'}}


def code_for(app, client):
    with client.session_transaction() as session:
        cid = session['conversation']
    with app.app_context(), connect() as db:
        return db.execute('SELECT code FROM conversations WHERE id=?', (cid,)).fetchone()[0]


def test_end_to_end_two_conversations_are_isolated(app, transport):
    alice, bob = app.test_client(), app.test_client()
    assert post(alice).status_code == 201
    assert post(bob, '我是另一位學生').status_code == 201
    alice_code = code_for(app, alice)
    bob_code = code_for(app, bob)
    assert alice_code != bob_code
    assert transport.call_args_list[0].args[0] == 'push'
    assert '/reply ' + alice_code in transport.call_args_list[0].args[1]['messages'][0]['text']
    reply = event(app, alice_code)
    assert signed(app.test_client(), app, [reply]).status_code == 200
    assert len(alice.get('/api/chat/messages').json['messages']) == 2
    assert len(bob.get('/api/chat/messages?code=' + alice_code).json['messages']) == 1
    assert alice.get('/api/chat/messages').json['messages'][-1]['body'] == '歡迎討論！\n請分享你的想法。'
    assert app.test_client().get('/api/chat/messages?code=' + alice_code).json['messages'] == []


def test_signature_validation_and_empty_verification(app):
    client = app.test_client()
    assert signed(client, app, []).status_code == 200
    assert signed(client, app, [], signature='wrong').status_code == 400
    assert client.post('/line/webhook', json={'events': []}).status_code == 400
    assert signed(client, app, [], raw=b'not json').status_code == 400
    assert signed(client, app, [], raw=b'[]').status_code == 400


@pytest.mark.parametrize('kind', ['other_user', 'group', 'image', 'bad_command', 'unknown_thread'])
def test_only_professor_text_command_can_reply(app, transport, kind):
    client = app.test_client()
    post(client)
    e = event(app, code_for(app, client))
    if kind == 'other_user': e['source']['userId'] = 'U' + '2'*32
    if kind == 'group': e['source']['type'] = 'group'
    if kind == 'image': e['message']['type'] = 'image'
    if kind == 'bad_command': e['message']['text'] = 'hello'
    if kind == 'unknown_thread': e['message']['text'] = '/reply FFFFFFFFFFFF hello'
    assert signed(client, app, [e]).status_code == 200
    assert len(client.get('/api/chat/messages').json['messages']) == 1


def test_webhook_redelivery_deduplication_and_ack_failure(app, transport):
    client = app.test_client()
    post(client)
    e = event(app, code_for(app, client))
    transport.side_effect = RuntimeError('network failed')
    assert signed(client, app, [e, e]).status_code == 200
    e['deliveryContext'] = {'isRedelivery': True}
    assert signed(client, app, [e]).status_code == 200
    assert len(client.get('/api/chat/messages').json['messages']) == 2


def test_failed_push_saved_and_retry_is_idempotent(app, transport):
    client = app.test_client()
    rid = str(uuid.uuid4())
    transport.side_effect = RuntimeError('timeout')
    assert post(client, rid=rid).status_code == 502
    retry_key = transport.call_args.args[2]
    assert client.get('/api/chat/messages').json['messages'][0]['status'] == 'failed'
    transport.side_effect = None
    assert post(client, rid=rid).status_code == 201
    assert transport.call_args.args[2] == retry_key
    assert post(client, rid=rid).status_code == 200
    assert transport.call_count == 2
    assert len(client.get('/api/chat/messages').json['messages']) == 1


def test_csrf_validation_and_payload_limits(app, transport):
    client = app.test_client()
    assert client.post('/api/chat/messages', json={}).status_code == 403
    csrf = client.get('/api/chat/session').json['csrf']
    assert client.post('/api/chat/messages', json=[], headers={'X-CSRF-Token': csrf}).status_code == 400
    assert post(client, 'x'*1501).status_code == 400
    assert post(client, ' ').status_code == 400
    assert post(client, rid='../file').status_code == 400
    assert not transport.called


def test_rate_limit_and_honeypot(app, transport):
    client = app.test_client()
    for i in range(5):
        assert post(client, str(i)).status_code == 201
    assert post(client).status_code == 429
    assert transport.call_count == 5
    fresh = app.test_client()
    csrf = fresh.get('/api/chat/session').json['csrf']
    assert fresh.post('/api/chat/messages', json={'name': 'spam', 'message': 'text', 'request_id': str(uuid.uuid4()), 'website': 'spam'}, headers={'X-CSRF-Token': csrf}).status_code == 400


def test_chat_retention(app, transport):
    client = app.test_client()
    post(client)
    with app.app_context(), connect() as db:
        db.execute('UPDATE messages SET created=?', (time.time() - 31*86400,))
        db.execute('UPDATE conversations SET created=?', (time.time() - 31*86400,))
    assert client.get('/api/chat/messages').json['messages'] == []
    assert post(client).status_code == 201


def test_message_content_not_interpreted_as_code(app, transport):
    client = app.test_client()
    text = '<script>alert(1)</script>'
    assert post(client, text).status_code == 201
    assert client.get('/api/chat/messages').json['messages'][0]['body'] == text


def test_cookies_and_security_headers(app):
    client = app.test_client()
    response = client.get('/api/chat/session')
    assert 'HttpOnly' in response.headers['Set-Cookie']
    assert 'SameSite=Lax' in response.headers['Set-Cookie']
    assert response.headers['Cache-Control'] == 'no-store'
    assert "script-src 'self'" in response.headers['Content-Security-Policy']


def test_line_transport_recognizes_accepted_retry_only_with_header(app, monkeypatch):
    headers = Message()
    headers['x-line-accepted-request-id'] = 'original-id'
    mocked = Mock(side_effect=urllib.error.HTTPError('https://api.line.me', 409, 'duplicate', headers, None))
    monkeypatch.setattr('urllib.request.urlopen', mocked)
    with app.app_context():
        assert line_post('push', {'to': 'test'}, 'retry-key') == 200
        request = mocked.call_args.args[0]
        assert request.get_header('X-line-retry-key') == 'retry-key'
        assert request.get_header('Authorization') == 'Bearer fake-token'
        mocked.side_effect = urllib.error.HTTPError('https://api.line.me', 409, 'conflict', Message(), None)
        with pytest.raises(RuntimeError):
            line_post('push', {'to': 'test'}, 'retry-key')


@pytest.mark.parametrize('code', [401, 429, 500])
def test_line_transport_failures_are_not_reported_as_success(app, monkeypatch, code):
    monkeypatch.setattr('urllib.request.urlopen', Mock(side_effect=urllib.error.HTTPError('https://api.line.me', code, 'failure', Message(), None)))
    with app.app_context(), pytest.raises(RuntimeError):
        line_post('push', {'to': 'test'}, 'retry-key')


def test_retry_attempts_are_also_rate_limited(app, transport):
    client = app.test_client()
    transport.side_effect = RuntimeError('outage')
    rid = str(uuid.uuid4())
    for _ in range(5):
        assert post(client, rid=rid).status_code == 502
    assert post(client, rid=rid).status_code == 429
    assert transport.call_count == 5


def test_parallel_redeliveries_are_deduplicated(app, transport):
    from concurrent.futures import ThreadPoolExecutor
    client = app.test_client()
    post(client)
    e = event(app, code_for(app, client))
    def deliver(_):
        return signed(app.test_client(), app, [e]).status_code
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(deliver, range(4))) == [200]*4
    assert len(client.get('/api/chat/messages').json['messages']) == 2
