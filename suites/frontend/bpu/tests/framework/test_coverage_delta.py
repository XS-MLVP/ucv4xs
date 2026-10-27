"""Do not credit incompatible denominators or failed/unrelated scenarios."""
import json

import pytest
from tools.coverage_delta import attribute, lcov_rows, new_hits


def test_only_previous_zero_rows_are_incremental():
    assert new_hits({('a', 1): 0, ('a', 2): 2}, {('a', 1): 3, ('a', 2): 0}) == [('a', 1)]


def test_changed_native_denominator_is_rejected():
    with pytest.raises(ValueError, match='denominator'):
        new_hits({('a', 1): 0}, {('b', 1): 3})


@pytest.mark.parametrize('body', ('', 'DA:1,2\n', 'SF:a\nDA:1,-1\n', 'SF:a\nDA:1,0\nDA:1,2\n'))
def test_bad_lcov_is_rejected(tmp_path, body):
    path = tmp_path / 'native.info'
    path.write_text(body)
    with pytest.raises(ValueError):
        lcov_rows(path)


@pytest.mark.parametrize('fault', ('failed', 'incomplete', 'integrity', 'feature', 'multiple', 'association'))
def test_unqualified_feature_cannot_receive_credit(tmp_path, fault):
    evidence = dict(pytest_exitstatus=0, evidence_complete=True, integrity_errors=[],
                    tests=[dict(nodeid='checked', status='PASS')])
    feature = dict(id='F', status='PASS', tests=[dict(nodeid='checked', status='PASS')])
    if fault == 'failed': evidence['pytest_exitstatus'] = 1
    elif fault == 'incomplete': evidence['evidence_complete'] = False
    elif fault == 'integrity': evidence['integrity_errors'] = ['bad receipt']
    elif fault == 'feature': feature['status'] = 'FAIL'
    elif fault == 'multiple': evidence['tests'] *= 2
    elif fault == 'association': feature['tests'][0]['nodeid'] = 'unrelated'
    (tmp_path / 'evidence.json').write_text(json.dumps(evidence))
    (tmp_path / 'feature-points.json').write_text(json.dumps(dict(features=[feature])))
    with pytest.raises(ValueError):
        attribute(tmp_path / 'unused_baseline', tmp_path, dut='bpu', feature='F')


@pytest.mark.parametrize('layout', ('flat', 'refresh'))
def test_both_isolated_layouts_read_the_original_receipt_without_copying(tmp_path, layout):
    evidence_dir = tmp_path if layout == 'flat' else tmp_path / 'pytest-artifacts'
    evidence_dir.mkdir(exist_ok=True)
    receipt = evidence_dir / 'evidence.json'
    receipt.write_text(json.dumps(dict(pytest_exitstatus=1)))
    before = receipt.read_bytes()
    with pytest.raises(ValueError, match='complete successful pytest evidence'):
        attribute(tmp_path / 'unused_baseline', tmp_path, dut='bpu', feature='F')
    assert receipt.read_bytes() == before


def test_ambiguous_duplicate_receipts_cannot_select_a_convenient_verdict(tmp_path):
    (tmp_path / 'pytest-artifacts').mkdir()
    for path in (tmp_path / 'evidence.json', tmp_path / 'pytest-artifacts' / 'evidence.json'):
        path.write_text('{}')
    with pytest.raises(ValueError, match='unambiguous'):
        attribute(tmp_path / 'unused_baseline', tmp_path, dut='bpu', feature='F')
