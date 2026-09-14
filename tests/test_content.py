import re
import shutil

import pytest

from app import create_app
from content_store import ContentStore, FILES, ROOT, record_year, safe_markdown, source_directory


@pytest.fixture
def app(tmp_path):
    content = tmp_path / 'content'
    shutil.copytree(ROOT / 'content/zh', content)
    return create_app({'TESTING': True, 'CONTENT_DIR': content})


def test_all_source_records_are_present(app):
    store = app.extensions['content_store']
    expected = {key: len(re.findall(r'^\d+\.\s', store.source(key), re.M)) for key in FILES if key != 'profile'}
    for lang in ('zh', 'en'):
        docs = store.all(lang)
        assert {key: docs[key]['count'] for key in expected} == expected
        for key in expected:
            # All numbered items from the original source must survive parsing.
            assert len(re.findall(r'^\d+\.\s', store.source(key), re.M)) == docs[key]['count']


@pytest.mark.parametrize('lang', ['zh', 'en'])
def test_page_and_complete_cv(app, lang):
    client = app.test_client()
    page = client.get('/?lang=' + lang)
    assert page.status_code == 200
    assert b'NSTC 115-2221-E-141-008-MY2' in page.data
    assert b'I856852' in page.data
    cv = client.get('/cv/' + lang + '.md')
    assert cv.status_code == 200
    assert 'attachment' in cv.headers['Content-Disposition']
    assert 'text/markdown' in cv.content_type
    assert '財務金融' in cv.text if lang == 'zh' else 'Financial Technology' in cv.text
    for phrase in ('I856852', 'PBM1152228', '1140113173642', '10.1007/978-981-16-4258-6', 'TANET 2013'):
        assert phrase in cv.text
    assert 'no-store' in page.headers['Cache-Control']


def test_modified_markdown_updates_without_restart_and_never_shows_stale_translation(app):
    store = app.extensions['content_store']
    client = app.test_client()
    before = client.get('/api/content/version').json['version']
    path = store.directory / FILES['industry'][0]
    original = path.read_text()
    path.write_text(original.replace('198,993', '299,999') + '\n99. 吳威震，2028，全新合作計畫，執行中\n')
    after = client.get('/api/content/version').json['version']
    assert before != after
    for lang in ('zh', 'en'):
        page = client.get('/?lang=' + lang).text
        assert '全新合作計畫' in page
        assert '299,999' in page
        assert '198,993' not in page
        cv = client.get('/cv/' + lang + '.md').text
        assert '全新合作計畫' in cv
        assert '198,993' not in cv
    assert 'Source updated.' in client.get('/?lang=en').text


def test_markdown_is_sanitized_and_links_work():
    html = str(safe_markdown('[bad](javascript:alert(1)) <img src=x onerror=alert(1)>\n\nhttps://orcid.org/0000-0002-2419-6453'))
    assert 'javascript:' not in html
    assert '<img' not in html
    assert 'onerror' not in html
    assert 'href="https://orcid.org/0000-0002-2419-6453"' in html
    assert 'href="https://reurl.cc/example"' in str(safe_markdown('中文佳作https://reurl.cc/example'))


def test_year_does_not_use_patent_lookup_url_or_conference_title():
    assert record_year('Editors. Innovative Computing: IC 2021 (2022).', 'books') == '2022'
    assert record_year('專利 I856852 https://tiponet.tipo.gov.tw/S092_OUT/2022', 'patents') == ''


def test_contact_information_not_exposed(app):
    for lang in ('en', 'zh'):
        page = app.test_client().get('/?lang=' + lang).text

        assert 'mailto:' not in page
        assert 'tel:' not in page
        assert 'weichen@ntub.edu.tw' not in page
        assert 'weichen At ntub.edu.tw' not in page
        assert '+886-2-2322-6477' not in page


def test_unknown_cv_is_not_a_file_read(app):
    client = app.test_client()
    assert client.get('/cv/private.md').status_code == 404
    assert client.get('/cv/../../.env').status_code == 404


def test_messaging_routes_removed_even_with_old_configuration(app):
    app.config.update(LINE_CHANNEL_SECRET='old-secret', LINE_CHANNEL_ACCESS_TOKEN='old-token', LINE_ADMIN_USER_ID='old-admin')
    client = app.test_client()
    for path in ('/api/chat/session', '/api/chat/messages', '/line/webhook'):
        assert client.get(path).status_code == 404
        assert client.post(path, json={}).status_code == 404
    for lang in ('zh', 'en'):
        page = client.get('/?lang=' + lang).text
        assert 'chat-dialog' not in page
        assert 'open-chat' not in page
        assert 'LINE' not in page
    assert 'cleanup-chat' not in app.cli.commands
    assert 'chat' not in app.blueprints


def test_production_is_stateless_and_preserves_security_headers(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    response = create_app().test_client().get('/')
    assert response.status_code == 200
    assert 'Set-Cookie' not in response.headers
    assert response.headers['Strict-Transport-Security'] == 'max-age=31536000'
    assert "script-src 'self'" in response.headers['Content-Security-Policy']


def test_default_content_uses_project_edits(monkeypatch, tmp_path):
    monkeypatch.delenv('SOURCE_MD_DIR', raising=False)
    assert source_directory() == ROOT / 'content/zh'
    monkeypatch.setenv('SOURCE_MD_DIR', str(tmp_path))
    assert source_directory() == tmp_path


@pytest.mark.parametrize('lang', ['zh', 'en'])
def test_cv_is_visible_before_research_and_services_are_complete(app, lang):
    page = app.test_client().get('/?lang=' + lang).text
    profile = page.split('<section id="about"', 1)[1].split('</section>', 1)[0]
    assert '<details' not in profile
    assert page.index('id="about"') < page.index('id="research"')
    assert 'ECC52782528612' in profile
    assert 'post-quantum cryptography' in profile if lang == 'en' else '後量子密碼學' in profile
    docs = app.extensions['content_store'].all(lang)
    assert not docs['profile']['pending']
    assert not docs['services']['pending']
    assert docs['services']['count'] == 20
    services = page.split('<section id="services"', 1)[1].split('</section>', 1)[0]
    assert services.count('class="record"') == 20
    assert '2024–2026' in services if lang == 'en' else '113~115' in services
    assert 'Standing Supervisor' in services if lang == 'en' else '常務監事' in services
    cv = app.test_client().get('/cv/' + lang + '.md').text
    assert docs['services']['text'] in cv.replace('### ', '## ')


def test_service_updates_invalidate_translation_and_cv(app):
    store = app.extensions['content_store']
    path = store.directory / '服務.md'
    before = store.version()
    path.write_text(path.read_text().replace('113~115年度', '116年度'))
    assert store.version() != before
    english = store.document('services', 'en')
    assert english['pending']
    assert '116年度' in english['text']
    assert '2024–2026' not in english['text']
    assert '116年度' in store.cv('en')
