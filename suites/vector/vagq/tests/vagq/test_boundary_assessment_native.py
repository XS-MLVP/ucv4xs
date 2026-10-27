"""Same native VAGQ inputs, separate outcomes; known FAILs are not waived."""
import json
import os
from pathlib import Path

import pytest

from tools.run_vagq_exhaustive import atomic_json, digest
from vagqverify.native import open_dut
from vagqverify.vagq.exhaustive import ShapeSession, assess_shape_boundaries, build_shape_sequence, run_shape_sequence
from vagqverify.vagq.scenario_matrix import legal_public_feature_cases


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.vagq_isa_audit


def test_native_boundary_assessment_keeps_real_counterexamples(native_registration, tmp_path):
    if os.environ.get('RUN_VAGQ_BOUNDARY_ASSESSMENT') != '1':
        pytest.skip('explicit post-fix boundary qualification only')
    original = ROOT / 'results/vagq-exhaustive-20261020-v1'
    receipts = {row['ordinal']: row for row in json.loads((original / 'full/completed-shapes.json').read_text())}
    cases = tuple(legal_public_feature_cases())
    ordered_nf0 = next(i for i, case in enumerate(cases) if case.operation == 6 and case.nf == 0)
    # (raw architecture status, public lifecycle status, frozen-v2 status)
    expected = {
        0: ('PASS', 'PASS', 'PASS'), ordered_nf0: ('PASS', 'PASS', 'PASS'),
        12: ('PASS', 'PASS', 'FAIL'), 313: ('PASS', 'PASS', 'FAIL'),
        419: ('FAIL', 'FAIL', 'FAIL'), 1326: ('PASS', 'PASS', 'FAIL'),
        5014: ('FAIL', 'PASS', 'FAIL'), 2171: ('FAIL', 'PASS', 'FAIL'),
    }
    results = []
    with open_dut('VAGQ', tmp_path, clocked=True, register=native_registration) as dut:
        session = ShapeSession(dut)
        for ordinal, statuses in expected.items():
            receipt = receipts[ordinal]
            assert digest(Path(receipt['path'])) == receipt['sha256']
            previous = json.loads(Path(receipt['path']).read_text())
            plan = build_shape_sequence(cases[ordinal], ordinal)
            assert plan.stimulus() == previous['stimulus']
            result = run_shape_sequence(session, cases[ordinal], ordinal, plan=plan)
            assert result['events'] == previous['events']
            result['assessment'] = assessment = assess_shape_boundaries(plan, result['events'])
            actual = (assessment['architectural_requests']['status'],
                      assessment['public_lifecycle']['status'], assessment['legacy_v2']['status'])
            assert actual == statuses
            assert assessment['overall_isa_acceptance'] == 'NOT_VERIFIED'
            result['original_result_sha256'] = receipt['sha256']
            result['full_acceptance_credit'] = False
            result['test_scope'] = 'Boundary checker qualification/reproduction, NOT fixing known RTL failures'
            atomic_json(tmp_path / f'{ordinal:05d}-assessment.json', result)
            results.append(dict(ordinal=ordinal, shape_id=result['shape_id'],
                statuses=actual, full_acceptance_credit=False))
    atomic_json(tmp_path / 'assessment-summary.json', results)
