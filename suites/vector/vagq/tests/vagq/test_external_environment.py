"""Real-DUT runs with a modeled public LSQ/SQ/VRF/ROB environment."""
from dataclasses import replace
from pathlib import Path

import pytest

from suites.vector.vagq.vagq.external_env import PublicVAGQEnvironment, Scenario
from suites.vector.vagq.vagq.types import AddrPacket, DataPacket


pytestmark = [
    pytest.mark.vagq_isa_audit,
    pytest.mark.toffee_functional_coverage(False),
]


ROOT = Path(__file__).resolve().parents[2]
LOG_ROOT = ROOT / 'results/vagq-environment-20261017-v2/stimulus-logs'


def _addr(*, entry, rob, uop_type, vl=1, vstart=0, v0=1,
          deew=0, ieew=0, emul=0, nf=0, vsew=None, vlmul=0,
          uop_idx=0, last_uop=1, base=None):
    return AddrPacket(
        entry_idx=entry,
        uop_type=uop_type,
        rob_value=rob,
        pdest=3 + entry,
        psrc2=4 + entry,
        base_addr=0x1000 + entry * 0x100 if base is None else base,
        v0_byte_mask=v0,
        deew=deew,
        ieew=ieew,
        emul=emul,
        vl=vl,
        vstart=vstart,
        uop_idx=uop_idx,
        last_uop=last_uop,
        nf=nf,
        vsew=deew if vsew is None else vsew,
        vlmul=vlmul,
    )


def _data(addr, op2):
    return DataPacket(
        entry_idx=addr.entry_idx,
        rob_value=addr.rob_value,
        op2_data=op2,
    )


def test_environment_completes_normal_strided_load_with_latency_nack_and_hold(vagq_env):
    addr = _addr(entry=0, rob=810, uop_type=0, vl=2, v0=0x3)
    data = _data(addr, 8)
    scenario = Scenario(
        name='normal-strided-load',
        packets=((addr, data),),
        response_latency=2,
        ldu_hold_cycles=3,
        nack_once=True,
        expected_writebacks=1,
    )
    log = PublicVAGQEnvironment(log_root=LOG_ROOT).run(vagq_env, scenario)
    assert log.completed and not log.timed_out
    assert log.accepted_addresses
    assert log.responses
    assert any(item['nack'] for item in log.responses)


def test_environment_runs_fractional_lmul_and_keeps_extra_work_evidence(vagq_env):
    addr = _addr(
        entry=0, rob=820, uop_type=0, vl=2, v0=0x3,
        deew=0, ieew=0, emul=5, vsew=0, vlmul=5,
    )
    data = _data(addr, 0x20)
    scenario = Scenario(
        name='fractional-lmul-mf8',
        packets=((addr, data),),
        response_latency=1,
        expected_writebacks=1,
    )
    log = PublicVAGQEnvironment(log_root=LOG_ROOT).run(vagq_env, scenario)
    assert log.completed and not log.timed_out
    assert log.extra_active_elements or log.extra_empty_masks


def test_environment_runs_wide_segment_and_records_duplicate_memory_bytes(vagq_env):
    indices = (0x20, 0x40, 0x60, 0x80)
    index_data = sum(value << (8 * index) for index, value in enumerate(indices))
    packets = []
    for uop_idx in range(5):
        addr = _addr(
            entry=uop_idx,
            rob=830,
            uop_type=4,
            vl=4,
            v0=0xffff,
            deew=2,
            ieew=0,
            emul=0,
            nf=4,
            vsew=2,
            vlmul=0,
            uop_idx=uop_idx,
            last_uop=int(uop_idx == 4),
            base=0x9000,
        )
        packets.append((addr, _data(addr, index_data)))
    scenario = Scenario(
        name='wide-segment-mop-overlap',
        packets=tuple(packets),
        response_latency=2,
        expected_writebacks=5,
        max_cycles=500,
    )
    log = PublicVAGQEnvironment(log_root=LOG_ROOT).run(vagq_env, scenario)
    assert log.completed and not log.timed_out
    assert log.duplicate_memory_bytes


def test_environment_sq_serializes_ordered_indexed_store_after_public_issue(vagq_env):
    addr = _addr(
        entry=1, rob=840, uop_type=7, vl=3, v0=0x7,
        deew=0, ieew=0, emul=0, vsew=0, vlmul=0,
    )
    data = _data(addr, 0x40 | (0x20 << 8) | (0x60 << 16))
    scenario = Scenario(
        name='ordered-indexed-store-sq-serialized',
        packets=((addr, data),),
        response_latency=2,
        ordered_sq=True,
        ordered_first_element=0,
        expected_writebacks=1,
        max_cycles=300,
    )
    log = PublicVAGQEnvironment(log_root=LOG_ROOT).run(vagq_env, scenario)
    assert log.completed and not log.timed_out
    assert log.presented_store_order_violation
    assert log.sq_order_is_monotonic
    assert log.sq_accepted_elements == sorted(log.sq_accepted_elements)


