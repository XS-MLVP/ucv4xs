"""Real generated-DUT runs backed by independent virtual system contracts."""
from pathlib import Path

import pytest

from vagqverify.vagq.external_env import PublicVAGQEnvironment, Scenario
from vagqverify.vagq.types import AddrPacket, DataPacket
from vagqverify.vagq.virtual_coverage import VIRTUAL_COVERAGE
from vagqverify.vagq.virtual_system import VirtualSystem, VirtualSystemConfig


pytestmark = [
    pytest.mark.vagq_isa_audit,
    pytest.mark.toffee_functional_coverage(False),
]


ROOT = Path(__file__).resolve().parents[2]
LOG_ROOT = ROOT / 'results/vagq-virtual-system-20261017-v1/stimulus-logs'


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
        vma=0,
        vta=0,
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


def _run(vagq_env, scenario, config):
    system = VirtualSystem(config)
    log = PublicVAGQEnvironment(log_root=LOG_ROOT).run(
        vagq_env, scenario, virtual_system=system,
    )
    assert log.completed and not log.timed_out
    assert log.virtual_contract
    return log


def _sample_contract(*, scenario, isa_result='pass-local', contract_pass=True,
                     scope='public-boundary-contract'):
    VIRTUAL_COVERAGE.sample(
        scenario=scenario,
        virtual_outcome='contract-pass' if contract_pass else 'contract-violation',
        isa_result=isa_result,
        scope=scope,
    )


def test_virtual_system_accepts_out_of_order_load_responses(vagq_env):
    addr = _addr(entry=0, rob=1100, uop_type=0, vl=2, v0=0x3)
    scenario = Scenario(
        name='virtual-out-of-order-load-response',
        packets=((addr, _data(addr, 8)),),
        response_latency=1,
        expected_writebacks=1,
        max_cycles=100,
    )
    log = _run(
        vagq_env,
        scenario,
        VirtualSystemConfig(
            response_latency=1,
            response_extra_delay=((0, 3), (1, 0)),
            vrf_data=0xFFEEDDCCBBAA99887766554433221100,
        ),
    )
    responses = log.virtual_contract['lsq']['responses']
    assert [item['element'] for item in responses[:2]] == [1, 0]
    assert log.virtual_contract['virtual_contract_pass']
    _sample_contract(scenario='response-reorder')


def test_virtual_system_delivers_late_response_after_redirect(vagq_env):
    addr = _addr(entry=1, rob=1110, uop_type=0, vl=1, v0=1)
    scenario = Scenario(
        name='virtual-late-response-after-redirect',
        packets=((addr, _data(addr, 8)),),
        response_latency=4,
        redirect_cycle=4,
        redirect_rob_value=1110,
        expected_writebacks=0,
        min_cycles=12,
        max_cycles=80,
    )
    log = _run(
        vagq_env,
        scenario,
        VirtualSystemConfig(response_latency=4, deliver_late_response=True),
    )
    assert log.virtual_contract['lsq']['late_response_count'] == 1
    assert not log.writebacks
    assert log.virtual_contract['virtual_contract_pass']
    _sample_contract(scenario='late-response-redirect', isa_result='boundary')


def test_virtual_system_checks_vrf_old_vd_and_merge_write(vagq_env):
    addr = _addr(entry=2, rob=1120, uop_type=0, vl=1, v0=1)
    scenario = Scenario(
        name='virtual-vrf-old-vd-merge',
        packets=((addr, _data(addr, 8)),),
        response_latency=1,
        expected_writebacks=1,
        max_cycles=100,
    )
    log = _run(
        vagq_env,
        scenario,
        VirtualSystemConfig(
            response_latency=1,
            vrf_latency=2,
            vrf_data=0x0123456789ABCDEFFEDCBA9876543210,
        ),
    )
    contract = log.virtual_contract
    assert contract['vrf']['reads']
    assert contract['vrf']['writes']
    assert all(item['mask'] for item in contract['vrf']['writes'])
    assert contract['virtual_contract_pass']
    _sample_contract(scenario='vrf-merge')


