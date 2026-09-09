import re
import shutil

import pytest

from app import create_app
from content_store import ContentStore, FILES, ROOT, record_year, safe_markdown


@pytest.fixture
def app(tmp_path):
    content = tmp_path / 'content'
    shutil.copytree(ROOT / 'content/zh', content)
    return create_app({'TESTING': True, 'SECRET_KEY': 'test-secret', 'DATABASE_PATH': str(tmp_path / 'test.sqlite3'), 'CONTENT_DIR': content})


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


def test_contact_links_follow_source_cv(app):
    store = app.extensions['content_store']
    path = store.directory / 'CV.md'
    path.write_text(path.read_text().replace('weichen At ntub.edu.tw', 'new.email@example.edu').replace('+886-2-2322-6477', '+886-2-1234-5678'))
    for lang in ('en', 'zh'):
        page = app.test_client().get('/?lang=' + lang).text
        assert 'href="mailto:new.email@example.edu"' in page
        assert 'href="tel:+886212345678"' in page
        assert 'href="mailto:weichen@ntub.edu.tw"' not in page


def test_unknown_cv_is_not_a_file_read(app):
    client = app.test_client()
    assert client.get('/cv/private.md').status_code == 404
    assert client.get('/cv/../../.env').status_code == 404


def test_unconfigured_chat_is_honest(app):
    app.config.update(LINE_CHANNEL_SECRET='', LINE_CHANNEL_ACCESS_TOKEN='', LINE_ADMIN_USER_ID='')
    client = app.test_client()
    assert client.get('/api/chat/session').json == {'enabled': False}
    assert client.post('/api/chat/messages', json={}).status_code == 503
    assert '線上留言尚未開放' in client.get('/').text


def test_production_requires_stable_secret(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('SECRET_KEY', '')
    with pytest.raises(RuntimeError, match='persistent SECRET_KEY'):
        create_app()
