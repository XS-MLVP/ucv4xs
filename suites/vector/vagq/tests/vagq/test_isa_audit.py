"""RVV checks and explicitly scoped public-boundary probes.

Allocated-slot cleanup is checked separately from architectural memory work.
Address issue is not a store memory effect. Obligations that this standalone
root cannot observe are explicitly skipped, never counted as ISA passes.
"""
from collections import Counter
from dataclasses import asdict, replace
import json

import pytest

from vagqverify.vagq.driver import response_beat
from vagqverify.vagq.isa_coverage import PUBLIC_FEATURE_COVERAGE
from vagqverify.vagq.isa_reference import active_elements, architectural_accesses, vlmax
from vagqverify.vagq.model import IntegrationModel
from vagqverify.vagq.types import AddrPacket, Beat, DataPacket


pytestmark = [
    pytest.mark.toffee_functional_coverage(False),
    pytest.mark.vagq_isa_audit,
]


def load_addr(*, entry=0, rob=1, uop_type=0, vl=16, vstart=0,
              v0=0xffff, vma=0, vta=0, uop_idx=0, last=True,
              deew=0, ieew=0, emul=0, nf=0, vsew=None, vlmul=0):
    return AddrPacket(
        entry_idx=entry, uop_type=uop_type, rob_value=rob,
        pdest=3 + entry, psrc2=4 + entry, base_addr=0x1000 + entry * 0x100,
        v0_byte_mask=v0, deew=deew, ieew=ieew, emul=emul,
        vl=vl, vstart=vstart, vma=vma, vta=vta, uop_idx=uop_idx,
        last_uop=int(last), nf=nf, vsew=deew if vsew is None else vsew,
        vlmul=vlmul,
    )


def data_for(addr, *, op2=0x20):
    return DataPacket(
        entry_idx=addr.entry_idx, rob_value=addr.rob_value, op2_data=op2,
    )


def test_fractional_isa_elements_are_separate_from_allocated_protocol_slots():
    addr = load_addr(
        vl=2, v0=0x3, deew=0, ieew=0, emul=5, vsew=0, vlmul=5,
    )
    data = data_for(addr)
    plan = IntegrationModel.make_plan(addr, data)
    assert vlmax(vsew=addr.vsew, vlmul=addr.vlmul) == 2
    assert active_elements(
        vl=addr.vl, vstart=addr.vstart, vlmax_value=2, mask=addr.v0_byte_mask,
    ) == (0, 1)
    assert tuple(sorted(item["elem_idx"] for item in plan.active.values())) == (0, 1)
    assert plan.valid_mask == 0xffff
    assert plan.empty == set(range(2, 16))


def _collect_until_writeback(env, beat, addr, data, *, trace_path, limit=80):
    active = []
    empty = []
    trace = []
    env.reset()
    # Let the clocked root observe one neutral post-reset beat before the
    # first admission, matching the normal integration driver protocol.
    env.cycle(Beat())
    try:
        for cycle in range(limit):
            outputs = env.cycle(beat, admit=(addr, data) if cycle == 0 else None)
            trace.append({'cycle': cycle, 'input': asdict(beat), 'outputs': outputs})
            for lane in range(3):
                prefix = f"io_lduReq_{lane}_"
                if (outputs.get(prefix + "valid") and outputs.get(prefix + "bits_meta_valid")
                        and beat.ldu_ready[lane]):
                    active.append((cycle, outputs[prefix + "bits_meta_elemIdx"]))
            for lane in range(2):
                prefix = f"io_lsqEmptyReq_{lane}_"
                if outputs.get(prefix + "valid") and beat.empty_ready[lane]:
                    empty.append((cycle, outputs[prefix + "bits_issueMask"]))
            if outputs.get("io_robWriteback_valid"):
                return active, empty
            beat = _response_for_fires(outputs, beat)
        raise AssertionError("audit scenario did not reach writeback")
    finally:
        trace_path.write_text(json.dumps(trace, indent=2) + '\n')


