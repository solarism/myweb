"""Render public-only HTML and Markdown downloads for GitHub Pages."""
import argparse
import shutil
import sys
from pathlib import Path

from flask import Flask, render_template

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from content_store import ContentStore, ROOT
from labels import LABELS


def static_url(endpoint, **values):
    # Relative URLs work at /myweb/, a custom domain, and local previews alike.
    if endpoint == 'static':
        return 'static/' + values['filename']
    if endpoint == 'download_cv':
        return 'cv/' + values['lang'] + '.md'
    raise ValueError(f'Unsupported static endpoint: {endpoint}')


def export_site(output, source=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    store = ContentStore(source or ROOT / 'content/zh')
    # Rendering does not import app.py, load .env, create a DB or contact LINE.
    renderer = Flask(__name__, template_folder=str(ROOT / 'templates'))
    renderer.jinja_env.globals['url_for'] = static_url
    version = store.version()
    with renderer.app_context():
        for lang, filename in [('zh', 'index.html'), ('en', 'en.html')]:
            docs = store.all(lang)
            html = render_template(
                'index.html', lang=lang, t=LABELS[lang], docs=docs,
                publication_count=sum(docs[k]['count'] for k in ('journals', 'conferences', 'books')),
                project_count=sum(docs[k]['count'] for k in ('nstc', 'moe', 'industry', 'other')),
                version=version, chat_enabled=False, retention=0, contact=store.contact(),
                static_mode=True, language_url='en.html' if lang == 'zh' else 'index.html',
            )
            (output / filename).write_text(html, encoding='utf-8')
    shutil.copytree(ROOT / 'static', output / 'static', dirs_exist_ok=True)
    (output / 'cv').mkdir(exist_ok=True)
    for lang in ('zh', 'en'):
        (output / 'cv' / f'{lang}.md').write_text(store.cv(lang), encoding='utf-8')
    (output / '.nojekyll').touch()
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/pages')
    parser.add_argument('--source', type=Path, default=ROOT / 'content/zh')
    args = parser.parse_args()
    print('GitHub Pages files generated:', export_site(args.output, args.source))
