"""Regression controls for the typed expectation channel (no native DUT).

The original physical-field expectations are the authoritative record; these
checks verify that the typed translation does not silently drop them.  They
deliberately use wrong sampled pin values to prove that a dropped field would
have been a false PASS.
"""
from types import SimpleNamespace

import pytest

from suites.memblock.lsq.testbenches.psq.env.ports import Ports as PsqPorts
from suites.memblock.lsq.testbenches.psq.env import PsqEnv
from suites.memblock.lsq.testbenches.psq.transactions import PublicResponse
from suites.memblock.lsq.testbenches.shared.transactions import ForwardExpectation
from suites.memblock.lsq.testbenches.shared.transactions import UNSET
from suites.memblock.lsq.testbenches.store_queue.env.ports import Ports as SqPorts
from suites.memblock.lsq.testbenches.store_queue.env import StoreQueueEnv
from suites.memblock.lsq.testbenches.store_queue.transactions import Observation as SqObservation


def _psq():
    return PsqPorts.__new__(PsqPorts)


def _sq():
    return SqPorts.__new__(SqPorts)


def _compare(pins, expected):
    return [key for key, value in expected.items() if pins[key] != value]


@pytest.mark.parametrize("ports, observation_class, prefix", (
        (_psq, PublicResponse, "io_forward_0_s2Resp_"),
        (_sq, SqObservation, "io_forward_0_s2Resp_")))
def test_forward_expectation_is_consumed_for_every_lane(ports, observation_class, prefix):
    expected = ports().expected(observation_class(
        forward=(ForwardExpectation(valid=1, forward_mask=0x00FF, forward_data=0xA5),) * 3))
    assert expected[prefix + "valid"] == 1
    assert expected[prefix + "bits_forwardMask_0"] == 1
    assert expected[prefix + "bits_forwardMask_8"] == 0
    assert expected[prefix + "bits_forwardData_0"] == 0xA5
    assert prefix + "bits_forwardData_8" not in expected
    # Wrong actual data (old behaviour of an empty translation) must fail.
    pins = {key: value for key, value in expected.items()}
    pins[prefix + "bits_forwardData_0"] ^= 0x01
    assert _compare(pins, expected) == [prefix + "bits_forwardData_0"]


def test_explicit_zero_and_false_are_checked_but_omitted_fields_are_not():
    expected = _psq().expected(PublicResponse(
        forward=(ForwardExpectation(valid=1, forward_invalid=0, match_invalid=0,
                                    data_invalid=0, addr_invalid=0, forward_mask=0,
                                    data_byte_mask=0x00FF, forward_data=0),)))
    assert expected["io_forward_0_s2Resp_bits_dataInvalid_valid"] == 0
    assert expected["io_forward_0_s2Resp_bits_forwardInvalid"] == 0
    assert expected["io_forward_0_s2Resp_bits_matchInvalid"] == 0
    assert expected["io_forward_0_s2Resp_bits_addrInvalid_valid"] == 0
    assert expected["io_forward_0_s2Resp_bits_forwardMask_15"] == 0
    assert expected["io_forward_0_s2Resp_bits_forwardData_0"] == 0
    assert "io_forward_0_s2Resp_bits_forwardData_8" not in expected
    assert "io_forward_0_s2Resp_bits_dataInvalid_bits_value" not in expected

    partial = _psq().expected(PublicResponse(forward=(ForwardExpectation(valid=1),)))
    assert partial == {"io_forward_0_s2Resp_valid": 1}

    # A data-only window must not silently become DUT forwardMask assertions.
    data_only = _psq().expected(PublicResponse(forward=(
        ForwardExpectation(valid=1, data_byte_mask=0x00FF, forward_data=0x22),)))
    assert data_only["io_forward_0_s2Resp_bits_forwardData_0"] == 0x22
    assert not any("forwardMask" in key for key in data_only)

    readiness = _psq().expected(PublicResponse(addr_ready_clear_mask=(1 << 64) - 1,
                                               data_ready_clear_mask=(1 << 64) - 1))
    assert len(readiness) == 128 and not any(readiness.values())
    wrong = dict(readiness)
    wrong["io_toLoadQueue_stAddrReadyVec_63"] = 1
    assert _compare(wrong, readiness) == ["io_toLoadQueue_stAddrReadyVec_63"]


