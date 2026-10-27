"""No DUT credit: qualify the final audit's response and source-mask checks."""
from copy import deepcopy
import json
from pathlib import Path
from ucv.runtime import historical_path

import pytest

from tools.build_vagq_failure_review_report import source_segment_merge_mask, verify_driven_responses
from vagqverify.maskgen.reference import MaskRequest, evaluate_protocol
from vagqverify.vagq.failure_review import analyze_failure
from vagqverify.vagq.scenario_matrix import legal_public_feature_cases


ROOT = Path(__file__).resolve().parents[2]
REVIEW = historical_path('vagq', 'results/vagq-exhaustive-review-20261020-v1')


def test_source_window_is_not_field_major_destination_register_offset():
    request = MaskRequest(0xFFFF, 1, 1, 6, 2, 0, 0, 0, 1, 4)
    assert evaluate_protocol(request)['mergeWriteMask'] == 0xFFF0  # corrected element window 0
    assert source_segment_merge_mask(request, 5) == 0xFFF0  # source window 0


def test_recomputed_witnesses_compare_after_json_roundtrip():
    originals = json.loads((historical_path('vagq', 'results/vagq-exhaustive-20261020-v1/failed-shapes.json')).read_text())
    explanations = json.loads((REVIEW / 'case-review.json').read_text())
    cases = tuple(legal_public_feature_cases())
    for original, explanation in zip(originals, explanations):
        actual = analyze_failure(original, cases[original['ordinal']])
        assert json.loads(json.dumps(actual)) == explanation


def _response_run(*, intervention):
    return dict(events=dict(responses=[dict(cycle=4, kind='ldu', entry=0, issue_mask=0)]),
        actual_driven_lsu_responses=[dict(cycle=4, kind='ldu', lane=0, entry=0,
                                        issue_mask=1 if intervention else 0)],
        diagnostic_overrides=[dict(cycle=4, kind='ldu', lane=0, entry=0, original=0, driven=1)] if intervention else [],
        policy='ack_zero_only' if intervention else 'baseline', acceptance_credit=False)


@pytest.mark.parametrize('intervention', (False, True))
def test_actual_driven_response_accounting_rejects_hidden_ack_changes(intervention):
    run = _response_run(intervention=intervention)
    verify_driven_responses(run)
    corrupted = deepcopy(run)
    corrupted['actual_driven_lsu_responses'][0]['issue_mask'] ^= 2
    with pytest.raises(AssertionError):
        verify_driven_responses(corrupted)


def test_actual_driven_response_accounting_rejects_functional_credit():
    run = _response_run(intervention=True)
    run['acceptance_credit'] = True
    with pytest.raises(AssertionError):
        verify_driven_responses(run)
