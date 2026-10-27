"""Real generated-root probes for the RVV VAGQ operation matrix.

The checks in this file compare public requests against the independent
architectural access oracle.  They deliberately do not reuse the integration
model as the expected address source.
"""
from collections import Counter
from dataclasses import asdict, replace
import json

import pytest

from vagqverify.vagq.driver import response_beat
from vagqverify.vagq.isa_reference import architectural_accesses
from vagqverify.vagq.isa_coverage import DUT_COVERAGE, PUBLIC_FEATURE_COVERAGE
from vagqverify.vagq.isa_reference import emul_encoding
from vagqverify.vagq.scenario_matrix import representative_public_feature_cases
from vagqverify.vagq.scenario_matrix import (
    feature_case_id,
)
from vagqverify.vagq.types import AddrPacket, Beat, DataPacket, Response


pytestmark = pytest.mark.vagq_isa_audit


_LMUL_NAME = {5: 'mf8', 6: 'mf4', 7: 'mf2', 0: 'm1', 1: 'm2', 2: 'm4', 3: 'm8'}
_EEW_NAME = {0: 'e8', 1: 'e16', 2: 'e32', 3: 'e64'}


def _sample_case(*, addr, element_window='active', address_boundary=None,
                 ordering=None, restart='normal', outcome='dut-pass',
                 segment=None, full_uop=False):
    operation = {
        0: 'strided-load',
        1: 'strided-store',
        4: 'indexed-unordered-load',
        5: 'indexed-unordered-store',
        6: 'indexed-ordered-load',
        7: 'indexed-ordered-store',
    }[addr.uop_type]
    if address_boundary is None:
        address_boundary = 'index-zero-extended' if addr.uop_type >= 4 else 'stride-zero'
    if ordering is None:
        ordering = 'unordered' if addr.uop_type in (4, 5) else (
            'ordered-load' if addr.uop_type == 6 else 'ordered-store'
        )
    if segment is None:
        data_width = (addr.nf + 1) * (1 << addr.deew)
        segment = (
            'non-segment' if addr.nf == 0 else
            'segment-narrow' if data_width <= 16 else 'segment-cross-flow'
        )
    DUT_COVERAGE.sample(
        operation=operation,
        lmul=_LMUL_NAME[addr.vlmul],
        data_eew=_EEW_NAME[addr.deew],
        index_eew=_EEW_NAME[addr.ieew] if addr.uop_type >= 4 else 'na',
        element_window=element_window,
        segment_mop='full-uop-union' if full_uop else segment,
        address_boundary=address_boundary,
        ordering=ordering,
        restart_protocol=restart,
        audit_outcome=outcome,
    )


def _addr(*, entry, rob, uop_type, vl=2, vstart=0, v0=0x3,
          vma=0, vta=0, deew=0, ieew=0, emul=0, nf=0,
          vsew=None, vlmul=0, last_uop=1, uop_idx=0):
    if not 0 <= rob < (1 << 9):
        raise ValueError('ROB identity must fit the actual 9-bit public leaf')
    return AddrPacket(
        entry_idx=entry,
        uop_type=uop_type,
        rob_value=rob,
        pdest=3 + entry,
        psrc2=4 + entry,
        base_addr=0x1000 + entry * 0x100,
        v0_byte_mask=v0,
        deew=deew,
        ieew=ieew,
        emul=emul,
        vl=vl,
        vstart=vstart,
        vma=vma,
        vta=vta,
        uop_idx=uop_idx,
        last_uop=last_uop,
        nf=nf,
        vsew=deew if vsew is None else vsew,
        vlmul=vlmul,
    )


def _data(addr, value):
    return DataPacket(
        entry_idx=addr.entry_idx,
        rob_value=addr.rob_value,
        op2_data=value,
    )


def _feature_packet(case, ordinal):
    """Encode one independent feature shape at the actual public boundary."""
    emul = emul_encoding(
        vsew=case.vsew, vlmul=case.vlmul, eew=case.data_eew,
    )
    uop_type = {
        (False, True): 6,
        (False, False): 4,
        (True, True): 7,
        (True, False): 5,
    }.get((case.load, case.ordered), 0)
    if not case.indexed:
        uop_type = 0 if case.load else 1
    public_mask = 0xffff if case.nf else 1
    addr = AddrPacket(
        entry_idx=ordinal % 8,
        uop_type=uop_type,
        rob_value=100 + ordinal,
        pdest=8 + (ordinal % 32),
        psrc2=16 + (ordinal % 32),
        base_addr=0x100000 + ordinal * 0x100,
        v0_byte_mask=public_mask,
        deew=case.data_eew,
        ieew=case.index_eew,
        emul=emul,
        vl=1,
        vstart=0,
        vma=0,
        vta=0,
        uop_idx=0,
        last_uop=1,
        nf=case.nf,
        vsew=case.vsew,
        vlmul=case.vlmul,
    )
    if case.indexed:
        index_value = 0x20
        return addr, _data(addr, index_value), (index_value,)
    return addr, _data(addr, 8), None