def test_forward_data_without_byte_range_is_rejected_and_unknown_type_fails_closed():
    with pytest.raises(ValueError):
        _sq().expected(SqObservation(
            forward=(ForwardExpectation(valid=1, forward_data=0x11),)))
    with pytest.raises(ValueError):
        _sq().expected(SqObservation(
            forward=(ForwardExpectation(valid=1, data_byte_mask=0x00FF),)))
    with pytest.raises(ValueError):
        _sq().expected(SqObservation(
            forward=(ForwardExpectation(valid=1, data_byte_mask=0, forward_data=0x11),)))
    with pytest.raises(TypeError):
        _sq().expected(SqObservation(forward=(object(),)))

    # The data window is a selection of compared bytes, not a DUT mask.  A
    # narrower window must leave the other data bytes unconstrained while an
    # explicit forward_mask still asserts all sixteen mask bits.
    expected = _psq().expected(PublicResponse(forward=(
        ForwardExpectation(valid=1, forward_mask=0x00FF, data_byte_mask=0x0001, forward_data=0xA5),)))
    assert expected["io_forward_0_s2Resp_bits_forwardData_0"] == 0xA5
    assert "io_forward_0_s2Resp_bits_forwardData_1" not in expected
    assert expected["io_forward_0_s2Resp_bits_forwardMask_8"] == 0
    wrong = dict(expected)
    wrong["io_forward_0_s2Resp_bits_forwardData_0"] ^= 1
    assert _compare(wrong, expected) == ["io_forward_0_s2Resp_bits_forwardData_0"]


def test_exception_info_is_not_silently_dropped():
    from suites.memblock.lsq.testbenches.shared.transactions import ExceptionInfo
    expected = _sq().expected(SqObservation(
        exception_info=ExceptionInfo(vaddr=0x1234)))
    assert expected["io_exceptionInfo_valid"] == 1
    assert expected["io_exceptionInfo_bits_vaddr"] == 0x1234

    from dataclasses import replace
    from suites.memblock.lsq.testbenches.deq.env.ports import Ports as DeqPorts
    from suites.memblock.lsq.testbenches.deq.transactions import Observation as DeqObservation
    from suites.memblock.lsq.testbenches.deq import transactions as deq_tx
    from suites.memblock.lsq.testbenches.shared import transactions as shared_tx
    for ports, observation, vocabulary in ((_psq(), PublicResponse, shared_tx), (_sq(), SqObservation, shared_tx),
                                           (DeqPorts.__new__(DeqPorts), DeqObservation, deq_tx)):
        for field, value, valid_pin, payload_pin in (
                ("writeback", vocabulary.Writeback(access_fault=0, valid=None), "io_writeBack_valid", "io_writeBack_bits_exceptionVec_7"),
                ("exception_info", vocabulary.ExceptionInfo(vaddr=0x1234, valid=None), "io_exceptionInfo_valid", "io_exceptionInfo_bits_vaddr"),
                ("cache_request", vocabulary.CacheRequest(opcode=0, valid=None), "io_toDCache_req_valid", "io_toDCache_req_bits_opcode"),
                ("uncache_request", vocabulary.UncacheRequest(addr=0x1234, valid=None), "io_toUncacheBuffer_req_valid", "io_toUncacheBuffer_req_bits_addr")):
            payload_only = ports.expected(observation(**{field: value}))
            assert set(payload_only) == {payload_pin}
            required = ports.expected(observation(**{field: replace(value, valid=1)}))
            assert required[valid_pin] == 1 and payload_only.items() <= required.items()
            wrong = dict(required, **{valid_pin: 0})
            assert _compare(wrong, required) == [valid_pin]
            explicit_zero = ports.expected(observation(**{field: replace(value, valid=0)}))
            assert explicit_zero[valid_pin] == 0
        assert ports.word_expected(0, vocabulary.SbufferWord(wline=0))["io_writeToSbuffer_req_0_valid"] == 1
        assert ports.word_expected(0, vocabulary.SbufferWord(wline=0, valid=None)) == {
            "io_writeToSbuffer_req_0_bits_wline": 0}


