"""Binding selftest: public snapshot decode and response construction.

These checks isolate the environment seam itself.  They use a complete
synthetic sample of every leaf registered in the generated schema (not a DUT)
and therefore never earn functional credit.
"""
import dataclasses
from types import SimpleNamespace

import pytest

from suites.vector.vagq.testbenches.vagq.env import Env
from suites.vector.vagq.testbenches.vagq.env.driver import response_beat
from suites.vector.vagq.testbenches.vagq.env.probe import PRUNED_OUTPUT_REASONS
from suites.vector.vagq.testbenches.vagq.env.probe import decode
from suites.vector.vagq.testbenches.vagq.env.schema import OUTPUT_NAMES
from suites.vector.vagq.testbenches.vagq.model import IntegrationModel
from suites.vector.vagq.testbenches.vagq.transactions import ActiveRequest
from suites.vector.vagq.testbenches.vagq.transactions import AddrPacket
from suites.vector.vagq.testbenches.vagq.transactions import Beat
from suites.vector.vagq.testbenches.vagq.transactions import DataPacket
from suites.vector.vagq.testbenches.vagq.transactions import Observation

pytestmark = [
    pytest.mark.toffee_functional_coverage(False),
    pytest.mark.selftest,
]


def complete_sample(**values):
    """Every schema-registered output leaf present; unknown keys rejected."""
    sample = {name: 0 for name in OUTPUT_NAMES}
    for suffix, value in values.items():
        name = 'io_' + suffix
        assert name in sample, name
        sample[name] = value
    return sample


def test_decode_maps_public_leaves_to_one_typed_snapshot():
    observation = decode(complete_sample(**{
        'addrUop_0_ready': 1,
        'lduReq_0_valid': 1,
        'lduReq_0_bits_meta_valid': 1,
        'lduReq_0_bits_meta_entryIdx': 5,
        'lduReq_0_bits_meta_byteOffset': 3,
        'lduReq_0_bits_meta_elemIdx': 9,
        'lduReq_0_bits_meta_dataMask': 0xF,
        'lduReq_0_bits_req_data_src_0': 0x1234,
        'lduReq_1_bits_req_data_src_0': 0xBAD,
        'lsqEmptyReq_1_valid': 1,
        'lsqEmptyReq_1_bits_issueMask': 0x100,
        'robWriteback_valid': 1,
        'robWriteback_bits_entryIdx': 5,
        'robWriteback_bits_robIdx_value': 64,
    }), cycle=7)
    assert observation.cycle == 7
    assert observation.addr_ready == (True, False)
    assert observation.loads[0] == ActiveRequest(
        group='load', lane=0, valid=True, meta_valid=True,
        entry_idx=5, byte_offset=3, elem_idx=9, data_mask=0xF,
        vaddr=0x1234,
    )
    # A stale payload on a lane without valid must not become a request.
    assert observation.loads[1].valid is False
    assert observation.empty_requests[1].valid is True
    assert observation.empty_requests[1].issue_mask == 0x100
    assert observation.writeback.entry_idx == 5
    assert observation.writeback.rob_value == 64
    # A pruned leaf is the documented interface constant, not an observation.
    assert 'io_staReq_0_bits_req_data_pc' in PRUNED_OUTPUT_REASONS
    assert observation.stores[0].pc == 0


@pytest.mark.parametrize('missing', (
    'io_robWriteback_bits_entryIdx',
    'io_lduReq_0_bits_meta_elemIdx',
    'io_vrfReadReq_bits_robIdx_value',
))
def test_missing_required_leaf_is_rejected_not_zero_filled(missing):
    sample = complete_sample(**{
        'lduReq_0_valid': 1,
        'lduReq_0_bits_meta_valid': 1,
        'lduReq_0_bits_meta_entryIdx': 5,
        'robWriteback_valid': 1,
        'robWriteback_bits_entryIdx': 5,
        'robWriteback_bits_robIdx_value': 64,
        'vrfReadReq_valid': 1,
        'vrfReadReq_bits_entryIdx': 0,
        'vrfReadReq_bits_robIdx_value': 9,
    })
    reference = decode(sample)
    del sample[missing]
    with pytest.raises(ValueError, match='missing required public output sample'):
        decode(sample)
    # The intact sample really carried the identity that would be lost.
    if missing.startswith('io_robWriteback'):
        assert (reference.writeback.valid, reference.writeback.entry_idx) == (True, 5)


