#!/usr/bin/env python3
"""Scan sbu_* models for duplicate field labels (Odoo.sh WARNING source)."""
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scan():
    by_model = defaultdict(lambda: defaultdict(list))
    for mod in sorted(os.listdir(ROOT)):
        if not mod.startswith('sbu_'):
            continue
        models_dir = os.path.join(ROOT, mod, 'models')
        if not os.path.isdir(models_dir):
            continue
        for fn in sorted(os.listdir(models_dir)):
            if not fn.endswith('.py'):
                continue
            path = os.path.join(models_dir, fn)
            text = open(path, encoding='utf-8').read()
            mname = re.search(r"_name\s*=\s*['\"]([^'\"]+)['\"]", text)
            minherit = re.search(r"_inherit\s*=\s*['\"]([^'\"]+)['\"]", text)
            model = (mname.group(1) if mname else None) or (minherit.group(1) if minherit else None)
            if not model:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if 'string=' not in line:
                    continue
                sm = re.search(r"string\s*=\s*['\"]([^'\"]+)['\"]", line)
                if sm:
                    by_model[model][sm.group(1)].append(f'{mod}/models/{fn}:{i}')
    found = False
    for model in sorted(by_model):
        dups = {k: v for k, v in by_model[model].items() if len(v) > 1}
        if dups:
            found = True
            print(model)
            for label, locs in sorted(dups.items()):
                print(f'  duplicate {label!r}: {locs}')
    if not found:
        print('No duplicate field labels found in sbu_* models/')


if __name__ == '__main__':
    scan()
