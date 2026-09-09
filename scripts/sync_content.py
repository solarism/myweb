"""Snapshot original Markdown and explicitly pair reviewed translations."""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from content_store import ROOT, FILES, ContentStore, digest, units


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', action='store_true', help='Copy the current source files into content/zh for GitHub deployment.')
    parser.add_argument('--approve-translations', action='store_true', help='Pair current source units with reviewed content/en files (same unit order/count required).')
    args = parser.parse_args()
    store = ContentStore()
    if args.snapshot:
        for filename, _, _ in FILES.values():
            source, target = store.directory / filename, ROOT / 'content/zh' / filename
            if source.resolve() != target.resolve():
                shutil.copyfile(source, target)
        print('Bundled Markdown updated from:', store.directory)
    registry = store.translations()
    if args.approve_translations:
        # Explicit command because pairing an old translation to new facts would be incorrect.
        new_pairs = []
        for key, (filename, _, _) in FILES.items():
            source = units(store.source(key))
            translated = units((ROOT / 'content/en' / filename).read_text())
            if len(source) != len(translated):
                raise SystemExit(f'{filename}: source has {len(source)} units; English has {len(translated)}. Match paragraph/heading/item boundaries before approving.')
            new_pairs.extend(('en', digest(a), b) for a, b in zip(source, translated))
        source = units(store.source('profile'))
        chinese = units((ROOT / 'content/CV.zh.md').read_text())
        if len(source) != len(chinese):
            raise SystemExit('CV.zh.md must match source CV paragraph/heading/item boundaries.')
        new_pairs.extend(('zh', digest(a), b) for a, b in zip(source, chinese))
        for lang, hashed, translation in new_pairs:
            registry.setdefault(lang, {})[hashed] = translation
        (ROOT / 'content/translations.json').write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n')
        print('Reviewed translations paired to source fingerprints.')
    for lang in ('zh', 'en'):
        out = ROOT / 'downloads'
        out.mkdir(exist_ok=True)
        (out / f'Wei-Chen-Wu-CV-{lang}.md').write_text(store.cv(lang))
    print('CV Markdown files generated in downloads/.')


if __name__ == '__main__':
    main()
