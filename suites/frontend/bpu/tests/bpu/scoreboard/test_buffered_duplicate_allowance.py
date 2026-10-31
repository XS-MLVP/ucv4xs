"""Negative controls for the bounded AheadBTB buffered-cleanup allowance.

These tests prove the allowance refuses every difference except the one it
declares: a content-identical extra way whose invalidation the reference has
already issued but the single-port bank has not yet serviced.  They are pure
oracle tests; the DUT evidence lives in test_conditional_prefix.py.
"""
from types import SimpleNamespace

import pytest

from suites.frontend.bpu.bpu.checker.pipeline import buffered_duplicate_allowances

ROW, BANK, WAY, SURVIVOR = 1, 3, 1, 3
ENTRY = dict(valid=True, tag=1, position=2, kind=1, action=0, target=515)


def reference(*, memory_valid=False, invalidation=True, write_way=WAY, write_row=ROW):
    entry = SimpleNamespace(valid=memory_valid)
    pending = SimpleNamespace(versions={
        1: SimpleNamespace(order=7, write=SimpleNamespace(row=write_row, way=write_way,
            entry=SimpleNamespace(valid=not invalidation)))})
    sources = SimpleNamespace(has_own_ahead=True,
        ahead=SimpleNamespace(memory={(BANK, ROW, WAY): entry}, pending=[SimpleNamespace(versions={}),
            SimpleNamespace(versions={}), SimpleNamespace(versions={}), pending]))
    return SimpleNamespace(sources=sources)


def values(*, extra=ENTRY, survivor=ENTRY, extra_present=1, survivor_present=1):
    section = {f'{way}.valid': 0 for way in range(4)}
    section.update({f'{way}.micro_valid': 0 for way in range(4)})
    section.update({f'{way}.meta_hit': 0 for way in range(4)})
    section.update(row=ROW, banks=1 << BANK)
    for way, entry, present in ((WAY, extra, extra_present), (SURVIVOR, survivor, survivor_present)):
        if not present:
            continue
        section.update({f'{way}.valid': 1, f'{way}.micro_valid': 1, f'{way}.meta_hit': 1,
            f'{way}.position': entry['position'], f'{way}.kind': entry['kind'],
            f'{way}.action': entry['action'], f'{way}.target_low': entry['target']})
    return section


def observed(*, extra=ENTRY, survivor=ENTRY):
    entries = [dict(hit=0, position=0, kind=0, action=0, target_low=0) for _ in range(4)]
    for way, entry in ((WAY, extra), (SURVIVOR, survivor)):
        entries[way] = dict(hit=1, position=entry['position'], kind=entry['kind'],
            action=entry['action'], target_low=entry['target'])
    return dict(ahead=dict(meta=dict(entries=entries)), early_direction=dict(), fast=dict(meta=dict(entries=entries)))


def run(model, expected_ahead, actual_ahead, observed_value, **sections):
    expected = dict(ahead=expected_ahead, **{name: sections[name][0] for name in sections})
    actual = dict(ahead=actual_ahead, **{name: sections[name][1] for name in sections})
    return buffered_duplicate_allowances(model, expected, actual, observed_value), expected, actual


def test_content_identical_extra_way_with_issued_invalidation_is_the_only_allowed_case():
    expected_ahead, actual_ahead = values(extra_present=0), values(extra_present=1)
    early = ({f'{WAY}.valid': 0, f'{SURVIVOR}.valid': 1}, {f'{WAY}.valid': 1, f'{SURVIVOR}.valid': 1})
    allowances, expected, actual = run(reference(), expected_ahead, actual_ahead, observed(),
        early_direction=early)
    assert [record['section'] for record in allowances] == ['ahead', 'early_direction']
    assert allowances[0]['way'] == WAY and allowances[0]['survivor'] == SURVIVOR
    assert allowances[0]['bank'] == BANK and allowances[0]['row'] == ROW
    assert set(allowances[0]['keys']) == {f'{WAY}.valid', f'{WAY}.micro_valid', f'{WAY}.meta_hit'}
    assert 'ahead' in expected and '1.position' not in expected['ahead']
    assert actual['ahead'][f'{SURVIVOR}.valid'] == 1
    assert actual['ahead'][f'{SURVIVOR}.target_low'] == ENTRY['target']


@pytest.mark.parametrize('mutation', [
    dict(extra=dict(ENTRY, position=4)),
    dict(extra=dict(ENTRY, kind=2)),
    dict(extra=dict(ENTRY, action=1)),
    dict(extra=dict(ENTRY, target=259)),
])
def test_differing_extra_content_is_never_allowed(mutation):
    expected_ahead = values(extra_present=0)
    actual_ahead = values(extra_present=1, **{key: value for key, value in mutation.items()})
    allowances, _, _ = run(reference(), expected_ahead, actual_ahead, observed(**mutation))
    assert allowances == []


def test_reference_still_resident_copy_is_never_allowed():
    expected_ahead = values(extra_present=0)
    actual_ahead = values(extra_present=1)
    allowances, _, _ = run(reference(memory_valid=True), expected_ahead, actual_ahead, observed())
    assert allowances == []


def test_missing_invalidation_version_is_never_allowed():
    expected_ahead = values(extra_present=0)
    actual_ahead = values(extra_present=1)
    allowances, _, _ = run(reference(invalidation=False), expected_ahead, actual_ahead, observed())
    assert allowances == []


@pytest.mark.parametrize('kwargs', [dict(write_way=SURVIVOR), dict(write_row=ROW + 1)])
def test_invalidation_must_name_the_exact_row_and_way(kwargs):
    expected_ahead = values(extra_present=0)
    actual_ahead = values(extra_present=1)
    allowances, _, _ = run(reference(**kwargs), expected_ahead, actual_ahead, observed())
    assert allowances == []


def test_non_own_ahead_source_never_gets_the_allowance():
    model = reference()
    model.sources.has_own_ahead = False
    expected_ahead, actual_ahead = values(extra_present=0), values(extra_present=1)
    allowances, _, _ = run(model, expected_ahead, actual_ahead, observed())
    assert allowances == []
