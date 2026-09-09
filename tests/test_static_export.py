from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from scripts.export_static import export_site


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        self.urls.extend(value for key, value in attrs if key in ('src', 'href'))


def test_pages_export_has_no_backend_and_all_relative_links_resolve(tmp_path):
    output = export_site(tmp_path / 'pages')
    for filename, switch in [('index.html', 'en.html'), ('en.html', 'index.html')]:
        html = (output / filename).read_text()
        assert 'data-mode="static"' in html
        assert 'id="chat-dialog"' not in html
        assert 'open-chat' not in html
        assert f'href="{switch}"' in html
        parser = Links()
        parser.feed(html)
        for url in parser.urls:
            if url.startswith('#') or urlsplit(url).scheme:
                continue
            assert not url.startswith('/')
            resolved = urlsplit(urljoin('https://solarism.github.io/myweb/' + filename, url))
            assert resolved.path.startswith('/myweb/')
            assert (output / resolved.path.removeprefix('/myweb/')).is_file(), url
    assert (output / '.nojekyll').is_file()
    assert (output / 'cv/en.md').read_text().startswith('# Wei-Chen Wu')
    assert (output / 'cv/zh.md').read_text().startswith('# 吳威震')
    assert {p.name for p in output.iterdir()} == {'index.html', 'en.html', '.nojekyll', 'cv', 'static'}