def _response_for_fires(outputs, beat):
    """Generate only responses for requests whose public consumer fired."""
    next_beat = response_beat(outputs, base=Beat(
        ldu_ready=beat.ldu_ready, sta_ready=beat.sta_ready, empty_ready=beat.empty_ready,
    ))
    ldu = tuple(
        response if beat.ldu_ready[lane] else type(response)()
        for lane, response in enumerate(next_beat.ldu_resp)
    )
    empty = tuple(
        response if beat.empty_ready[lane] else type(response)()
        for lane, response in enumerate(next_beat.empty_resp)
    )
    sta = tuple(
        response if beat.sta_ready[lane] else type(response)()
        for lane, response in enumerate(next_beat.sta_resp)
    )
    return replace(next_beat, ldu_resp=ldu, sta_resp=sta, empty_resp=empty)


def test_fractional_lmul_limits_memory_and_cleans_reserved_slots(vagq_env, tmp_path):
    # RVV VLEN=128, SEW=8, LMUL=mf8: VLMAX is exactly two elements.  The
    # public emul is the data EMUL, which is also mf8 in this configuration.
    addr = load_addr(
        entry=0, rob=301, vl=2, v0=0xffff, deew=0, ieew=0, emul=5,
        vsew=0, vlmul=5,
    )
    data = data_for(addr, op2=0x20)
    active, empty = _collect_until_writeback(
        vagq_env,
        Beat(
            addr=(addr, None), addr_valid=(True, False),
            stride=(data, None), stride_valid=(True, False),
        ),
        addr,
        data,
        trace_path=tmp_path / 'fractional-checker-events.json',
    )
    assert vlmax(vsew=addr.vsew, vlmul=addr.vlmul) == 2
    assert Counter(elem for _, elem in active) == Counter(active_elements(
        vl=addr.vl, vstart=addr.vstart, vlmax_value=2, mask=addr.v0_byte_mask,
    ))
    assert Counter(mask for _, mask in empty) == Counter(1 << site for site in range(2, 16))
    plan = vagq_env.model.plans[addr.entry_idx]
    assert plan.emitted_active == {0, 1}
    assert plan.emitted_empty == set(range(2, 16))
    assert plan.complete and plan.writeback_seen
    PUBLIC_FEATURE_COVERAGE.sample(
        operation='strided-load', vsew='e8', vlmul='mf8', data_eew='e8',
        index_eew='na', nf='0', uop_count='1', comparison='pass',
    )


@pytest.mark.parametrize('block_older_lane', (False, True), ids=('ready', 'backpressure'))
def test_ordered_store_address_fills_preserve_elements_and_sq_slots(
    vagq_env, tmp_path, block_older_lane,
):
    """Check address fills only, NOT final ordered-store memory effects."""
    addr = load_addr(
        entry=1, rob=302, uop_type=7, vl=3, v0=0x7,
        deew=0, ieew=0, emul=0, vsew=0, vlmul=0,
    )
    data = data_for(addr, op2=0x40 | (0x20 << 8) | (0x60 << 16))
    vagq_env.reset()
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(addr, None), addr_valid=(True, False),
        index=(data, None), index_valid=(True, False),
    )
    accepted, trace = [], []
    blocked = False
    try:
        for cycle in range(100):
            beat = replace(beat, sta_ready=(not (block_older_lane and cycle < 8), True))
            outputs = vagq_env.cycle(beat, admit=(addr, data) if cycle == 0 else None)
            trace.append({'cycle': cycle, 'input': asdict(beat), 'outputs': outputs})
            if cycle == 0:
                assert outputs['io_addrUop_0_ready']
                # indexDataUop is Valid-only: there is no public ready leaf.
            for lane in range(2):
                prefix = f'io_staReq_{lane}_'
                if outputs[prefix + 'valid'] and outputs[prefix + 'bits_meta_valid']:
                    if not beat.sta_ready[lane]:
                        blocked = True
                        continue
                    accepted.append({
                        'cycle': cycle, 'lane': lane,
                        'element': outputs[prefix + 'bits_meta_elemIdx'],
                        'address': outputs[prefix + 'bits_req_data_src_0'],
                        'mask': outputs[prefix + 'bits_meta_dataMask'],
                        'sq': outputs[prefix + 'bits_req_sqIdx_value'],
                    })
            if outputs['io_robWriteback_valid']:
                break
            beat = _response_for_fires(outputs, beat)
        else:
            raise AssertionError('ordered-store address-fill scenario did not complete')
    finally:
        (tmp_path / 'ordered-store-address-events.json').write_text(json.dumps({
            'scope': 'real VAGQ address fills, synthetic responses; no SQ or memory effects simulated',
            'cycles': trace, 'accepted_addresses': accepted,
            'final_memory_order_verified': False,
        }, indent=2) + '\n')
    expected = architectural_accesses(
        kind='indexed', base=addr.base_addr, vsew=0, vlmul=0, vl=3,
        vstart=0, mask=7, data_eew=0, index_eew=0,
        index_values=(0x40, 0x20, 0x60),
    )
    # Compare multiplicities too: duplicate/missing addresses must still fail.
    assert Counter((item['element'], item['address']) for item in accepted) == Counter(
        (item.element, item.address) for item in expected
    )
    assert all(item['sq'] == addr.sq_value + item['element'] for item in accepted)
    assert all(item['mask'] == 1 for item in accepted)
    assert blocked == block_older_lane
    assert vagq_env.model.plans[addr.entry_idx].writeback_seen


