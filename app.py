import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from chat import chat, cleanup, enabled, init_db
from content_store import ContentStore, ROOT
from labels import LABELS

load_dotenv(ROOT / '.env')


def create_app(test_config=None):
    app = Flask(__name__)
    production = os.getenv('APP_ENV') == 'production'
    secret = os.getenv('SECRET_KEY', '')
    if production and len(secret) < 32 and not test_config:
        raise RuntimeError('Set a persistent SECRET_KEY of at least 32 characters for production.')
    app.config.update(
        SECRET_KEY=secret or secrets.token_urlsafe(48),
        DATABASE_PATH=os.getenv('DATABASE_PATH', str(ROOT / 'instance/chat.sqlite3')),
        LINE_CHANNEL_ACCESS_TOKEN=os.getenv('LINE_CHANNEL_ACCESS_TOKEN', ''),
        LINE_CHANNEL_SECRET=os.getenv('LINE_CHANNEL_SECRET', ''),
        LINE_ADMIN_USER_ID=os.getenv('LINE_ADMIN_USER_ID', ''),
        CHAT_RETENTION_DAYS=int(os.getenv('CHAT_RETENTION_DAYS', '30')),
        CHAT_GLOBAL_DAILY_LIMIT=int(os.getenv('CHAT_GLOBAL_DAILY_LIMIT', '100')),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=production, PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    if os.getenv('TRUST_PROXY') == '1':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    store = ContentStore(app.config.get('CONTENT_DIR'))
    app.extensions['content_store'] = store
    app.register_blueprint(chat)
    init_db(app)

    @app.before_request
    def expire_messages():
        # Maintenance is request-driven so retention works without a paid cron service.
        if request.path.startswith('/api/chat/') or request.path == '/line/webhook':
            cleanup()

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.path.startswith('/api/') or request.path == '/':
            response.headers['Cache-Control'] = 'no-store'
        if production:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.get('/')
    def index():
        lang = 'en' if request.args.get('lang') == 'en' else 'zh'
        docs = store.all(lang)
        total = sum(docs[key]['count'] for key in ('journals', 'conferences', 'books'))
        project_count = sum(docs[key]['count'] for key in ('nstc', 'moe', 'industry', 'other'))
        return render_template('index.html', lang=lang, t=LABELS[lang], docs=docs,
                               publication_count=total, project_count=project_count,
                               version=store.version(), chat_enabled=enabled(),
                               retention=app.config['CHAT_RETENTION_DAYS'], contact=store.contact(),
                               static_mode=False, language_url='?lang=' + ('zh' if lang == 'en' else 'en'))

    @app.get('/api/content/version')
    def version():
        return jsonify(version=store.version())

    @app.get('/cv/<lang>.md')
    def download_cv(lang):
        if lang not in ('zh', 'en'):
            return Response('Not found', status=404)
        return Response(store.cv(lang), content_type='text/markdown; charset=utf-8',
                        headers={'Content-Disposition': f'attachment; filename="Wei-Chen-Wu-CV-{lang}.md"',
                                 'Cache-Control': 'no-store'})

    @app.get('/healthz')
    def health():
        return jsonify(status='ok')

    @app.cli.command('cleanup-chat')
    def clean_chat():
        """Delete expired messages and old delivery metadata."""
        cleanup()
        print('Expired chat data removed.')

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=int(os.getenv('PORT', 5000)), debug=False)
