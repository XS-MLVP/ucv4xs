"""The matrix must grow with its input model, never default new classes to PASS."""
from copy import deepcopy
import json
import pytest
from suites.frontend.bpu import ROOT
from suites.frontend.bpu.tools.io_matrix import MATRIX
from suites.frontend.bpu.tools.io_matrix import DUT_RESPONSIBILITIES
from suites.frontend.bpu.tools.io_matrix import SOURCE_FAMILIES
from suites.frontend.bpu.tools.io_matrix import UNCLASSIFIED
from suites.frontend.bpu.tools.io_matrix import resolve
from suites.frontend.bpu.tools.io_matrix import validate
from suites.frontend.bpu.testbenches.bpu.model.selection import Kind
from suites.frontend.bpu.testbenches.mbtb.model.learning_matrix import PAYLOAD_CASES


def test_every_input_class_and_response_domain_has_an_explicit_disposition():
    validate()
    assert set(DUT_RESPONSIBILITIES) == set(json.loads((ROOT / 'ucv.json').read_text())['duts'])
    assert {int(v) for v in Kind} == {0, 1, 2, 3}
    assert {'conditional', 'direct', 'indirect', 'none', 'lookup', 'recovery', 'retirement'} == set(SOURCE_FAMILIES)
    assert all(row['missing'] and row['next_action'] for row in UNCLASSIFIED)


@pytest.mark.parametrize('fault', ('new-class', 'missing-row', 'missing-domain', 'empty-tests', 'silent-gap', 'static-pass'))
def test_missing_or_unproved_matrix_evidence_is_rejected(fault):
    matrix = deepcopy(MATRIX)
    if fault == 'new-class':
        matrix['unreviewed'] = deepcopy(matrix['cold-nt'])
    elif fault == 'missing-row':
        del matrix['cold-nt']
    elif fault == 'missing-domain':
        del matrix['cold-nt']['correction']
    elif fault == 'empty-tests':
        matrix['cold-nt']['correction']['nodeids'] = ()
    elif fault == 'silent-gap':
        matrix['cold-nt']['clean'].pop('next_action')
    else:
        matrix['cold-nt']['clean'] = dict(status='pass')
    with pytest.raises(ValueError):
        validate(matrix)


def test_collection_and_partial_pass_are_not_complete_outcome_credit():
    assert resolve({})['cold-nt']['correction']['status'] == 'gap'
    nodes = MATRIX['cold-nt']['correction']['nodeids']
    assert resolve({nodes[0]: 'PASS'})['cold-nt']['correction']['status'] == 'gap'
    verdicts = dict.fromkeys(nodes, 'PASS')
    assert resolve(verdicts)['cold-nt']['correction']['status'] == 'pass'
    verdicts[nodes[-1]] = 'FAIL'
    assert resolve(verdicts)['cold-nt']['correction']['status'] == 'fail'


def test_nonexistent_cold_target_regions_do_not_inflate_semantic_coverage():
    assert len(PAYLOAD_CASES) == 48  # Preserve all existing parameter nodeids.
    assert len({c.coverage_label for c in PAYLOAD_CASES}) == 40
    for alignment in (0, 1):
        for position in (1, 15):
            aliases = [c for c in PAYLOAD_CASES if c.mode == 'cold-nt' and c.alignment == alignment and c.position == position]
            assert len(aliases) == 3 and len({c.coverage_label for c in aliases}) == 1