def _active_outputs(outputs, *, load):
    group = 'lduReq' if load else 'staReq'
    lanes = 3 if load else 2
    result = []
    for lane in range(lanes):
        prefix = f'io_{group}_{lane}_'
        if outputs.get(prefix + 'valid') and outputs.get(prefix + 'bits_meta_valid'):
            result.append({
                'lane': lane,
                'element': outputs[prefix + 'bits_meta_elemIdx'],
                'byte': outputs[prefix + 'bits_meta_byteOffset'],
                'data_mask': outputs[prefix + 'bits_meta_dataMask'],
                'address': outputs[prefix + 'bits_req_data_src_0'],
                'entry': outputs[prefix + 'bits_meta_entryIdx'],
                'rob': outputs[prefix + 'bits_req_robIdx_value'],
                'lq': outputs[prefix + 'bits_req_lqIdx_value'],
                'sq': outputs[prefix + 'bits_req_sqIdx_value'],
            })
    return result


def _responses_for_ready(outputs, beat, *, data=0):
    next_beat = response_beat(
        outputs,
        base=Beat(
            ldu_ready=beat.ldu_ready,
            sta_ready=beat.sta_ready,
            empty_ready=beat.empty_ready,
        ),
        data=data,
    )
    return replace(
        next_beat,
        ldu_resp=tuple(
            response if beat.ldu_ready[lane] else Response()
            for lane, response in enumerate(next_beat.ldu_resp)
        ),
        sta_resp=tuple(
            response if beat.sta_ready[lane] else Response()
            for lane, response in enumerate(next_beat.sta_resp)
        ),
    )


def _run_single(env, addr, data, *, index_values=None, arch_mask=None, vrf_data=0,
                return_empty=False, compare_first_field_only=False, limit=160,
                trace_path=None):
    """Run one entry and collect fired public memory requests."""
    # The integration checker is a separate implementation model.  This test
    # intentionally compares the DUT with isa_reference.py instead.
    env.checker.compare = lambda *_args: None
    env.reset()
    env.cycle(Beat())
    load = (addr.uop_type & 1) == 0
    beat = Beat(
        addr=(addr, None),
        addr_valid=(True, False),
        stride=(data, None) if addr.uop_type < 4 else (None, None),
        stride_valid=(True, False) if addr.uop_type < 4 else (False, False),
        index=(data, None) if addr.uop_type >= 4 else (None, None),
        index_valid=(True, False) if addr.uop_type >= 4 else (False, False),
    )
    observed = []
    empty_observed = []
    if trace_path is not None:
        trace_path.write_text('')
    for cycle in range(limit):
        outputs = env.cycle(
            beat,
            admit=(addr, data) if cycle == 0 else None,
        )
        if trace_path is not None:
            with trace_path.open('a') as stream:
                stream.write(json.dumps({'cycle': cycle, 'input': asdict(beat), 'outputs': outputs}) + '\n')
        for item in _active_outputs(outputs, load=load):
            item['cycle'] = cycle
            observed.append(item)
        for lane in range(2):
            prefix = f'io_lsqEmptyReq_{lane}_'
            if outputs.get(prefix + 'valid'):
                empty_observed.append({
                    'cycle': cycle,
                    'entry': outputs[prefix + 'bits_entryIdx'],
                    'mask': outputs[prefix + 'bits_issueMask'],
                    'rob': outputs[prefix + 'bits_robIdx_value'],
                    'is_load': outputs[prefix + 'bits_isLoad'],
                    'lq': outputs[prefix + 'bits_lqIdx_value'],
                })
        if outputs.get('io_robWriteback_valid'):
            assert outputs['io_robWriteback_bits_entryIdx'] == addr.entry_idx
            assert outputs['io_robWriteback_bits_robIdx_value'] == addr.rob_value
            break
        beat = response_beat(outputs, data=vrf_data)
    else:
        raise AssertionError(f'uop type {addr.uop_type} did not complete')

    expected = architectural_accesses(
        kind='indexed' if addr.uop_type >= 4 else 'strided',
        base=addr.base_addr,
        vsew=addr.vsew,
        vlmul=addr.vlmul,
        vl=addr.vl,
        vstart=addr.vstart,
        mask=addr.v0_byte_mask if arch_mask is None else arch_mask,
        data_eew=addr.deew,
        nf=addr.nf,
        stride=data.op2_data,
        index_values=index_values,
        index_eew=addr.ieew,
        index_data=data.op2_data,
    )
    coalesced_segment = addr.nf and (addr.nf + 1) * (1 << addr.deew) <= 16
    expected_pairs = {
        (item.element, item.address) for item in expected
        if (compare_first_field_only or coalesced_segment) and item.field == 0
        or not compare_first_field_only and not coalesced_segment
    }
    observed_pairs = Counter((item['element'], item['address']) for item in observed)
    assert observed_pairs == Counter(expected_pairs)
    assert all(item['entry'] == addr.entry_idx and item['rob'] == addr.rob_value for item in observed)
    return (observed, empty_observed) if return_empty else observed


