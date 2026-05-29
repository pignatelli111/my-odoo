#!/usr/bin/env python3
"""Scan SBU model files for duplicate field labels (Odoo.sh build warning)."""
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def scan_package(rel_path):
    by_model = defaultdict(lambda: defaultdict(list))
    for py in (ROOT / rel_path).rglob('*.py'):
        text = py.read_text(encoding='utf-8')
        model = None
        m = re.search(r"_name\s*=\s*['\"]([^'\"]+)['\"]", text)
        if m:
            model = m.group(1)
        im = re.search(r"_inherit\s*=\s*['\"]([^'\"]+)['\"]", text)
        if im:
            model = im.group(1)
        if not model:
            continue
        for fm, lab in re.findall(
            r"(\w+)\s*=\s*fields\.\w+\([^;]*?string=['\"]([^'\"]+)['\"]",
            text,
            re.DOTALL,
        ):
            by_model[model][lab].append(f'{py.name}:{fm}')
    return by_model


def main():
    found = False
    for pkg in ('sbu_estimate/models', 'sbu_purchase_flow/models', 'sbu_sal/models'):
        for model, labs in sorted(scan_package(pkg).items()):
            dups = {k: v for k, v in labs.items() if len(v) > 1}
            if dups:
                found = True
                print(f'\n{pkg} :: {model}')
                for lab, fields in sorted(dups.items()):
                    print(f'  "{lab}": {fields}')
    if not found:
        print('No duplicate labels found in scan (regex may miss some fields).')


if __name__ == '__main__':
    main()
