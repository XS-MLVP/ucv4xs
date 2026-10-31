#!/usr/bin/env python3
"""Validate project skill documents, not client registration or semantic approval.

OpenCode V2 allows optional frontmatter and path-derived IDs. This project
additionally requires portable names/descriptions on its entries and drafts.
Supporting Markdown is documentation, not an independently installed skill.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'(?<!!)\[[^\]]*\]\(([^)]+)\)')
PORTABLE_NAME = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
FRAMEWORK_NAMES = (
    'Bundle', 'SignalDriver', 'Agent', 'Scoreboard', 'SamplingMonitor',
    'ReadyValidMonitor', 'SyncSingleCycleDriver', 'AsyncSingleCycleDriver',
    'SyncMultiCycleDriver', 'AsyncDriver', 'CoverGroupDef', 'CoverPointDef', 'CrossDef',
)


def audit(root=ROOT, *, check_framework=False):
    root = Path(root).resolve()
    errors, entries, drafts, names = [], [], [], {}
    documents = sorted((root / 'skills').rglob('*.md'))
    for path in documents:
        relative = str(path.relative_to(root))
        text = path.read_text(encoding='utf-8')
        entry = path.name == 'SKILL.md'
        draft = path.parent.name == 'pending' and path.name != 'README.md'
        if entry or draft:
            parts = text.split('---', 2) if text.startswith('---' + chr(10)) else []
            try:
                metadata = yaml.safe_load(parts[1]) if len(parts) == 3 else None
            except yaml.YAMLError as error:
                errors.append(f'{relative}: invalid YAML: {error}')
                metadata = None
            if not isinstance(metadata, dict):
                errors.append(f'{relative}: project policy requires YAML frontmatter')
            else:
                name, description = metadata.get('name'), metadata.get('description')
                expected = path.parent.name if entry else path.stem
                if (not isinstance(name, str) or not PORTABLE_NAME.fullmatch(name)
                        or len(name) > 64 or name != expected):
                    errors.append(f'{relative}: portable project name must match {expected}')
                if not isinstance(description, str) or not description.strip():
                    errors.append(f'{relative}: project policy requires description')
                if isinstance(name, str):
                    if name in names:
                        errors.append(f'{relative}: duplicate name also in {names[name]}')
                    names[name] = relative
                (entries if entry else drafts).append({'path': relative, 'name': name})
            if draft and '待审核' not in text:
                errors.append(f'{relative}: draft must retain pending-review label')
        for link in LINK.findall(text):
            target = link.split('#', 1)[0]
            if not target or '://' in target or target.startswith('mailto:'):
                continue
            resolved = (path.parent / unquote(target)).resolve()
            if not resolved.is_relative_to(root):
                errors.append(f'{relative}: link escapes repository: {link}')
            elif not resolved.exists():
                errors.append(f'{relative}: missing local link: {link}')
        for target in re.findall(r'\.tools/sources/toffee/docs/[A-Za-z0-9_./-]+', text):
            if not (root / target).exists():
                errors.append(f'{relative}: missing locked framework documentation: {target}')
        if '`MultiCycle`' in text:
            errors.append(f'{relative}: MultiCycle is not a public Toffee export')
    framework = {'checked': False}
    if check_framework:
        try:
            toffee = importlib.import_module('toffee')
            missing = [name for name in FRAMEWORK_NAMES if not hasattr(toffee, name)]
            framework = {'checked': True, 'module': str(Path(toffee.__file__).resolve()),
                         'checked_exports': list(FRAMEWORK_NAMES), 'missing': missing}
            errors.extend(f'toffee: missing public export {name}' for name in missing)
        except ImportError as error:
            errors.append(f'framework check unavailable: {error}')
    return {'status': 'FAIL' if errors else 'PASS', 'documents': len(documents),
            'entrypoints': entries, 'pending_drafts': drafts,
            'support_documents': len(documents) - len(entries) - len(drafts),
            'framework': framework, 'errors': sorted(set(errors)),
            'limits': ['Does not prove client discovery, registration or permissions.',
                       'Entry/draft/support counts classify project intent, not a live registry.',
                       'API presence is not behavioral certification.',
                       'Link fragments and methodological correctness need review.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict', action='store_true')
    parser.add_argument('--check-framework', action='store_true')
    args = parser.parse_args(argv)
    result = audit(check_framework=args.check_framework)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(args.strict and bool(result['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