@pytest.mark.parametrize(
    'uop_type', (0, 1, 4, 5, 6, 7),
)
def test_all_vagq_memory_operation_kinds_match_independent_access_set(vagq_env, uop_type):
    is_indexed = uop_type >= 4
    is_load = (uop_type & 1) == 0
    if is_indexed:
        indices = (0x20, 0x40)
        op2 = indices[0] | (indices[1] << 8)
    else:
        indices = None
        op2 = (1 << 64) - 8 if uop_type < 2 else 8
    addr = _addr(
        entry=uop_type,
        rob=100 + uop_type,
        uop_type=uop_type,
        vl=2,
        v0=0x3,
        deew=0,
        ieew=0,
        emul=0,
    )
    _sample_case(
        addr=addr,
        address_boundary=(
            'stride-negative' if uop_type == 0 else
            'stride-positive' if uop_type == 1 else
            'index-zero-extended'
        ),
    )
    _run_single(
        vagq_env,
        addr,
        _data(addr, op2),
        index_values=indices,
        vrf_data=0x0123456789ABCDEFFEDCBA9876543210 if not is_load else 0,
    )


def test_generated_dut_representative_public_feature_shapes_match_rvv_oracle(
    vagq_env,
):
    """Execute the independent covering set on the real generated root.

    This is deliberately a single managed DUT test so that the covering set is
    affordable while every selected shape still gets a reset, public admission,
    request trace, response, and independent architectural comparison.
    Segment shapes here are standalone port injections, not reachable decoded
    instructions in the current integration. Their raw overlap observation and
    decoder exclusion are checked in test_wide_segment_source_audit.py. An
    unexpected address mismatch still fails with the feature-shape identity.
    """
    failures = []
    for ordinal, case in enumerate(representative_public_feature_cases()):
        addr, data, index_values = _feature_packet(case, ordinal)
        _sample_case(
            addr=addr,
            segment=(
                'non-segment' if case.nf == 0 else
                'segment-narrow' if (case.nf + 1) * (1 << case.data_eew) <= 16
                else 'segment-cross-flow'
            ),
            full_uop=case.uop_count > 1,
        )
        PUBLIC_FEATURE_COVERAGE.sample(
            operation={
                0: 'strided-load', 1: 'strided-store',
                4: 'indexed-unordered-load', 5: 'indexed-unordered-store',
                6: 'indexed-ordered-load', 7: 'indexed-ordered-store',
            }[case.operation],
            vsew={0: 'e8', 1: 'e16', 2: 'e32', 3: 'e64'}[case.vsew],
            vlmul={5: 'mf8', 6: 'mf4', 7: 'mf2', 0: 'm1', 1: 'm2',
                   2: 'm4', 3: 'm8'}[case.vlmul],
            data_eew={0: 'e8', 1: 'e16', 2: 'e32', 3: 'e64'}[case.data_eew],
            index_eew=(
                {0: 'e8', 1: 'e16', 2: 'e32', 3: 'e64'}[case.index_eew]
                if case.indexed else 'na'
            ),
            nf=str(case.nf),
            uop_count=str(case.uop_count),
            comparison='pass',
            shape_id=feature_case_id(case),
        )
        try:
            _run_single(
                vagq_env,
                addr,
                data,
                index_values=index_values,
                arch_mask=1,
                vrf_data=(
                    0x0123456789ABCDEFFEDCBA9876543210
                    if not case.load else 0
                ),
                # This one-uop probe observes only the first public flow.  The
                # pending production-path byte-union obligation is explicitly
                # skipped below; standalone observations are audited separately.
                compare_first_field_only=True,
            )
        except AssertionError as exc:
            failures.append({
                'operation': case.operation,
                'vsew': case.vsew,
                'vlmul': case.vlmul,
                'data_eew': case.data_eew,
                'index_eew': case.index_eew,
                'nf': case.nf,
                'uop_count': case.uop_count,
                'error': str(exc),
            })
    assert not failures, f'independent public feature mismatches: {failures}'