def test_environment_delivers_late_response_after_redirect(vagq_env):
    addr = _addr(entry=2, rob=850, uop_type=0, vl=1, v0=0x1)
    data = _data(addr, 8)
    scenario = Scenario(
        name='late-response-after-redirect',
        packets=((addr, data),),
        response_latency=5,
        redirect_cycle=4,
        redirect_rob_value=850,
        expected_writebacks=0,
        min_cycles=16,
        max_cycles=80,
    )
    log = PublicVAGQEnvironment(log_root=LOG_ROOT).run(vagq_env, scenario)
    assert log.completed and not log.timed_out
    assert log.responses
    assert not log.writebacks


@pytest.mark.parametrize('fault_element', (0, 1, 2))
def test_environment_injects_precise_load_fault_at_each_active_element(
    vagq_env, fault_element,
):
    addr = _addr(entry=3, rob=860 + fault_element, uop_type=0, vl=3, v0=0x7)
    data = _data(addr, 8)
    scenario = Scenario(
        name=f'load-fault-element-{fault_element}',
        packets=((addr, data),),
        response_latency=2,
        fault_kind='load',
        fault_element=fault_element,
        expected_writebacks=1,
        max_cycles=120,
    )
    log = PublicVAGQEnvironment(log_root=LOG_ROOT).run(vagq_env, scenario)
    assert log.completed and not log.timed_out
    assert any(item['exception'] for item in log.responses)
    assert any(item['exception'] for item in log.writebacks)


def test_environment_exercises_eight_entry_admission_and_reuse_window(vagq_env):
    packets = []
    for entry in range(8):
        addr = _addr(entry=entry, rob=880 + entry, uop_type=0, vl=1, v0=0x1)
        packets.append((addr, _data(addr, 8)))
    scenario = Scenario(
        name='eight-entry-admission-window',
        packets=tuple(packets),
        response_latency=3,
        expected_writebacks=8,
        max_cycles=400,
    )
    log = PublicVAGQEnvironment(log_root=LOG_ROOT).run(vagq_env, scenario)
    assert log.completed and not log.timed_out
    assert len(log.accepted_addresses) == 8
    assert len(log.writebacks) == 8


def test_environment_exercises_ordered_load_entry_wraparound(vagq_env):
    first = _addr(
        entry=7, rob=900, uop_type=6, vl=2, v0=0x3,
        deew=0, ieew=0, emul=0, vsew=0, vlmul=0,
        uop_idx=0, last_uop=0, base=0xA000,
    )
    second = replace(first, entry_idx=0, uop_idx=1, last_uop=1)
    packets = (
        (first, _data(first, 0x20 | (0x40 << 8))),
        (second, _data(second, 0x60 | (0x80 << 8))),
    )
    scenario = Scenario(
        name='ordered-load-entry-wraparound',
        packets=packets,
        response_latency=1,
        expected_writebacks=2,
        max_cycles=180,
    )
    log = PublicVAGQEnvironment(log_root=LOG_ROOT).run(vagq_env, scenario)
    assert log.completed and not log.timed_out
    assert len(log.writebacks) == 2


def test_environment_retries_indexed_store_while_std_is_busy(vagq_env):
    addr = _addr(
        entry=4, rob=920, uop_type=5, vl=3, v0=0x7,
        deew=1, ieew=0, emul=0, vsew=1, vlmul=0,
    )
    data = _data(addr, 0x20 | (0x40 << 8) | (0x60 << 16))
    scenario = Scenario(
        name='indexed-store-nack-std-busy',
        packets=((addr, data),),
        response_latency=3,
        sta_hold_cycles=2,
        nack_once=True,
        std_busy_cycles=frozenset(range(8, 12)),
        vrf_data=0x0123456789ABCDEFFEDCBA9876543210,
        expected_writebacks=1,
        max_cycles=180,
    )
    log = PublicVAGQEnvironment(log_root=LOG_ROOT).run(vagq_env, scenario)
    assert log.completed and not log.timed_out
    assert any(item['nack'] for item in log.responses)
    assert log.std_outputs
    assert log.vrf_reads
    assert log.writebacks


def test_environment_consumes_empty_markers_under_backpressure(vagq_env):
    addr = _addr(entry=5, rob=930, uop_type=0, vl=3, vstart=1, v0=0x5)
    data = _data(addr, 8)
    scenario = Scenario(
        name='empty-marker-backpressure',
        packets=((addr, data),),
        response_latency=2,
        empty_hold_cycles=6,
        expected_writebacks=1,
        max_cycles=180,
    )
    log = PublicVAGQEnvironment(log_root=LOG_ROOT).run(vagq_env, scenario)
    assert log.completed and not log.timed_out
    assert log.accepted_empty_requests
    assert log.responses
    assert log.writebacks
