import os

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from content_store import ContentStore, ROOT
from labels import LABELS

load_dotenv(ROOT / '.env')


def create_app(test_config=None):
    app = Flask(__name__)
    production = os.getenv('APP_ENV') == 'production'
    app.config['MAX_CONTENT_LENGTH'] = 64 * 1024
    if test_config:
        app.config.update(test_config)
    if os.getenv('TRUST_PROXY') == '1':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    store = ContentStore(app.config.get('CONTENT_DIR'))
    app.extensions['content_store'] = store

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
                               version=store.version(),
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

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=int(os.getenv('PORT', 5000)), debug=False)