def test_negative_stride_and_nondefault_data_index_widths_match_rvv_address_oracle(vagq_env):
    addr = _addr(
        entry=0, rob=120, uop_type=0, vl=2, v0=0x3,
        deew=2, ieew=0, emul=0, vsew=2, vlmul=0,
    )
    addr = replace(addr, v0_byte_mask=0x11)
    _sample_case(addr=addr, address_boundary='stride-negative')
    _run_single(
        vagq_env, addr, _data(addr, (1 << 64) - 16), arch_mask=0x3, vrf_data=0,
    )

    addr = _addr(
        entry=1, rob=121, uop_type=4, vl=2, v0=0x3,
        deew=1, ieew=2, emul=0, vsew=1, vlmul=0,
    )
    addr = replace(addr, v0_byte_mask=0x5)
    _sample_case(addr=addr, address_boundary='index-zero-extended')
    indices = (0x80000000, 0x12345678)
    _run_single(
        vagq_env,
        addr,
        _data(addr, indices[0] | (indices[1] << 32)),
        index_values=indices,
        arch_mask=0x3,
    )


def test_vagq_stride_address_wraps_at_xlen_boundary(vagq_env):
    addr = _addr(
        entry=7, rob=124, uop_type=0, vl=2, v0=0x3,
        deew=0, ieew=0, emul=0, vsew=0, vlmul=0,
    )
    addr = replace(addr, base_addr=(1 << 64) - 4)
    _sample_case(addr=addr, address_boundary='xlEN-wrap')
    observed = _run_single(
        vagq_env, addr, _data(addr, 8), arch_mask=0x3,
    )
    assert {(item['element'], item['address']) for item in observed} == {
        (0, (1 << 64) - 4), (1, 4),
    }


def test_segment_flow_requests_match_architectural_element_field_addresses(vagq_env):
    addr = _addr(
        entry=2, rob=122, uop_type=4, vl=2, v0=0x3f,
        deew=2, ieew=0, emul=0, nf=2, vsew=2, vlmul=0,
    )
    _sample_case(addr=addr, segment='segment-narrow')
    indices = (0x20, 0x40)
    observed = _run_single(
        vagq_env,
        addr,
        _data(addr, indices[0] | (indices[1] << 8)),
        index_values=indices,
        arch_mask=0x3,
    )
    expected = architectural_accesses(
        kind='indexed', base=addr.base_addr, vsew=addr.vsew,
        vlmul=addr.vlmul, vl=addr.vl, vstart=addr.vstart,
        mask=0x3, data_eew=addr.deew, nf=addr.nf,
        index_values=indices, index_eew=addr.ieew,
    )
    # One public VAGQ request carries all contiguous fields of an element when
    # the segment fits in one 16-byte flow.  The architectural oracle still
    # expands fields; compare the request address to field zero and check the
    # public data mask covers the complete segment.
    assert {(item['element'], item['address']) for item in observed} == {
        (item.element, item.address) for item in expected if item.field == 0
    }
    assert {item['data_mask'] for item in observed} == {0xFFF}


def test_nonzero_segment_start_field_is_visible_in_real_request_address(vagq_env):
    addr = _addr(
        entry=2, rob=123, uop_type=4, vl=2, v0=0xffff,
        deew=2, ieew=0, emul=0, nf=4, vsew=2, vlmul=0,
        uop_idx=1,
    )
    _sample_case(addr=addr, segment='nonzero-start-field')
    data = _data(addr, 0x21 | (0x32 << 8))
    vagq_env.checker.compare = lambda *_args: None
    vagq_env.reset()
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(addr, None), addr_valid=(True, False),
        index=(data, None), index_valid=(True, False),
    )
    observed = False
    for cycle in range(100):
        outputs = vagq_env.cycle(
            beat, admit=(addr, data) if cycle == 0 else None,
        )
        for lane in range(3):
            prefix = f'io_lduReq_{lane}_'
            if outputs.get(prefix + 'valid') and outputs.get(prefix + 'bits_meta_valid'):
                if outputs[prefix + 'bits_meta_elemIdx'] == 0:
                    assert outputs[prefix + 'bits_meta_dataMask'] == 0xF
                    assert outputs[prefix + 'bits_req_data_src_0'] == 0x1231
                    observed = True
        if outputs.get('io_robWriteback_valid'):
            break
        beat = response_beat(outputs)
    else:
        raise AssertionError('nonzero field-offset probe did not complete')
    assert observed


