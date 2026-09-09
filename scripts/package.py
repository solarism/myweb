"""Create a GitHub-ready archive using an explicit allowlist; exclude secrets/data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FILES = ['app.py', 'chat.py', 'content_store.py', 'labels.py', 'requirements.txt', 'requirements.lock',
         'requirements-dev.txt', 'pytest.ini', 'README.md', '.gitignore', '.env.example', '.dockerignore',
         'Dockerfile', 'compose.yaml', 'render.yaml']
DIRECTORIES = ['templates', 'static', 'content', 'downloads', 'docs', 'scripts', 'tests', '.github']
output = ROOT / 'dist/professor-website.zip'
output.parent.mkdir(exist_ok=True)
paths = [ROOT / name for name in FILES]
for directory in DIRECTORIES:
    paths.extend(p for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for path in paths:
        archive.write(path, Path('myweb') / path.relative_to(ROOT))
print(output)