def test_response_beat_requires_current_cycle_handshake_evidence():
    observation = decode(complete_sample(**{
        'lduReq_0_valid': 1,
        'lduReq_0_bits_meta_valid': 1,
        'lduReq_0_bits_meta_entryIdx': 2,
        'lduReq_0_bits_meta_byteOffset': 4,
        'lduReq_0_bits_meta_dataMask': 0xF,
        'lduReq_1_valid': 1,
        'lduReq_1_bits_meta_valid': 0,
        'lduReq_1_bits_meta_entryIdx': 3,
        'lsqEmptyReq_0_valid': 1,
        'lsqEmptyReq_0_bits_entryIdx': 1,
        'lsqEmptyReq_0_bits_issueMask': 0x20,
        'vrfReadReq_valid': 1,
        'vrfReadReq_bits_entryIdx': 2,
        'vrfReadReq_bits_robIdx_value': 9,
    }))
    # No handshake evidence at all: nothing may be acknowledged.
    unevidenced = response_beat(observation)
    assert not any(response.valid for response in unevidenced.ldu_resp)
    assert not any(response.valid for response in unevidenced.empty_resp)

    ready = Beat(ldu_ready=(True, True, True), empty_ready=(True, True))
    beat = response_beat(observation, beat=ready, data=0xAA)
    assert beat.ldu_resp[0].valid and beat.ldu_resp[0].entry_idx == 2
    assert beat.ldu_resp[0].issue_mask == 1 << 4
    # A valid lane without metadata is a native issue payload, not VAGQ work.
    assert beat.ldu_resp[1].valid is False
    assert beat.ldu_resp[2].valid is False
    assert beat.empty_resp[0].valid and beat.empty_resp[0].issue_mask == 0x20
    assert beat.vrf_resp.valid and beat.vrf_resp.data == 0xAA
    assert beat.vrf_resp.rob_value == 9

    # Same observation, but lane 0 is backpressured this cycle: a merely
    # offered request must not be acknowledged.
    gated = response_beat(observation, beat=Beat(
        ldu_ready=(False, True, True),
        sta_ready=(True, True),
        empty_ready=(False, True),
    ))
    assert gated.ldu_resp[0].valid is False
    assert gated.empty_resp[0].valid is False
    assert gated.vrf_resp.valid is True

    # Ready carried by the observation is equivalent same-cycle evidence.
    sample = complete_sample(**{
        'lduReq_0_valid': 1,
        'lduReq_0_bits_meta_valid': 1,
        'lduReq_0_bits_meta_entryIdx': 2,
        'lduReq_0_bits_meta_byteOffset': 4,
    })
    captured = decode(sample, cycle=4, beat=Beat(ldu_ready=(True, True, True)))
    carried = response_beat(captured)
    assert carried.ldu_resp[0].valid and carried.ldu_resp[0].entry_idx == 2
    same = response_beat(captured, beat=Beat(ldu_ready=(True, True, True)))
    assert same.ldu_resp[0].valid is True
    backpressured = decode(sample, cycle=5, beat=Beat(ldu_ready=(False, True, True)))
    assert response_beat(backpressured).ldu_resp[0].valid is False
    # Known sampled evidence must not be overridden by a conflicting beat.
    with pytest.raises(ValueError, match='conflicting ldu_ready evidence'):
        response_beat(backpressured, beat=Beat())
    blocked_snapshot = decode(
        sample, cycle=6, beat=Beat(ldu_ready=(False, False, False)))
    with pytest.raises(ValueError, match='conflicting ldu_ready evidence'):
        response_beat(blocked_snapshot, beat=Beat(ldu_ready=(True, True, True)))
    # One positive source remains sufficient; no source still means zero ACK.
    assert response_beat(blocked_snapshot).ldu_resp[0].valid is False
    assert response_beat(observation, beat=Beat()).ldu_resp[0].valid is True
    assert response_beat(observation).ldu_resp[0].valid is False

    # `base` is next-cycle input only.  A blocked current cycle must not borrow
    # the next cycle's released ready to acknowledge this cycle's request.
    released_next = Beat(ldu_ready=(True, True, True),
                         sta_ready=(True, True), empty_ready=(True, True))
    blocked_with_next = response_beat(blocked_snapshot, base=released_next)
    assert blocked_with_next.ldu_resp[0].valid is False
    assert blocked_with_next.ldu_ready == (True, True, True)
    unevidenced_with_next = response_beat(observation, base=released_next)
    assert unevidenced_with_next.ldu_resp[0].valid is False
    # The same next-cycle release does not change an already-known ACK.
    acked_with_next = response_beat(captured, base=released_next)
    assert acked_with_next.ldu_resp[0].valid is True


