"""Syntax and references are executable checks, not semantic approval."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('audit_skills', ROOT / 'scripts/audit-skills.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_project_skill_entries_and_references_are_valid():
    result = AUDIT.audit()
    assert result['errors'] == []
    assert len(result['entrypoints']) == 3
    assert len(result['pending_drafts']) == 4


def test_skill_audit_rejects_metadata_and_broken_links(tmp_path):
    directory = tmp_path / 'skills' / 'example'
    directory.mkdir(parents=True)
    (directory / 'SKILL.md').write_text('''---
name: wrong-name
description: Test
---
[missing](missing.md)
''')
    errors = AUDIT.audit(tmp_path)['errors']
    assert any('portable project name' in error for error in errors)
    assert any('missing local link' in error for error in errors)


def test_support_document_is_not_an_installed_skill(tmp_path):
    directory = tmp_path / 'skills' / 'execution'
    directory.mkdir(parents=True)
    (directory / 'example.md').write_text('# Supporting method')
    result = AUDIT.audit(tmp_path)
    assert result['status'] == 'PASS'
    assert result['entrypoints'] == []
    assert result['support_documents'] == 1