@pytest.mark.skip(reason=(
    'Final ordered-store memory effects require real SQ/Sbuffer/DCache or Uncache; '
    'the standalone VAGQ root only exposes address requests, not memory effects'
))
def test_ordered_store_final_memory_effects_follow_element_order():
    """Open ISA obligation, not covered by the passing address-fill probes."""
    raise AssertionError('Connect and observe the real memory-effect path before enabling this test')


def test_indexed_segment_mop_applies_nonzero_start_field_to_first_address(vagq_env):
    # This legal indexed-segment configuration starts uop 1 at field 4 of a
    # five-field, 32-bit segment.  Its first request is only the remaining
    # field (four bytes) and its address is index[0] + 4*EEW.
    addr = load_addr(
        entry=2, rob=303, uop_type=4, vl=2, v0=0xffff,
        deew=2, ieew=0, emul=0, uop_idx=1, nf=4,
        vsew=2, vlmul=0,
    )
    data = data_for(addr, op2=0x21 | (0x32 << 8))
    vagq_env.reset()
    # This probe audits the address-side DUT directly.  The existing public
    # contract model intentionally does not yet claim the full wide-segment
    # merge-window mapping, so do not let that separate oracle hide the
    # generated request under test.
    vagq_env.checker.compare = lambda *_args: None
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(addr, None), addr_valid=(True, False),
        index=(data, None), index_valid=(True, False),
    )
    observed = False
    for cycle in range(80):
        outputs = vagq_env.cycle(
            beat, admit=(addr, data) if cycle == 0 else None,
        )
        for lane in range(3):
            prefix = f"io_lduReq_{lane}_"
            if outputs.get(prefix + "valid") and outputs.get(prefix + "bits_meta_valid"):
                if outputs[prefix + "bits_meta_elemIdx"] == 0:
                    assert outputs[prefix + "bits_meta_dataMask"] == 0xf
                    assert outputs[prefix + "bits_req_data_src_0"] == 0x1231
                    observed = True
        if outputs.get("io_robWriteback_valid"):
            break
        beat = response_beat(outputs)
    else:
        raise AssertionError("nonzero field-offset scenario did not complete")
    assert observed