@pytest.mark.parametrize('eew', range(4))
def test_all_data_and_index_eew_widths_match_independent_addresses(vagq_env, eew):
    element_bytes = 1 << eew
    public_mask = sum(1 << (element * element_bytes) for element in range(2))
    stride_addr = _addr(
        entry=3, rob=130 + eew, uop_type=0, vl=2,
        v0=public_mask, deew=eew, ieew=0, emul=0,
        vsew=eew, vlmul=0,
    )
    _sample_case(
        addr=stride_addr,
        address_boundary='stride-zero' if eew == 0 else 'stride-positive',
    )
    _run_single(
        vagq_env, stride_addr, _data(stride_addr, element_bytes * 3),
        arch_mask=0x3,
    )

    index_addr = _addr(
        entry=4, rob=140 + eew, uop_type=4, vl=2,
        v0=public_mask, deew=eew, ieew=eew, emul=0,
        vsew=eew, vlmul=0,
    )
    _sample_case(addr=index_addr, address_boundary='index-zero-extended')
    index_width = element_bytes * 8
    indices = (0x20, 0x40)
    index_data = indices[0] | (indices[1] << index_width)
    _run_single(
        vagq_env, index_addr, _data(index_addr, index_data),
        index_values=indices, arch_mask=0x3,
    )


@pytest.mark.parametrize(
    'vlmul,vsew,vl,emul', ((1, 0, 4, 1), (2, 1, 4, 2), (3, 2, 2, 3)),
)
def test_integer_lmul_register_groups_preserve_architectural_element_indices(
    vagq_env, vlmul, vsew, vl, emul,
):
    element_bytes = 1 << vsew
    public_mask = sum(1 << (element * element_bytes) for element in range(vl))
    addr = _addr(
        entry=5, rob=150 + vlmul, uop_type=0, vl=vl,
        v0=public_mask, deew=vsew, ieew=0, emul=emul,
        vsew=vsew, vlmul=vlmul,
    )
    _sample_case(addr=addr, address_boundary='stride-positive')
    _run_single(
        vagq_env, addr, _data(addr, element_bytes * 5), arch_mask=(1 << vl) - 1,
    )


@pytest.mark.parametrize('nf', range(1, 8))
def test_narrow_segment_field_counts_are_coalesced_without_losing_element_identity(
    vagq_env, nf,
):
    addr = _addr(
        entry=6, rob=170 + nf, uop_type=4, vl=2, v0=0xffff,
        deew=0, ieew=0, emul=0, nf=nf, vsew=0, vlmul=0,
    )
    _sample_case(addr=addr, segment='segment-narrow')
    indices = (0x20, 0x40)
    observed = _run_single(
        vagq_env, addr, _data(addr, indices[0] | (indices[1] << 8)),
        index_values=indices, arch_mask=0x3,
    )
    assert {item['data_mask'] for item in observed} == {(1 << (nf + 1)) - 1}


@pytest.mark.parametrize(
    'vlmul,vl,emul', ((5, 2, 5), (6, 4, 6), (7, 8, 7)),
)
def test_fractional_lmul_memory_matches_vlmax_and_cleanup_stays_in_allocation(
    vagq_env, tmp_path, vlmul, vl, emul,
):
    # Do not hide padding with zero mask bits: vl must bound actual memory.
    public_mask = 0xffff
    addr = _addr(
        entry=7, rob=190 + vlmul, uop_type=0, vl=vl,
        v0=public_mask, deew=0, ieew=0, emul=emul,
        vsew=0, vlmul=vlmul,
    )
    addr = replace(addr, lq_value=32)
    observed, empty = _run_single(
        vagq_env, addr, _data(addr, 0x10), arch_mask=(1 << vl) - 1,
        return_empty=True,
        trace_path=tmp_path / 'fractional-boundary-events.jsonl',
    )
    # Independent RVV address/multiplicity comparison is in _run_single.
    assert Counter(item['element'] for item in observed) == Counter(range(vl))
    assert {item['lq'] for item in observed} == set(range(32, 32 + vl))
    # Sixteen slots were reserved by the producer; only unused slots are freed.
    assert Counter(item['mask'] for item in empty) == Counter(1 << site for site in range(vl, 16))
    assert Counter(item['lq'] for item in empty) == Counter(range(32 + vl, 48))
    assert all(item['lq'] == 32 + item['mask'].bit_length() - 1 for item in empty)
    assert all(item['entry'] == addr.entry_idx and item['rob'] == addr.rob_value
               and item['is_load'] == 1 for item in empty)
    _sample_case(addr=addr)


