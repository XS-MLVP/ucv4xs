"""Explicit sparse-segment correctness canary; unresolved RTL stays FAIL."""
from collections import Counter
from dataclasses import replace
import os

import pytest

from tools.run_vagq_exhaustive import atomic_json
from vagqverify.native import open_dut
from vagqverify.vagq.exhaustive import (
    ShapeSession, U64_MASK, assess_shape_boundaries, build_shape_sequence, run_shape_sequence,
)
from vagqverify.vagq.isa_reference import architectural_accesses
from vagqverify.vagq.scenario_matrix import legal_public_feature_cases


pytestmark = pytest.mark.vagq_isa_audit


def test_sparse_segment_masks_preserve_element_ownership(native_registration, tmp_path):
    if os.environ.get('RUN_VAGQ_SPARSE_CANARY') != '1':
        pytest.skip('explicit known-limitation canary; not ordinary regression')
    ordinal, case = next((i, case) for i, case in enumerate(legal_public_feature_cases())
        if (case.operation, case.vsew, case.vlmul, case.data_eew, case.nf) == (0, 2, 0, 2, 4))
    failures = []
    with open_dut('VAGQ', tmp_path, clocked=True, register=native_registration) as dut:
        session = ShapeSession(dut)
        for byte_mask, architectural_mask in ((0x0F0F, 0b0101), (0xF0F0, 0b1010)):
            original = build_shape_sequence(case, ordinal)
            packets = tuple((replace(addr, v0_byte_mask=byte_mask), data)
                            for addr, data in original.packets)
            accesses = architectural_accesses(kind='strided', base=original.base,
                vsew=case.vsew, vlmul=case.vlmul, vl=case.vlmax, vstart=0,
                mask=architectural_mask, data_eew=case.data_eew, nf=case.nf,
                stride=original.stride)
            # The architecture answer uses the element mask, NOT MaskGen or
            # emitted requests. Byte replication is supplied only to the DUT.
            expected = Counter((access.element, (access.address + byte) & U64_MASK)
                for access in accesses for byte in range(1 << case.data_eew))
            plan = replace(original, packets=packets, expected_bytes=expected)
            result = run_shape_sequence(session, case, ordinal, plan=plan)
            result.update(stimulus=plan.stimulus(), architectural_mask=architectural_mask,
                byte_mask=byte_mask, variant_id=f'{result["shape_id"]}_v0{byte_mask:04x}',
                assessment=assess_shape_boundaries(plan, result['events']),
                scope='nf>0 forced-port sparse-mask canary, NOT current production decode')
            atomic_json(tmp_path / f'sparse-{byte_mask:04x}-result.json', result)
            if result['assessment']['request_boundary_status'] != 'PASS':
                failures.append(dict(variant_id=result['variant_id'],
                    assessment=result['assessment']))
    atomic_json(tmp_path / 'sparse-summary.json', dict(attempted=2, failures=failures,
        full_acceptance_credit=False, original_8352_inventory_unchanged=True))
    assert not failures, f'sparse segment correctness counterexamples: {failures}'
