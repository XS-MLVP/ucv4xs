"""Independent per-feature checkers for the InstrUncache top level."""

from __future__ import annotations

from toffee import Scoreboard

from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import IDLE
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import REFILL_RESP
from suites.frontend.instr_uncache.testbenches.instr_uncache.model import Outputs
from suites.frontend.instr_uncache.testbenches.instr_uncache.model import reset_snapshot


def _fields(expected: Outputs) -> list[str]:
    fields = ["req_ready", "resp_valid", "a_valid", "wfi_safe"]
    if expected.a_valid:
        fields += ["a_addr", "a_mem_page_nc", "a_mem_back_mm"]
    if expected.resp_valid:
        fields += ["resp_corrupt", "resp_denied", "resp_need_resend"]
        if not expected.resp_corrupt and not expected.resp_denied:
            fields += ["resp_data"]
    return fields


def check_outputs(expected: Outputs, observed: Outputs, *, phase: str) -> None:
    if not isinstance(expected, Outputs) or not isinstance(observed, Outputs):
        raise TypeError("top checker requires complete semantic Outputs snapshots")
    fields = _fields(expected)
    Scoreboard(f"instr_uncache.{phase}").check(
        expected={field: getattr(expected, field) for field in fields},
        actual={field: getattr(observed, field) for field in fields},
    )


def check_reset(observed: Outputs, *, phase: str) -> None:
    expected = reset_snapshot()
    fields = ["req_ready", "resp_valid", "a_valid", "wfi_safe"]
    Scoreboard(f"instr_uncache.reset.{phase}").check(
        expected={field: getattr(expected, field) for field in fields},
        actual={field: getattr(observed, field) for field in fields},
    )


def check_request_accepted(cycle) -> None:
    assert cycle.events.req_fire == 1
    assert cycle.state_before == IDLE and cycle.state_after != IDLE


def check_single_outstanding(cycle) -> None:
    if cycle.state_before != IDLE:
        assert cycle.before.req_ready == 0
    if cycle.state_after != IDLE:
        assert cycle.after.req_ready == 0


def check_acquire(cycle, expected_addr: int, *, mm: int, nc: int) -> None:
    assert cycle.events.acquire_fire == 1, (
        f"cycle {cycle.index}: expected A fire, before={cycle.before.as_dict()}")
    assert cycle.before.a_addr == expected_addr
    assert cycle.before.a_mem_back_mm == mm
    assert cycle.before.a_mem_page_nc == nc


def check_response(cycle, *, data: int | None = None, corrupt: int, denied: int,
                   need_resend: int) -> None:
    assert cycle.events.resp_fire == 1
    assert cycle.before.resp_corrupt == corrupt
    assert cycle.before.resp_denied == denied
    assert cycle.before.resp_need_resend == need_resend
    if data is not None and not corrupt and not denied:
        assert cycle.before.resp_data == data


def check_wfi(cycle) -> None:
    if cycle.inputs.wfi_req:
        assert cycle.before.a_valid == 0
    assert cycle.before.wfi_safe == int(cycle.state_before != REFILL_RESP)
    assert cycle.after.wfi_safe == int(cycle.state_after != REFILL_RESP)


def check_source_filter(cycle) -> None:
    """A D response with source != 0 must be invisible to the entry."""
    if cycle.inputs.d_valid and cycle.inputs.d_source != 0:
        assert cycle.events.grant_fire == 0, (
            f"cycle {cycle.index}: source {cycle.inputs.d_source} completed the request")
        assert cycle.state_after == cycle.state_before
        assert cycle.before.resp_valid == 0 and cycle.after.resp_valid == 0
    if cycle.inputs.d_valid and cycle.inputs.d_source == 0:
        assert cycle.events.grant_fire == int(cycle.state_before == REFILL_RESP)


def check_no_response(cycle) -> None:
    assert cycle.before.resp_valid == 0 and cycle.after.resp_valid == 0


def check_response_loss_persists(cycle, state: str) -> None:
    assert cycle.state_before == state and cycle.state_after == state
    assert cycle.before.resp_valid == 0 and cycle.after.resp_valid == 0
    assert cycle.after.req_ready == 0