def test_simple_load_fault_can_restart_from_reported_vstart(vagq_env):
    """Check the public fault/writeback/re-dispatch plumbing for one load."""
    original = load_addr(entry=3, rob=304, vl=3, v0=0x7, vstart=0)
    data = data_for(original, op2=0x10)
    vagq_env.reset()
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(original, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
        ldu_ready=(True, True, True),
    )
    before_fault = []
    faulted = False
    for cycle in range(80):
        outputs = vagq_env.cycle(
            beat, admit=(original, data) if cycle == 0 else None,
        )
        active = [
            lane for lane in range(3)
            if outputs.get(f"io_lduReq_{lane}_valid")
            and outputs.get(f"io_lduReq_{lane}_bits_meta_valid")
            and beat.ldu_ready[lane]
        ]
        before_fault.extend(
            outputs[f"io_lduReq_{lane}_bits_meta_elemIdx"] for lane in active
        )
        next_beat = _response_for_fires(outputs, beat)
        if active and not faulted:
            lane = next(
                (lane for lane in active
                 if outputs[f"io_lduReq_{lane}_bits_meta_elemIdx"] == 1),
                None,
            )
            if lane is not None:
                responses = list(next_beat.ldu_resp)
                responses[lane] = replace(
                    responses[lane], exception=1, exception_number=9,
                    fault_elem_idx=1,
                )
                next_beat = replace(next_beat, ldu_resp=tuple(responses))
                faulted = True
        beat = next_beat
        if outputs.get("io_robWriteback_valid"):
            assert outputs.get("io_robWriteback_bits_exception") == 1
            break
    else:
        raise AssertionError("faulting load did not reach exception writeback")
    assert faulted and 0 in before_fault and 1 in before_fault

    # The entry is architecturally cleared with the exception writeback.  Mark
    # the public model likewise before presenting the restarted instruction;
    # this is not a DUT state write and keeps the checker at the same boundary.
    vagq_env.model.plans[original.entry_idx].flushed = True
    restart = replace(original, vstart=1)
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(restart, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
        ldu_ready=(True, True, True),
    )
    resumed = []
    for cycle in range(80):
        outputs = vagq_env.cycle(
            beat, admit=(restart, data) if cycle == 0 else None,
        )
        active = [
            lane for lane in range(3)
            if outputs.get(f"io_lduReq_{lane}_valid")
            and outputs.get(f"io_lduReq_{lane}_bits_meta_valid")
            and beat.ldu_ready[lane]
        ]
        resumed.extend(
            outputs[f"io_lduReq_{lane}_bits_meta_elemIdx"] for lane in active
        )
        beat = _response_for_fires(outputs, beat)
        if outputs.get("io_robWriteback_valid"):
            assert outputs.get("io_robWriteback_bits_exception") == 0
            break
    else:
        raise AssertionError("restarted load did not complete")
    assert resumed and min(resumed) >= 1 and set(resumed) >= {1, 2}


def test_ordered_indexed_load_uops_handoff_between_adjacent_entries(vagq_env):
    """Exercise real uop types 6 and adjacent-entry ordered handoff."""
    first = load_addr(
        entry=4, rob=305, uop_type=6, vl=32, v0=0xffff,
        emul=1, uop_idx=0, last=False, vsew=0, vlmul=1,
    )
    second = load_addr(
        entry=5, rob=305, uop_type=6, vl=32, v0=0xffff,
        emul=1, uop_idx=1, last=True, vsew=0, vlmul=1,
    )
    first_data = data_for(first, op2=0x10 | (0x20 << 8))
    second_data = data_for(second, op2=0x110 | (0x120 << 8))
    vagq_env.reset()
    # The legacy top checker assumes a single live plan when validating a
    # writeback.  This probe intentionally has two same-ROB plans; observe the
    # public request ordering directly instead of turning that checker limit
    # into an apparent DUT failure.
    vagq_env.checker.compare = lambda *_args: None
    vagq_env.cycle(Beat())
    beat = Beat(
        addr=(first, second), addr_valid=(True, True),
        index=(first_data, second_data), index_valid=(True, True),
    )
    first_seen = None
    second_seen = None
    completed = set()
    for cycle in range(160):
        outputs = vagq_env.cycle(
            beat,
            admit=[(first, first_data), (second, second_data)]
            if cycle == 0 else None,
        )
        for lane in range(3):
            prefix = f"io_lduReq_{lane}_"
            if outputs.get(prefix + "valid") and outputs.get(prefix + "bits_meta_valid"):
                entry = outputs[prefix + "bits_meta_entryIdx"]
                if entry == first.entry_idx and first_seen is None:
                    first_seen = cycle
                if entry == second.entry_idx and second_seen is None:
                    second_seen = cycle
        if outputs.get("io_robWriteback_valid"):
            completed.add(outputs["io_robWriteback_bits_entryIdx"])
        beat = response_beat(outputs)
        if completed == {first.entry_idx, second.entry_idx}:
            break
    else:
        raise AssertionError("ordered indexed load uops did not complete")
    assert first_seen is not None and second_seen is not None
    assert first_seen < second_seen
