"""NF=0 focused native campaign; no segment-entry requirement or ISA PASS claim."""
from collections import Counter
import json
import os

import pytest

from tools.run_vagq_exhaustive import atomic_json
from vagqverify.native import open_dut
from vagqverify.vagq.exhaustive import ShapeSession
from vagqverify.vagq.nf0_focus import PROFILES, compatible_shapes, make_variant, run_variant

pytestmark = pytest.mark.vagq_isa_audit


def batches():
    all_shapes = compatible_shapes()
    result = []
    for operation in (0, 1, 4, 5, 6, 7):
        shapes = tuple(item for item in all_shapes if item[1].operation == operation)
        if os.environ.get('NF0_FOCUS_SMOKE') == '1':
            result.append((f'op{operation}-smoke', (shapes[0], shapes[-1])))
        else:
            for start in range(0, len(shapes), 26):
                result.append((f'op{operation}-{start:02d}', shapes[start:start + 26]))
    return result


@pytest.mark.parametrize('batch_id,shapes', batches(), ids=lambda value: value if isinstance(value, str) else None)
def test_nf0_full_sequence_profiles(batch_id, shapes, native_registration, tmp_path):
    if os.environ.get('RUN_VAGQ_NF0_FOCUS') != '1':
        pytest.skip('explicit NF=0 focus campaign; fresh evidence directory required')
    counts = Counter()
    failures = []
    with (tmp_path / 'variants.jsonl').open('x') as journal:
        with open_dut('VAGQ', tmp_path, clocked=True, register=native_registration) as dut:
            session = ShapeSession(dut)
            for ordinal, case in shapes:
                for profile in PROFILES:
                    variant = make_variant(case, ordinal, profile)
                    result = run_variant(session, variant)
                    path = tmp_path / f'{ordinal:05d}-{profile}.json'
                    atomic_json(path, result)
                    row = dict(ordinal=ordinal, profile=profile, status=result['status'],
                        actual_sequence_uops=result['actual_sequence_uops'],
                        admissions=len(result['events']['admissions']),
                        writebacks=len(result['events']['writebacks']),
                        requests=len(result['events']['requests']),
                        blocked_cycles=result['events']['blocked_cycles'],
                        cycles=result['events']['cycles'], path=str(path))
                    journal.write(json.dumps(row) + '\n')
                    journal.flush()
                    counts[result['status']] += 1
                    if result['status'] != 'PASS':
                        failures.append(dict(**row, errors=result['errors']))
    atomic_json(tmp_path / 'summary.json', dict(batch_id=batch_id, shapes=len(shapes),
        profiles=PROFILES, attempted=len(shapes) * len(PROFILES), counts=dict(counts),
        failures=failures, full_data_or_memory_effect_acceptance=False))
    assert not failures, f'NF=0 correctness failures: {failures[:6]}'