@pytest.mark.parametrize('uop_type', (4, 6))
def test_multi_uop_index_window_is_partitioned_without_gaps_or_duplicates(
    vagq_env, uop_type,
):
    """Check uopIdx=0/1 against a full architectural VLMAX=32 access set."""
    first = _addr(
        entry=0, rob=210, uop_type=uop_type, vl=32, v0=0xffff,
        deew=0, ieew=0, emul=1, vsew=0, vlmul=1,
    )
    first = replace(first, last_uop=0)
    second = replace(first, entry_idx=1, uop_idx=1, last_uop=1)
    _sample_case(addr=first, full_uop=True)
    first_data = _data(first, sum((0x10 + index) << (8 * index) for index in range(16)))
    second_data = _data(second, sum((0x20 + index) << (8 * index) for index in range(16)))

    vagq_env.checker.compare = lambda *_args: None
    vagq_env.reset()
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(first, second), addr_valid=(True, True),
        index=(first_data, second_data), index_valid=(True, True),
    )
    observed = {first.entry_idx: [], second.entry_idx: []}
    completed = set()
    last_outputs = {}
    ready_history = []
    for cycle in range(240):
        outputs = vagq_env.cycle(
            beat,
            admit=[(first, first_data), (second, second_data)]
            if cycle == 0 else None,
        )
        last_outputs = outputs
        ready_history.append((
            outputs.get('io_addrUop_0_ready'),
            outputs.get('io_addrUop_1_ready'),
        ))
        for lane in range(3):
            prefix = f'io_lduReq_{lane}_'
            if outputs.get(prefix + 'valid') and outputs.get(prefix + 'bits_meta_valid'):
                entry = outputs[prefix + 'bits_meta_entryIdx']
                observed.setdefault(entry, []).append((
                    outputs[prefix + 'bits_meta_elemIdx'],
                    outputs[prefix + 'bits_req_data_src_0'],
                ))
        if outputs.get('io_robWriteback_valid'):
            completed.add(outputs['io_robWriteback_bits_entryIdx'])
        if completed == {first.entry_idx, second.entry_idx}:
            break
        beat = response_beat(outputs)
    else:
        raise AssertionError(
            f'multi-uop indexed load did not complete: observed={observed}, '
            f'last_writeback={last_outputs.get("io_robWriteback_valid")}, '
            f'ready={ready_history[:8]}'
        )

    base = first.base_addr
    assert set(observed[first.entry_idx]) == {
        (element, base + 0x10 + element) for element in range(16)
    }
    assert set(observed[second.entry_idx]) == {
        (element, base + 0x20 + (element - 16)) for element in range(16, 32)
    }
    assert not (
        set(observed[first.entry_idx]) & set(observed[second.entry_idx])
    )


def test_prestart_inactive_tail_and_vstart_ge_vl_do_not_generate_active_memory(
    vagq_env,
):
    # Element 0 is prestart, element 1 is masked inactive, element 2 is the
    # only active element.  Tail/inactive work may be represented by the
    # internal empty-marker protocol, but must never become an LSU request.
    addr = _addr(
        entry=0, rob=240, uop_type=0, vl=3, vstart=1, v0=0x5,
    )
    _sample_case(addr=addr, element_window='prestart')
    observed, empty = _run_single(
        vagq_env, addr, _data(addr, 8), arch_mask=0x5, return_empty=True,
    )
    assert {(item['element'], item['address']) for item in observed} == {
        (2, addr.base_addr + 16),
    }
    assert empty
    assert all(not (item['mask'] & (1 << 2)) for item in empty)

    # RVV specifies no body and no agnostic tail update when vstart >= vl.
    no_body = _addr(
        entry=1, rob=241, uop_type=0, vl=2, vstart=2, v0=0xffff,
        vma=1, vta=1,
    )
    _sample_case(addr=no_body, element_window='vstart-ge-vl')
    observed, _ = _run_single(
        vagq_env, no_body, _data(no_body, 8), arch_mask=0x3,
        return_empty=True,
    )
    assert observed == []


