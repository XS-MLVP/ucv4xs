"""Checker discrimination controls: one wrong bit must be rejected."""

from __future__ import annotations

from dataclasses import replace

import pytest
from toffee.scoreboard import ScoreboardMismatch

from suites.frontend.ibuffer.testbenches.ibuffer.checker import check_outputs as check_ibuffer
from suites.frontend.ibuffer.testbenches.ibuffer.model import DECODE_WIDTH
from suites.frontend.ibuffer.testbenches.ibuffer.model import Outputs
from suites.frontend.ibuffer.testbenches.ibuffer.model import LaneOutputs
from suites.frontend.ibuffer.testbenches.ibuffer.model import reset_outputs
from suites.frontend.ibuffer.testbenches.vtype_gen.model import VType


def _valid_lane() -> LaneOutputs:
    lane = reset_outputs().lanes[0]
    return replace(lane, valid=1, instr=0x1234_5678, foldpc=0x155,
                   is_rvc=1, pred_taken=1, ftq_flag=1, ftq_value=7,
                   ftq_offset=9, trigger=3, cross_page_ipf_fix=1,
                   backend_exception=1, satp_flush_first_fetch_fault=1,
                   exc_page_fault=1,
                   vtype=VType(0, 1, 0, 2, 1), specvtype=VType(0, 0, 1, 2, 1))


def _with_lane(outputs: Outputs, lane: int, row: LaneOutputs) -> Outputs:
    lanes = list(outputs.lanes)
    lanes[lane] = row
    return replace(outputs, lanes=tuple(lanes))


@pytest.mark.feature("IBUF-ENV-002")
def test_ibuffer_checker_rejects_one_payload_bit():
    expected = _with_lane(reset_outputs(), 0, _valid_lane())
    actual_row = replace(_valid_lane(), instr=0x1234_5679)
    actual = _with_lane(reset_outputs(), 0, actual_row)
    with pytest.raises(ScoreboardMismatch):
        check_ibuffer(expected, actual, phase="discrimination")


@pytest.mark.feature("IBUF-ENV-002")
def test_ibuffer_checker_rejects_ready_empty_and_exception_lies():
    expected = reset_outputs()
    for field, value in (("in_ready", 0), ("empty", 0), ("full", 1)):
        with pytest.raises(ScoreboardMismatch):
            check_ibuffer(expected, replace(expected, **{field: value}),
                          phase="discrimination")
    lane = _valid_lane()
    expected = _with_lane(reset_outputs(), 0, lane)
    for change in ({"exc_page_fault": 0}, {"exc_guest_page_fault": 1},
                   {"satp_flush_first_fetch_fault": 0},
                   {"cross_page_ipf_fix": 0}, {"backend_exception": 0}):
        actual = _with_lane(reset_outputs(), 0, replace(lane, **change))
        with pytest.raises(ScoreboardMismatch):
            check_ibuffer(expected, actual, phase="discrimination")


@pytest.mark.feature("IBUF-ENV-002")
def test_ibuffer_checker_rejects_vtype_and_stall_lies():
    lane = _valid_lane()
    expected = _with_lane(reset_outputs(), 0, lane)
    actual = _with_lane(reset_outputs(), 0,
                        replace(lane, vtype=VType(0, 1, 0, 2, 0)))
    with pytest.raises(ScoreboardMismatch):
        check_ibuffer(expected, actual, phase="discrimination")
    actual = _with_lane(reset_outputs(), 0,
                        replace(lane, specvtype=VType(1, 0, 0, 0, 0)))
    with pytest.raises(ScoreboardMismatch):
        check_ibuffer(expected, actual, phase="discrimination")
    base = reset_outputs()
    actual = replace(base, stall_reason=(13,) * DECODE_WIDTH)
    with pytest.raises(ScoreboardMismatch):
        check_ibuffer(base, actual, phase="discrimination")


@pytest.mark.feature("IBUF-ENV-002")
def test_ibuffer_checker_accepts_the_true_value():
    lane = _valid_lane()
    expected = _with_lane(reset_outputs(), 0, lane)
    check_ibuffer(expected, expected, phase="discrimination")  # must not raise