def test_present_records_real_sample_cycle_and_reset_restarts_identity():
    env = Env.__new__(Env)
    env.driver = SimpleNamespace(drive=lambda beat: None, tick=lambda: None)
    env.sample = lambda: complete_sample()
    assert [env.present(Beat()).cycle for _ in range(2)] == [0, 1]
    env.driver = SimpleNamespace(
        reset_dut=lambda: None, drive=lambda beat: None, tick=lambda: None)
    env.model = IntegrationModel()
    env.coverage = SimpleNamespace(reset=lambda: None)
    env.reset()
    assert env.present(Beat()).cycle == 0


def _restart_env(addr, data):
    env = Env.__new__(Env)
    env.model = IntegrationModel()
    env._writebacks = {}
    env._sample_cycle = 0
    env.sample = lambda: complete_sample()
    env.admit(addr, data)
    return env


def _exception_writeback(**changes):
    fields = {
        'robWriteback_valid': 1,
        'robWriteback_bits_entryIdx': 0,
        'robWriteback_bits_robIdx_value': 7,
        'robWriteback_bits_exception': 1,
        'robWriteback_bits_uopIdx': 0,
    }
    fields.update(changes)
    return complete_sample(**fields)


def test_restart_requires_observed_exception_writeback_for_the_same_attempt():
    addr = AddrPacket(entry_idx=0, rob_value=7, v0_byte_mask=1, vl=1)
    data = DataPacket(entry_idx=0, rob_value=7)

    env = _restart_env(addr, data)
    with pytest.raises(AssertionError, match='requires an observed writeback'):
        env.restart_entry(0)
    # A successful writeback cannot be relabelled as a fault.
    env._observe(complete_sample(**{
        'robWriteback_valid': 1,
        'robWriteback_bits_entryIdx': 0,
        'robWriteback_bits_robIdx_value': 7,
    }), Beat())
    with pytest.raises(AssertionError, match='requires an exception writeback'):
        env.restart_entry(0)

    # Wrong identity must fail explicitly and must not be credited to the plan.
    for counterexample in (
        {'robWriteback_bits_robIdx_value': 8},
        {'robWriteback_bits_robIdx_flag': 1},
        {'robWriteback_bits_uopIdx': 1},
    ):
        wrong = _restart_env(addr, data)
        with pytest.raises(AssertionError, match='writeback identity does not belong'):
            wrong._observe(_exception_writeback(**counterexample), Beat())
        with pytest.raises(AssertionError, match='requires an observed writeback'):
            wrong.restart_entry(0)

    # Legal fault restart: the exception writeback carries the same attempt.
    legal = _restart_env(addr, data)
    legal._observe(_exception_writeback(), Beat())
    legal.restart_entry(0)
    with pytest.raises(AssertionError, match='already restarted'):
        legal.restart_entry(0)
    legal.admit(addr, data)
    with pytest.raises(AssertionError, match='requires an observed writeback'):
        legal.restart_entry(0)
    # Two completions cannot authorize one restart.
    duplicated = _restart_env(addr, data)
    duplicated._observe(_exception_writeback(), Beat())
    duplicated._observe(_exception_writeback(), Beat())
    with pytest.raises(AssertionError, match='duplicated completion'):
        duplicated.restart_entry(0)


def test_observation_copies_caller_sequences_and_checks_lane_shape():
    slots = [ActiveRequest('load', lane) for lane in range(3)]
    observation = Observation(loads=slots)
    slots[0] = ActiveRequest('load', 0, valid=True, meta_valid=True)
    assert observation.loads[0].valid is False
    assert isinstance(observation.loads, tuple)
    with pytest.raises(ValueError, match='exactly 3 lanes'):
        Observation(loads=slots[:2])
    wrong_lane = list(observation.loads)
    wrong_lane[1] = ActiveRequest('load', 2)
    with pytest.raises(ValueError, match='identifies lane 2'):
        Observation(loads=wrong_lane)
    wrong_group = list(observation.loads)
    wrong_group[0] = ActiveRequest('store', 0)
    with pytest.raises(ValueError, match='identifies group'):
        Observation(loads=wrong_group)


def test_observation_and_requests_are_immutable_snapshots():
    observation = decode(complete_sample())
    with pytest.raises(dataclasses.FrozenInstanceError):
        observation.cycle = 3
    with pytest.raises(dataclasses.FrozenInstanceError):
        observation.loads[0].entry_idx = 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        Beat().ldu_ready = (False, False, False)
