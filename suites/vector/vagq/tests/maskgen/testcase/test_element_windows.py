"""Native regression of field-independent destination windows and mask policy."""
from dataclasses import asdict
import json
import math
import os

import pytest

from tools.run_vagq_exhaustive import atomic_json
from suites.vector.vagq.maskgen.probe import bind_maskgen
from suites.vector.vagq.maskgen.reference import MaskRequest, allocated_uops, evaluate_protocol, mop_info


def _configurations():
    for deew in range(4):
        for nf in range(1, 8):
            yield deew, deew, 0, nf, nf + 1
    for emul, fields in ((1, 2), (1, 3), (2, 2)):
        yield 2, 2, emul, fields - 1, fields
    for emul, deew in ((5, 0), (6, 1), (7, 2)):
        yield deew, deew, emul, 4, 5
    # Four index banks per LMUL window; only two destination fields.
    yield 0, 2, 1, 1, 4
    # Explicit special 7-field/e8/index-e32 layout, including dummy MOP uops.
    yield 0, 2, 0, 6, 7


def _run_matrix(maskgen_dut, tmp_path, *, require_all_outputs):
    observe = bind_maskgen(maskgen_dut)
    samples, errors, fixed_errors, configs = 0, [], [], 0
    journal = tmp_path / 'element-window-samples.jsonl'
    with journal.open('x') as stream:
        for deew, ieew, emul, nf, per_window in _configurations():
            seed = MaskRequest(0xFFFF, deew, ieew, emul, 1, 0, 0, 0, 0, nf)
            assert seed.legal
            windows = math.ceil(seed.lmul)
            uops = per_window * windows
            assert len(allocated_uops(seed)) == uops
            vlmax = int(16 * seed.lmul / (1 << deew))
            profiles = ((0, 0), (vlmax, 0), (vlmax - 1, min(1, vlmax - 1)), (vlmax, vlmax))
            for vl, vstart in profiles:
                for v0 in (0, 0xFFFF, 0xA5A5):
                    for vma, vta in ((0, 0), (0, 1), (1, 0), (1, 1)):
                        for uop in range(uops):
                            request = MaskRequest(v0, deew, ieew, emul, vl, vstart, vma, vta, uop, nf)
                            expected_window = uop // per_window
                            # Independent destination semantics: every field
                            # reuses the same contiguous element range.
                            body = tail = 0
                            for byte in range(16):
                                element = expected_window * (16 >> deew) + (byte >> deew)
                                if vstart <= element < vl:
                                    body |= 1 << byte
                                elif element >= vstart and element >= vl:
                                    tail |= 1 << byte
                            semantic_merge = (~(body & v0)) & 0xFFFF
                            semantic_agnostic = ((body & ~v0 & 0xFFFF) if vma else 0) | (tail if vta else 0)
                            expected, actual = evaluate_protocol(request), observe(request)
                            fixed_fields_match = (mop_info(request).destination_window == expected_window
                                and actual['mergeWriteMask'] == semantic_merge
                                and actual['mergeWriteMask'] == expected['mergeWriteMask']
                                and actual['elemAgnosticMask'] == semantic_agnostic
                                and actual['elemAgnosticMask'] == expected['elemAgnosticMask'])
                            passed = expected == actual and fixed_fields_match
                            row = dict(request=asdict(request), expected=expected, actual=actual,
                                semantic_window=expected_window, semantic_merge=semantic_merge,
                                semantic_agnostic=semantic_agnostic, matches=passed,
                                fixed_fields_match=fixed_fields_match,
                                scope='MaskGen public contract; no whole-chip ISA credit')
                            stream.write(json.dumps(row) + '\n')
                            if not passed:
                                errors.append(row)
                            if not fixed_fields_match:
                                fixed_errors.append(row)
                            samples += 1
            stream.flush()
            os.fsync(stream.fileno())
            configs += 1
    atomic_json(tmp_path / 'element-window-summary.json', dict(configurations=configs,
        samples=samples, full_output_mismatches=len(errors),
        fixed_field_mismatches=len(fixed_errors), examples=errors[:8],
        full_output_acceptance=(not errors),
        asserted_scope='all outputs' if require_all_outputs else 'fixed merge/agnostic/window fields ONLY',
        journal=str(journal), semantics='Element window independent of field-major register index'))
    selected = errors if require_all_outputs else fixed_errors
    assert not selected, f'{len(selected)}/{samples} native policy mismatches: {selected[:2]}'


def test_corrected_merge_window_fields(maskgen_dut, tmp_path):
    # A scoped repair regression, not an all-output acceptance test. The JSON
    # still records ALL mismatches; the explicit canary below must expose them.
    _run_matrix(maskgen_dut, tmp_path, require_all_outputs=False)


@pytest.mark.vagq_isa_audit
def test_segment_element_windows_and_policies(maskgen_dut, tmp_path):
    # Keep this full-output canary failing while the independent sparse-mask
    # counterexamples remain. No XFAIL, skip, or expected-count waiver.
    _run_matrix(maskgen_dut, tmp_path, require_all_outputs=True)
