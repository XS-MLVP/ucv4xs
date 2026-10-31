"""Every residual useful row must fit a known per-cell template.

Synthetic fixtures only; real native reports are classified by the explicit
command.  A weakened or wrong-template row must be rejected, and the audit never
grants functional credit or changes the denominator.
"""
import json
from pathlib import Path

import pytest

from suites.frontend.bpu.utage.coverage.useful_cell_audit import SOURCE, ROOT, TEMPLATES, classify, source_lines


def fixture(*lines):
    return {'dut': {'utage': {
        'source_lines': {'total': 100, 'hit': 100 - len(lines)},
        'uncovered_rtl_source_lines': [
            {'file': SOURCE, 'line': line} for line in lines],
    }}}


def find_line(pattern):
    for number, line in enumerate(source_lines(), 1):
        if pattern.search(line):
            return number
    raise AssertionError(pattern.pattern)


def test_real_derived_templates_are_all_recognised_and_unmatched_is_reported():
    rows = []
    for _, pattern in TEMPLATES:
        try:
            rows.append(find_line(pattern))
        except AssertionError:
            # This generated variant has no textual occurrence of that shape;
            # the accepted-template list may be a superset of what is emitted.
            continue
    rows = sorted(set(rows))
    assert len(rows) >= 4
    result = classify(fixture(*rows))
    assert result['matched'] == len(rows)
    assert result['unmatched'] == []
    assert result['functional_pass_credit'] is False
    assert result['whole_design_formal_claim'] is False
    assert result['native_denominator_unchanged'] is True
    assert result['native_source_lines'] == {'total': 100, 'hit': 100 - len(rows)}


def test_unknown_row_is_kept_as_unclassified():
    known = find_line(TEMPLATES[0][1])
    lines = source_lines()
    unknown = next(number for number, line in enumerate(lines, 1)
                   if number != known and line.startswith('usefulEntries_') and
                   not any(pattern.search(line) for _, pattern in TEMPLATES))
    result = classify(fixture(known, unknown))
    assert result['matched'] == 1
    assert [row[0] for row in result['unmatched']] == [unknown]


@pytest.mark.parametrize('replacement', (
    "usefulEntries_0_1_value <= 2'h2;",
    "usefulEntries_0_1_value <= _GEN_148;",
    "usefulEntries_0_1_value <= _newUseful_T_14;",
))
def test_weakened_or_wrong_template_source_is_rejected_without_editing_rtl(monkeypatch, replacement):
    path = ROOT / SOURCE
    before = path.read_bytes()
    changed = path.read_text().splitlines()
    target = next(number for number, line in enumerate(changed, 1)
                  if 'usefulEntries_0_1_value <= 2\'h1;' in line)
    changed[target - 1] = f'            {replacement}'
    real_read = Path.read_text

    def read(self, *args, **kwargs):
        return '\n'.join(changed) if self == path else real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', read)
    result = classify(fixture(target))
    assert result['matched'] == 0
    assert result['unmatched'][0][0] == target
    assert path.read_bytes() == before


def test_branch_style_template_requires_the_exact_guard_text():
    lines = source_lines()
    head = next(number for number, line in enumerate(lines, 1)
                if line == 'if (io_train_t1_alloc_valid)')
    result = classify(fixture(head))
    assert result['templates']['allocate-head'] == 1
    assert result['unmatched'] == []