def test_virtual_system_tracks_precise_fault_then_restart(vagq_env):
    original = _addr(entry=6, rob=1150, uop_type=0, vl=2, v0=0x3)
    config = VirtualSystemConfig(
        response_latency=1,
        fault_kind='load',
        fault_element=1,
    )
    system = VirtualSystem(config)
    fault_run = PublicVAGQEnvironment(log_root=LOG_ROOT).run(
        vagq_env,
        Scenario(
            name='virtual-precise-load-fault',
            packets=((original, _data(original, 8)),),
            response_latency=1,
            fault_kind='load',
            fault_element=1,
            expected_writebacks=1,
            max_cycles=140,
        ),
        virtual_system=system,
    )
    assert fault_run.completed and not fault_run.timed_out
    assert fault_run.writebacks[0]['exception'] == 1
    assert fault_run.virtual_contract['rob']['writebacks'][0]['fault_vstart'] == 1
    assert fault_run.virtual_contract['virtual_contract_pass']
    _sample_contract(scenario='precise-restart')

    restart = _addr(
        entry=6, rob=1150, uop_type=0, vl=2, vstart=1, v0=0x3,
    )
    restart_run = PublicVAGQEnvironment(log_root=LOG_ROOT).run(
        vagq_env,
        Scenario(
            name='virtual-precise-load-restart',
            packets=((restart, _data(restart, 8)),),
            response_latency=1,
            expected_writebacks=1,
            max_cycles=140,
        ),
        virtual_system=system,
        reset_virtual=False,
    )
    assert restart_run.completed and not restart_run.timed_out
    assert restart_run.writebacks[0]['exception'] == 0
    assert restart_run.virtual_contract['virtual_contract_pass']
    restart_events = [
        event for event in restart_run.virtual_contract['scheduler_events']
        if event.get('action') == 'restart-admission'
    ]
    assert restart_events


def test_virtual_system_separates_ordered_sq_acceptance_from_public_presentation(
    vagq_env,
):
    addr = _addr(entry=3, rob=1130, uop_type=7, vl=3, v0=0x7)
    scenario = Scenario(
        name='virtual-ordered-store-three-orders',
        packets=((addr, _data(addr, 0x40 | (0x20 << 8) | (0x60 << 16))),),
        response_latency=2,
        ordered_sq=True,
        ordered_first_element=0,
        expected_writebacks=1,
        max_cycles=180,
    )
    log = _run(
        vagq_env,
        scenario,
        VirtualSystemConfig(
            response_latency=2,
            ordered_sq=True,
            ordered_first_element=0,
            vrf_latency=2,
            vrf_data=0x0123456789ABCDEFFEDCBA9876543210,
        ),
    )
    contract = log.virtual_contract
    assert contract['voq']['accepted_elements'] == sorted(
        contract['voq']['accepted_elements']
    )
    assert contract['voq']['memory_effect_elements'] == sorted(
        contract['voq']['memory_effect_elements']
    )
    assert log.presented_store_order_violation
    assert contract['virtual_contract_pass']
    _sample_contract(scenario='ordered-sq', isa_result='counterexample')


def test_virtual_system_tracks_eight_entry_rob_reuse(vagq_env):
    packets = []
    for entry in range(8):
        addr = _addr(entry=entry, rob=1140 + entry, uop_type=0, v0=1)
        packets.append((addr, _data(addr, 8)))
    scenario = Scenario(
        name='virtual-eight-entry-rob-reuse',
        packets=tuple(packets),
        response_latency=3,
        expected_writebacks=8,
        max_cycles=300,
    )
    log = _run(
        vagq_env,
        scenario,
        VirtualSystemConfig(response_latency=3),
    )
    contract = log.virtual_contract
    assert len(contract['rob']['writebacks']) == 8
    assert len(contract['rob']['retires']) == 8
    assert contract['virtual_contract_pass']
    _sample_contract(scenario='capacity-reuse')
