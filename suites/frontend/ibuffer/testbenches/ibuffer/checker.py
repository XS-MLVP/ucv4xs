"""Independent checkers for the IBuffer top-level contract.

Every checked cycle compares the complete observable output surface (valid,
payload, exception bits, vtype windows and stall reasons) against the model.
Payload fields are compared only on lanes the model says are valid: the
architectural contract does not constrain the bits of an invalid lane.
"""

from __future__ import annotations

from toffee import Scoreboard

from suites.frontend.ibuffer.testbenches.ibuffer.model import DECODE_WIDTH
from suites.frontend.ibuffer.testbenches.ibuffer.model import Outputs
from suites.frontend.ibuffer.testbenches.ibuffer.model import reset_outputs


def _flatten(outputs: Outputs) -> dict[str, int]:
    flat = {"in_ready": outputs.in_ready, "full": outputs.full,
            "empty": outputs.empty}
    for lane in range(DECODE_WIDTH):
        row = outputs.lanes[lane]
        flat[f"out_{lane}_valid"] = row.valid
        if row.valid:
            for key, value in row.payload().items():
                flat[f"out_{lane}_{key}"] = value
    for lane in range(DECODE_WIDTH):
        flat[f"stall_{lane}"] = outputs.stall_reason[lane]
    return flat


def check_outputs(expected: Outputs, observed: Outputs, *, phase: str) -> None:
    if not isinstance(expected, Outputs) or not isinstance(observed, Outputs):
        raise TypeError("IBuffer checker requires complete semantic Outputs")
    Scoreboard(f"ibuffer.{phase}").check(
        expected=_flatten(expected), actual=_flatten(observed))


def check_reset(observed: Outputs, *, phase: str) -> None:
    check_outputs(reset_outputs(), observed, phase=f"reset.{phase}")


def check_no_head_bubble(cycle) -> None:
    """The output window is head-contiguous: a valid lane implies its head."""
    for lane in range(1, DECODE_WIDTH):
        if cycle.before.lanes[lane].valid:
            assert cycle.before.lanes[lane - 1].valid, (
                f"cycle {cycle.index}: bubble at output lane {lane - 1}")


def check_no_bubble_after_edge(cycle) -> None:
    for lane in range(1, DECODE_WIDTH):
        if cycle.after.lanes[lane].valid:
            assert cycle.after.lanes[lane - 1].valid, (
                f"cycle {cycle.index}: post-edge bubble at lane {lane - 1}")


def check_enqueue(cycle, *, count: int) -> None:
    assert cycle.events.fire == 1, (
        f"cycle {cycle.index}: expected an enqueue fire, "
        f"state={cycle.state_before}")
    assert cycle.events.num_enq == count, (
        f"cycle {cycle.index}: enqueued {cycle.events.num_enq} != {count}")


def check_not_enqueued(cycle) -> None:
    assert cycle.events.fire == 0 or cycle.events.num_enq == 0, (
        f"cycle {cycle.index}: unexpected enqueue of {cycle.events.num_enq}")
    assert cycle.state_after["occupancy"] == cycle.state_before["occupancy"], (
        f"cycle {cycle.index}: queue occupancy changed without an enqueue")


def check_dequeue(cycle, *, count: int) -> None:
    assert cycle.events.num_out == count, (
        f"cycle {cycle.index}: dequeued {cycle.events.num_out} != {count}")


def check_bypass(cycle) -> None:
    assert cycle.events.use_bypass == 1, (
        f"cycle {cycle.index}: expected the bypass path")
    for lane, row in enumerate(cycle.before.lanes):
        if row.valid:
            assert row.vtype == row.specvtype, (
                f"cycle {cycle.index}: bypass lane {lane} has vtype != specvtype")


def check_full_backpressure(cycle) -> None:
    assert cycle.before.in_ready == 0 and cycle.before.full == 1, (
        f"cycle {cycle.index}: expected full/backpressure")
    assert cycle.events.fire == 0


def check_flush(cycle) -> None:
    assert cycle.inputs.flush == 1
    assert cycle.after.empty == 1, f"cycle {cycle.index}: not empty after flush"
    assert cycle.after.in_ready == 1, f"cycle {cycle.index}: not ready after flush"
    assert all(row.valid == 0 for row in cycle.after.lanes), (
        f"cycle {cycle.index}: output window not cleared by flush")
    assert cycle.state_after["occupancy"] == 0
    assert cycle.state_after["enq_ptr"] == 0 and cycle.state_after["deq_ptr"] == 0


def check_vtype_lane(cycle, lane: int, vtype) -> None:
    observed = cycle.before.lanes[lane]
    assert observed.valid == 1, f"cycle {cycle.index}: lane {lane} is not valid"
    assert observed.vtype == vtype, (
        f"cycle {cycle.index}: lane {lane} vtype {observed.vtype} != {vtype}")


def check_specvtype_lane(cycle, lane: int, vtype) -> None:
    observed = cycle.before.lanes[lane]
    assert observed.valid == 1, f"cycle {cycle.index}: lane {lane} is not valid"
    assert observed.specvtype == vtype, (
        f"cycle {cycle.index}: lane {lane} specvtype {observed.specvtype} != {vtype}")
