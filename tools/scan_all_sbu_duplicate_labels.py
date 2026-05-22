#!/usr/bin/env python3
"""Scan all sbu_* models for duplicate field labels (Odoo.sh fails on WARNING)."""
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIL_PREFIXES = ('message_', 'activity_', 'website_message')


def scan_file(py_path, by_model):
    text = py_path.read_text(encoding='utf-8')
    model = None
    m = re.search(r"_name\s*=\s*['\"]([^'\"]+)['\"]", text)
    if m:
        model = m.group(1)
    im = re.search(r"_inherit\s*=\s*['\"]([^'\"]+)['\"]", text)
    if im:
        model = im.group(1)
    if not model:
        return
    for fname, label in re.findall(
        r"(\w+)\s*=\s*fields\.\w+\([^)]*?string=['\"]([^'\"]+)['\"]",
        text,
        re.DOTALL,
    ):
        if fname.startswith(MAIL_PREFIXES):
            continue
        by_model[model][label].append(f'{py_path.name}:{fname}')


def main():
    by_model = defaultdict(lambda: defaultdict(list))
    for pkg in sorted(ROOT.glob('sbu_*')):
        models_dir = pkg / 'models'
        if models_dir.is_dir():
            for py in models_dir.rglob('*.py'):
                scan_file(py, by_model)
    found = False
    for model in sorted(by_model):
        dups = {k: v for k, v in by_model[model].items() if len(v) > 1}
        if dups:
            found = True
            print(f'\n{model}')
            for label, fields in sorted(dups.items()):
                print(f'  "{label}": {fields}')
    if not found:
        print('OK: no duplicate labels in sbu_* models (regex scan).')
    return 0 if not found else 1


if __name__ == '__main__':
    raise SystemExit(main())