def test_mask_and_tail_agnostic_policy_changes_only_allowed_destination_window(
    vagq_env,
):
    # The memory-side invariant is strict even when the destination policy is
    # agnostic: only element 0 may issue a memory request.  The old-vd/ones
    # choice itself is checked by the independent pure oracle and MergeCtrl
    # child evidence, not collapsed into one implementation-specific value.
    addr = _addr(
        entry=2, rob=242, uop_type=0, vl=2, v0=0x1,
        vma=1, vta=1,
    )
    _sample_case(addr=addr, element_window='inactive')
    _sample_case(addr=addr, element_window='tail')
    observed, _ = _run_single(
        vagq_env, addr, _data(addr, 8), arch_mask=0x1,
        vrf_data=0xFFEEDDCCBBAA99887766554433221100,
        return_empty=True,
    )
    assert {(item['element'], item['address']) for item in observed} == {
        (0, addr.base_addr),
    }


def test_real_load_request_is_stable_under_backpressure(vagq_env):
    addr = _addr(entry=4, rob=244, uop_type=0, vl=1, v0=0x1)
    data = _data(addr, 8)
    _sample_case(addr=addr, restart='backpressure')
    vagq_env.checker.compare = lambda *_args: None
    vagq_env.reset()
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(addr, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
        ldu_ready=(False, False, False),
    )
    held = None
    released = False
    for cycle in range(80):
        outputs = vagq_env.cycle(
            beat, admit=(addr, data) if cycle == 0 else None,
        )
        active = _active_outputs(outputs, load=True)
        if active and not released:
            signature = tuple(
                (item['element'], item['byte'], item['data_mask'], item['address'])
                for item in active
            )
            held = signature if held is None else held
            assert signature == held
        released = cycle >= 8
        beat = _responses_for_ready(
            outputs,
            replace(beat, ldu_ready=(released, released, released)),
        )
        beat = replace(beat, ldu_ready=(released, released, released))
        if released and active:
            break
    assert held is not None and released


def test_load_nack_retries_the_same_architectural_element(vagq_env):
    addr = _addr(entry=5, rob=245, uop_type=0, vl=1, v0=0x1)
    data = _data(addr, 8)
    _sample_case(addr=addr, restart='nack-retry')
    vagq_env.checker.compare = lambda *_args: None
    vagq_env.reset()
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(addr, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
    )
    nacked = False
    retried = False
    for cycle in range(100):
        outputs = vagq_env.cycle(
            beat, admit=(addr, data) if cycle == 0 else None,
        )
        active = _active_outputs(outputs, load=True)
        if active and nacked:
            retried = True
        next_beat = response_beat(outputs)
        if active and not nacked:
            lane = active[0]['lane']
            responses = list(next_beat.ldu_resp)
            responses[lane] = replace(responses[lane], is_nack=1)
            next_beat = replace(next_beat, ldu_resp=tuple(responses))
            nacked = True
        beat = next_beat
        if outputs.get('io_robWriteback_valid'):
            break
    else:
        raise AssertionError('NACK retry did not complete')
    assert nacked and retried


def test_redirect_flushes_pending_public_request_without_writeback(vagq_env):
    from vagqverify.vagq.types import Redirect

    addr = _addr(entry=6, rob=246, uop_type=0, vl=1, v0=0x1)
    data = _data(addr, 8)
    _sample_case(addr=addr, restart='redirect')
    vagq_env.checker.compare = lambda *_args: None
    vagq_env.reset()
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(addr, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
        ldu_ready=(False, False, False),
    )
    redirected = False
    saw_flush = False
    for cycle in range(40):
        outputs = vagq_env.cycle(
            beat, admit=(addr, data) if cycle == 0 else None,
        )
        active = _active_outputs(outputs, load=True)
        if active and not redirected:
            redirected = True
            beat = replace(
                _responses_for_ready(outputs, beat),
                redirect=Redirect(valid=True, level=1, rob_value=addr.rob_value),
            )
            continue
        if redirected:
            saw_flush |= not _active_outputs(outputs, load=True)
        beat = replace(
            _responses_for_ready(outputs, beat),
            redirect=beat.redirect,
        )
        if redirected and saw_flush:
            break
    assert redirected and saw_flush


