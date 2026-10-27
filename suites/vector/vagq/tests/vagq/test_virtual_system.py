"""Pure contract tests for the independent event-driven virtual system."""
import json

import pytest

from vagqverify.vagq.types import AddrPacket, Beat
from vagqverify.vagq.virtual_coverage import VIRTUAL_COVERAGE
from vagqverify.vagq.virtual_system import (
    EventScheduler,
    PHASE_RESPONSE,
    PHASE_RETIRE,
    VirtualRequest,
    VirtualSystem,
    VirtualSystemConfig,
)


pytestmark = pytest.mark.toffee_functional_coverage(False)


def _request(*, kind='load', lane=0, cycle=0, entry=0, rob=10, element=0,
             byte=0, address=0x1000):
    return VirtualRequest(
        kind=kind,
        lane=lane,
        cycle=cycle,
        entry=entry,
        rob=rob,
        element=element,
        byte=byte,
        mask=1,
        address=address,
        is_load=kind == 'load',
    )


def test_event_scheduler_orders_cycle_phase_and_sequence_deterministically():
    scheduler = EventScheduler()
    scheduler.schedule(2, PHASE_RETIRE, 'retire')
    scheduler.schedule(2, PHASE_RESPONSE, 'response-a')
    scheduler.schedule(2, PHASE_RESPONSE, 'response-b')
    due = scheduler.due(0)
    assert due == ()
    due = scheduler.due(1)
    assert due == ()
    due = scheduler.due(2)
    assert [event.kind for event in due] == [
        'response-a', 'response-b', 'retire',
    ]
    assert [event.sequence for event in due] == [1, 2, 0]


def test_virtual_lsq_retries_nack_reorders_responses_and_keeps_identity():
    system = VirtualSystem(VirtualSystemConfig(
        response_latency=1,
        nack_once=True,
        response_extra_delay=((0, 2), (1, 0)),
    ))
    first = _request(entry=0, rob=10, element=0)
    second = _request(entry=1, rob=11, element=1, address=0x1020)
    system.lsq.accept(first)
    system.lsq.accept(second)

    due_cycle_1 = system.begin_cycle(1)
    assert due_cycle_1['ldu'][0].valid is True
    assert due_cycle_1['ldu'][0].entry_idx == 1
    assert due_cycle_1['ldu'][0].is_nack == 0
    assert system.begin_cycle(2)['ldu'][0].valid is False

    due_cycle_3 = system.begin_cycle(3)
    assert due_cycle_3['ldu'][0].entry_idx == 0
    assert due_cycle_3['ldu'][0].is_nack == 1

    retry = _request(cycle=4, entry=0, rob=10, element=0)
    system.lsq.accept(retry)
    due_cycle_5 = system.begin_cycle(5)
    assert due_cycle_5['ldu'][0].valid is False
    due_cycle_7 = system.begin_cycle(7)
    assert due_cycle_7['ldu'][0].valid is True
    assert due_cycle_7['ldu'][0].entry_idx == 0
    assert due_cycle_7['ldu'][0].is_nack == 0
    assert [item['entry'] for item in system.lsq.response_records] == [1, 0, 0]


def test_virtual_lsq_can_deliver_a_late_response_after_virtual_flush():
    system = VirtualSystem(VirtualSystemConfig(
        response_latency=2,
        deliver_late_response=True,
    ))
    request = _request(rob=20, entry=2)
    system.lsq.accept(request)
    system.lsq.flush(rob_value=10, cycle=1)
    response_inputs = system.begin_cycle(2)
    assert response_inputs['ldu'][0].valid is True
    assert system.lsq.response_records[-1]['late'] is True
    assert system.lsq.late_response_count == 1


def test_virtual_vrf_rob_and_voq_contracts_are_serializable():
    system = VirtualSystem(VirtualSystemConfig(
        response_latency=1,
        vrf_latency=2,
        ordered_sq=True,
    ))
    addr = AddrPacket(entry_idx=0, rob_value=30, uop_idx=0, last_uop=1)
    system.admit(addr, cycle=0)
    system.vrf.set_old_data(addr.entry_idx, 0xAA)
    system.vrf.observe_read({
        'io_vrfReadReq_valid': 1,
        'io_vrfReadReq_bits_entryIdx': 0,
        'io_vrfReadReq_bits_robIdx_value': 30,
    }, cycle=0)
    assert system.begin_cycle(1)['vrf'].valid is False
    assert system.begin_cycle(2)['vrf'].data == 0xAA

    system.rob.writeback({
        'io_robWriteback_valid': 1,
        'io_robWriteback_bits_entryIdx': 0,
        'io_robWriteback_bits_robIdx_value': 30,
        'io_robWriteback_bits_exception': 0,
        'io_robWriteback_bits_faultVstart': 0,
    }, cycle=3)
    system.begin_cycle(4)
    assert system.rob.retires == [{
        'cycle': 4, 'entry': 0, 'rob': 30, 'exception': False,
    }]

    outputs = {
        'io_staReq_0_valid': 1,
        'io_staReq_0_bits_meta_valid': 1,
        'io_staReq_0_bits_meta_elemIdx': 0,
        'io_staReq_0_bits_meta_entryIdx': 0,
        'io_staReq_0_bits_meta_byteOffset': 0,
        'io_staReq_0_bits_meta_dataMask': 1,
        'io_staReq_0_bits_req_robIdx_value': 30,
        'io_staReq_0_bits_req_data_src_0': 0x1000,
        'io_staReq_1_valid': 0,
    }
    refined = system.refine_ready(outputs, Beat(sta_ready=(True, True)))
    assert refined.sta_ready == (True, False)
    system.observe_cycle(outputs, refined, cycle=5)
    assert system.voq.accepted[0]['element'] == 0

    encoded = json.dumps(system.to_dict(), sort_keys=True)
    assert 'virtual_contract_pass' in encoded
    assert system.to_dict()['virtual_contract_pass'] is True


def test_virtual_voq_records_a_contract_violation_without_hiding_scope():
    system = VirtualSystem(VirtualSystemConfig(ordered_sq=True))
    system.voq.observe_accepted({
        'entry': 0, 'element': 1, 'address': 0x1001,
    })
    assert system.voq.errors
    VIRTUAL_COVERAGE.sample(
        scenario='ordered-sq',
        virtual_outcome='contract-violation',
        isa_result='counterexample',
        scope='public-boundary-contract',
    )
    VIRTUAL_COVERAGE.sample(
        scenario='late-response-redirect',
        virtual_outcome='contract-pass',
        isa_result='boundary',
        scope='whole-chip-unobservable',
    )