def test_empty_expectation_object_is_not_a_check():
    env = StoreQueueEnv.__new__(StoreQueueEnv)
    env.nodeid = "control"
    with pytest.raises(AssertionError):
        env.expect_object({}, "literal empty expectation")
    psq = PsqEnv.__new__(PsqEnv)
    psq.nodeid = "control"
    with pytest.raises(AssertionError):
        psq.expect_object({}, "literal empty expectation")


def test_wrapper_typed_window_consumes_every_declared_channel():
    from suites.memblock.lsq.testbenches.lsq_wrapper.env.ports import decode_observation, expected as wrapper_expected
    from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import (
        BypassResponse, ForwardResponse, Observation, ReplaySlot, UncacheRequest)
    from suites.memblock.lsq.testbenches.raw.transactions import SqPtr

    observation = Observation(
        lq_empty=1, issue_ptr=SqPtr.encode(2),
        bypass=(BypassResponse(s1_valid=1, s1_paddr=0x40), None, None),
        replays=(ReplaySlot(valid=1, replay_queue_idx=5), None, None),
        forward=(ForwardResponse(valid=1, forward_mask=0x00FF, forward_data=0xA5), None, None),
        uncache_request=UncacheRequest(cmd=1, addr=0x4000, data=0x11),
        perf=tuple(7 if index == 35 else None for index in range(39)))
    values = wrapper_expected(observation)
    assert values["io_lqEmpty"] == 1
    assert values["io_issuePtrExt_value"] == 2
    assert values["io_bypass_0_s1Resp_bits_paddr"] == 0x40
    assert values["io_replay_0_bits_replayQueueIdx"] == 5
    assert values["io_forward_0_s2Resp_bits_forwardMask_7"] == 1
    assert values["io_forward_0_s2Resp_bits_forwardMask_8"] == 0
    assert values["io_forward_0_s2Resp_bits_forwardData_0"] == 0xA5
    assert values["io_uncache_req_bits_cmd"] == 1
    assert values["io_uncache_req_bits_addr"] == 0x4000
    assert values["io_perf_35_value"] == 7
    assert not any(key.startswith("io_perf_3") for key in values if key != "io_perf_35_value")
    with pytest.raises((AttributeError, TypeError)):
        wrapper_expected(Observation(forward=(object(),)))
    # Actual full-window decode must construct the real snapshot classes, not
    # just accept hand-built partial expectations. Missing observations fail.
    import json
    from suites.memblock.lsq import ROOT
    pins = {}
    def outputs(node, prefix=()):
        if "Pin" in node:
            if node["Pin"] == "output":
                pins["_".join(prefix)] = 0
        else:
            for name, value in node.items():
                if isinstance(value, dict):
                    outputs(value, (*prefix, name))
    outputs(json.loads((ROOT / "dut/lsq_wrapper/signals.json").read_text()))
    snapshot = decode_observation(pins)
    assert snapshot.forward[0].data_invalid_ptr == SqPtr()
    diagnostic = decode_observation(pins | {"io_stExceptionInfo_bits_vaddr": 0x12340,
                                           "io_stExceptionInfo_bits_isHyper": 1})
    assert diagnostic.st_exception is None
    assert diagnostic.st_exception_sample.vaddr == 0x12340 and diagnostic.st_exception_sample.hyper == 1
    with pytest.raises(ValueError):
        wrapper_expected(Observation(st_exception_sample=diagnostic.st_exception_sample))
    from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import NukeQuery
    with pytest.raises(ValueError):
        wrapper_expected(Observation(raw_nuke=(NukeQuery(req_ready=1, nuke=0),)))
    with pytest.raises(KeyError):
        decode_observation({key: value for key, value in pins.items() if key != "io_forward_0_s2Resp_valid"})
    from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import ExceptionInfo
    exception = wrapper_expected(Observation(ld_exception=ExceptionInfo(access_fault=0, bus_error=1)))
    assert exception == {"io_ldExceptionInfo_bits_exceptionVec_5": 0,
                         "io_ldExceptionInfo_bits_exceptionVec_19": 1}
