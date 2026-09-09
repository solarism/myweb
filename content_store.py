"""Read Markdown on every request; retain provenance for translated content."""
import hashlib
import json
import os
import re
from pathlib import Path

import bleach
import markdown
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent
FILES = {
    'profile': ('CV.md', '個人履歷', 'Profile'),
    'journals': ('期刊論文.md', '期刊論文', 'Journal articles'),
    'conferences': ('研討會論文.md', '研討會論文', 'Conference papers'),
    'books': ('專著及專書論文.md', '專著及專書論文', 'Books & book chapters'),
    'nstc': ('國科會計劃.md', '國科會計畫', 'NSTC research projects'),
    'moe': ('教育部計劃.md', '教育部計畫', 'Ministry of Education projects'),
    'industry': ('產學計劃.md', '產學合作', 'Industry collaboration'),
    'other': ('其他計劃.md', '其他計畫', 'Other projects'),
    'patents': ('專利.md', '專利', 'Patents'),
    'honors': ('榮譽.md', '榮譽', 'Honors'),
}


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def units(text):
    # A heading, numbered entry, or unnumbered paragraph is an independent unit.
    return [x.strip() for x in re.split(r'\n\s*\n|\n(?=##?\s|\d+[.)]\s)', text.strip()) if x.strip()]


def source_directory():
    explicit = os.getenv('SOURCE_MD_DIR', '').strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    return ROOT.parent if (ROOT.parent / 'CV.md').exists() else ROOT / 'content/zh'


def safe_markdown(text):
    # URL recognizers need a boundary after Chinese prose (e.g. 查詢https://…).
    text = re.sub(r'(?<=[\u3400-\u9fff])(https?://)', r' \1', text)
    html = markdown.markdown(text, extensions=['tables', 'fenced_code', 'nl2br'])
    html = bleach.clean(html, tags=set(bleach.sanitizer.ALLOWED_TAGS) | {
        'p', 'h1', 'h2', 'h3', 'h4', 'br', 'pre', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td'
    }, attributes={'a': ['href', 'title', 'rel'], 'ol': ['start']}, protocols=['https', 'http', 'mailto'], strip=True)
    return Markup(bleach.linkify(html, skip_tags=['pre', 'code']))


def record_year(text, key):
    if key in ('patents', 'honors', 'profile'):
        return ''
    without_urls = re.sub(r'https?://\S+', '', text)
    if key in ('journals', 'books', 'conferences'):
        dates = re.findall(r'[（(]((?:19|20)\d{2})(?:[年 ,.)）])', without_urls)
        if dates:
            return dates[0]
    year = re.search(r'(?<!\d)(?:19|20)\d{2}', without_urls)
    return year.group() if year else ''


def profile_group(heading):
    for key, terms in {'bio': ('Vita', '個人簡介'), 'research': ('研究', 'Research'),
                       'teaching': ('授課', 'Teaching'), 'links': ('Contributions', '學術貢獻'),
                       'phone': ('聯絡', 'Contact')}.items():
        if any(term.lower() in (heading or '').lower() for term in terms):
            return key
    return heading


class ContentStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else source_directory()

    def source(self, key):
        return (self.directory / FILES[key][0]).read_text(encoding='utf-8')

    def translations(self):
        path = ROOT / 'content/translations.json'
        return json.loads(path.read_text()) if path.exists() else {'en': {}, 'zh': {}}

    def version(self):
        return digest(''.join(self.source(key) for key in FILES) + json.dumps(self.translations(), sort_keys=True))

    def localized(self, key, lang):
        dictionary = self.translations().get(lang, {})
        output, pending = [], False
        for unit in units(self.source(key)):
            translated = dictionary.get(digest(unit))
            if translated is None:
                # English citations are already usable without a translation.
                missing = lang == 'en' and bool(re.search(r'[\u3400-\u9fff]', unit))
                pending |= missing
                output.append((unit, missing))
            else:
                output.append((translated, False))
        return output, pending

    def document(self, key, lang):
        localized, pending = self.localized(key, lang)
        entries, groups, current = [], [], None
        group_key = None
        for (text, missing), source_unit in zip(localized, units(self.source(key))):
            source_lines = source_unit.splitlines()
            if source_lines and re.match(r'^#{1,3}\s', source_lines[0]):
                group_key = profile_group(re.sub(r'^#+\s*', '', source_lines[0]))
            # Split heading from following text without consuming that text.
            lines = text.splitlines()
            if lines and re.match(r'^#{1,3}\s', lines[0]):
                current = re.sub(r'^#+\s*', '', lines.pop(0))
                if current not in groups:
                    groups.append(current)
                text = '\n'.join(lines).strip()
            if not text:
                continue
            body = re.sub(r'^\d+[.)]\s*', '', text)
            entries.append({'text': body, 'html': safe_markdown(body), 'group': current,
                            'group_key': group_key, 'year': record_year(body, key), 'pending': missing,
                            'active': '執行中' in body or 'ongoing' in body.lower() or 'in progress' in body.lower()})
        text = '\n\n'.join(item for item, _ in localized)
        return {'key': key, 'title': FILES[key][1 if lang == 'zh' else 2],
                'filename': FILES[key][0], 'text': text, 'html': safe_markdown(text),
                'entries': entries, 'count': len(entries), 'groups': groups, 'pending': pending}

    def all(self, lang):
        return {key: self.document(key, lang) for key in FILES}

    def contact(self):
        source = self.source('profile')
        email_match = re.search(r'([a-zA-Z0-9._%+-]+)\s*(?:@|[Aa][Tt])\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', source)
        phone_match = re.search(r'\+\d[\d ()-]{7,}\d', source)
        email = email_match[1] + '@' + email_match[2] if email_match else ''
        phone = phone_match[0].strip() if phone_match else ''
        return {'email': email, 'phone': phone, 'phone_uri': re.sub(r'[^+\d]', '', phone)}

    def cv(self, lang):
        documents = self.all(lang)
        title = '# 吳威震｜完整學術履歷' if lang == 'zh' else '# Wei-Chen Wu | Curriculum Vitae'
        note = ('論文引用保留原發表語言；各項年份、經費與狀態依來源檔案。' if lang == 'zh' else
                'Bibliographic titles retain their publication language where appropriate. Dates, funding and status follow the source records.')
        parts = [title, note]
        for key, doc in documents.items():
            parts.append('## ' + doc['title'])
            if doc['pending'] and lang == 'en':
                parts.append('> Updated source text is included below; its English translation is pending.')
            parts.append(re.sub(r'(?m)^(#{1,5})\s', r'#\1 ', doc['text']))
        return '\n\n'.join(parts) + '\n'