def test_store_precise_fault_restarts_at_fault_element_without_repeating_prefix(
    vagq_env,
):
    original = _addr(
        entry=3, rob=250, uop_type=1, vl=3, vstart=0, v0=0x7,
    )
    _sample_case(addr=original, restart='store-exception')
    data = _data(original, 8)
    vagq_env.checker.compare = lambda *_args: None
    vagq_env.reset()
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(original, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
        sta_ready=(True, True),
    )
    prefix = []
    fault_sent = False
    for cycle in range(120):
        outputs = vagq_env.cycle(
            beat, admit=(original, data) if cycle == 0 else None,
        )
        active = _active_outputs(outputs, load=False)
        prefix.extend(item['element'] for item in active)
        next_beat = response_beat(
            outputs, data=0x0123456789ABCDEFFEDCBA9876543210,
        )
        if not fault_sent:
            lane = next(
                (item['lane'] for item in active if item['element'] == 1),
                None,
            )
            if lane is not None:
                responses = list(next_beat.sta_resp)
                responses[lane] = replace(
                    responses[lane], exception=1, exception_number=11,
                    fault_elem_idx=1,
                )
                next_beat = replace(next_beat, sta_resp=tuple(responses))
                fault_sent = True
        beat = next_beat
        if outputs.get('io_robWriteback_valid'):
            assert outputs['io_robWriteback_bits_exception'] == 1
            break
    else:
        raise AssertionError('store precise-fault trace did not write back')
    assert fault_sent and 0 in prefix and 1 in prefix

    vagq_env.model.plans[original.entry_idx].flushed = True
    restart = replace(original, vstart=1)
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(restart, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
        sta_ready=(True, True),
    )
    resumed = []
    for cycle in range(120):
        outputs = vagq_env.cycle(
            beat, admit=(restart, data) if cycle == 0 else None,
        )
        resumed.extend(item['element'] for item in _active_outputs(outputs, load=False))
        beat = response_beat(
            outputs, data=0x0123456789ABCDEFFEDCBA9876543210,
        )
        if outputs.get('io_robWriteback_valid'):
            assert outputs['io_robWriteback_bits_exception'] == 0
            break
    else:
        raise AssertionError('store restart did not complete')
    assert resumed and min(resumed) >= 1 and set(resumed) >= {1, 2}


def test_load_precise_fault_restarts_at_reported_vstart(vagq_env):
    original = _addr(entry=0, rob=260, uop_type=0, vl=3, vstart=0, v0=0x7)
    data = _data(original, 8)
    _sample_case(addr=original, restart='load-exception-restart')
    vagq_env.checker.compare = lambda *_args: None
    vagq_env.reset()
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(original, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
    )
    fault_sent = False
    for cycle in range(120):
        outputs = vagq_env.cycle(
            beat, admit=(original, data) if cycle == 0 else None,
        )
        active = _active_outputs(outputs, load=True)
        next_beat = response_beat(outputs)
        if not fault_sent:
            lane = next(
                (item['lane'] for item in active if item['element'] == 1),
                None,
            )
            if lane is not None:
                responses = list(next_beat.ldu_resp)
                responses[lane] = replace(
                    responses[lane], exception=1, exception_number=9,
                    fault_elem_idx=1,
                )
                next_beat = replace(next_beat, ldu_resp=tuple(responses))
                fault_sent = True
        beat = next_beat
        if outputs.get('io_robWriteback_valid'):
            assert outputs['io_robWriteback_bits_exception'] == 1
            break
    else:
        raise AssertionError('load precise-fault trace did not write back')
    assert fault_sent

    vagq_env.model.plans[original.entry_idx].flushed = True
    restart = replace(original, vstart=1)
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(restart, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
    )
    resumed = []
    for cycle in range(120):
        outputs = vagq_env.cycle(
            beat, admit=(restart, data) if cycle == 0 else None,
        )
        resumed.extend(item['element'] for item in _active_outputs(outputs, load=True))
        beat = response_beat(outputs)
        if outputs.get('io_robWriteback_valid'):
            assert outputs['io_robWriteback_bits_exception'] == 0
            break
    else:
        raise AssertionError('load restart did not complete')
    assert resumed and min(resumed) >= 1 and set(resumed) >= {1, 2}


@pytest.mark.skip(reason=(
    'Current DecodeStage enables VAGQ only for nf=0; nf=4 is not a production-path input. '
    'Forced-port overlap observations remain covered by test_wide_segment_source_audit.py'
))
def test_wide_segment_production_path_covers_each_architectural_memory_byte():
    """Pending integration obligation; raw masks alone are not memory effects."""
    raise AssertionError('Use the actual producer/consumer path before enabling segment ISA acceptance')
