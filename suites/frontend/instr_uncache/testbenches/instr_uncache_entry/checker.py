"""Independent per-feature checkers for InstrUncacheEntry.

The cycle checker always compares the contract-visible outputs against the
independent model.  Feature checkers add the explicit obligation that the test
is claiming, so a test cannot pass merely because every output happened to
match while the feature-specific event never occurred.
"""

from __future__ import annotations

from toffee import Scoreboard

from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import IDLE
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import REFILL_RESP
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import Outputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import reset_snapshot


def _fields(expected: Outputs) -> list[str]:
    fields = ["req_ready", "resp_valid", "acquire_valid", "wfi_safe"]
    if expected.acquire_valid:
        fields += ["acquire_addr", "acquire_mem_page_nc", "acquire_mem_back_mm"]
    if expected.resp_valid:
        fields += ["resp_corrupt", "resp_denied", "resp_need_resend"]
        # Data is architecturally meaningful only for a clean completion.
        if not expected.resp_corrupt and not expected.resp_denied:
            fields += ["resp_data"]
    return fields


def check_outputs(expected: Outputs, observed: Outputs, *, phase: str) -> None:
    if not isinstance(expected, Outputs) or not isinstance(observed, Outputs):
        raise TypeError("Entry checker requires complete semantic Outputs snapshots")
    fields = _fields(expected)
    Scoreboard(f"instr_uncache_entry.{phase}").check(
        expected={field: getattr(expected, field) for field in fields},
        actual={field: getattr(observed, field) for field in fields},
    )


def check_reset(observed: Outputs, *, phase: str) -> None:
    if not isinstance(observed, Outputs):
        raise TypeError("Entry reset checker requires a complete snapshot")
    expected = reset_snapshot()
    fields = ["req_ready", "resp_valid", "acquire_valid", "wfi_safe"]
    Scoreboard(f"instr_uncache_entry.reset.{phase}").check(
        expected={field: getattr(expected, field) for field in fields},
        actual={field: getattr(observed, field) for field in fields},
    )


def check_request_accepted(cycle) -> None:
    assert cycle.events.req_fire == 1, (
        f"cycle {cycle.index}: expected a request acceptance, "
        f"before={cycle.before.as_dict()}")
    assert cycle.state_before == IDLE
    assert cycle.state_after != IDLE


def check_single_outstanding(cycle) -> None:
    """A second request must not be accepted while any state is occupied."""
    if cycle.state_before != IDLE:
        assert cycle.before.req_ready == 0, (
            f"cycle {cycle.index}: req_ready asserted in {cycle.state_before}")
    if cycle.state_after != IDLE:
        assert cycle.after.req_ready == 0, (
            f"cycle {cycle.index}: req_ready left asserted in {cycle.state_after}")


def check_acquire(cycle, expected_addr: int, *, mm: int, nc: int) -> None:
    assert cycle.events.acquire_fire == 1, (
        f"cycle {cycle.index}: expected an A-channel fire, before={cycle.before.as_dict()}")
    assert cycle.before.acquire_addr == expected_addr, (
        f"cycle {cycle.index}: A address {cycle.before.acquire_addr:#x} != {expected_addr:#x}")
    assert cycle.before.acquire_mem_back_mm == mm
    assert cycle.before.acquire_mem_page_nc == nc


def check_acquire_stalled(cycle, expected_addr: int) -> None:
    assert cycle.before.acquire_valid == 1
    assert cycle.events.acquire_fire == 0
    assert cycle.state_after == cycle.state_before
    assert cycle.before.acquire_addr == expected_addr == cycle.after.acquire_addr


def check_response(cycle, *, data: int | None = None, corrupt: int, denied: int,
                   need_resend: int) -> None:
    assert cycle.events.resp_fire == 1, (
        f"cycle {cycle.index}: expected a response pulse, before={cycle.before.as_dict()}")
    assert cycle.before.resp_corrupt == corrupt
    assert cycle.before.resp_denied == denied
    assert cycle.before.resp_need_resend == need_resend
    if data is not None and not corrupt and not denied:
        assert cycle.before.resp_data == data, (
            f"cycle {cycle.index}: response data {cycle.before.resp_data:#010x} != {data:#010x}")


def check_wfi(cycle) -> None:
    if cycle.inputs.wfi_req:
        assert cycle.before.acquire_valid == 0, (
            f"cycle {cycle.index}: A request asserted while wfiReq=1")
    expected_before = int(cycle.state_before != REFILL_RESP)
    expected_after = int(cycle.state_after != REFILL_RESP)
    assert cycle.before.wfi_safe == expected_before, (
        f"cycle {cycle.index}: wfiSafe {cycle.before.wfi_safe} != {expected_before} "
        f"in {cycle.state_before}")
    assert cycle.after.wfi_safe == expected_after, (
        f"cycle {cycle.index}: post-edge wfiSafe {cycle.after.wfi_safe} != "
        f"{expected_after} in {cycle.state_after}")


def check_no_response(cycle) -> None:
    assert cycle.before.resp_valid == 0 and cycle.after.resp_valid == 0, (
        f"cycle {cycle.index}: unexpected response pulse")


def check_response_loss_persists(cycle, state: str) -> None:
    assert cycle.state_before == state and cycle.state_after == state
    assert cycle.before.resp_valid == 0 and cycle.after.resp_valid == 0
    assert cycle.after.req_ready == 0


def check_flush_pruned(audit: dict) -> None:
    """The structural evidence for the out-of-domain flush residual.

    This is deliberately *not* a behaviour check: DefaultConfig ties the flush
    input to false before elaboration, so the cancellation path cannot be
    driven in this closure.  The assertions below only prove that structural
    fact and the recorded scope; they must never be reported as flush
    behaviour verification.
    """
    assert audit["flush"].startswith("pruned constant false")
    assert audit["flush_constant"] == "false.B"
    assert audit["flush_scope"] == "DefaultConfig/public-a0c2a26cb"
    assert audit["flush_behavior"].startswith("not behavior-verified")
    assert audit["flush_evidence"].endswith("flush-closure.json")
    absent = audit["absent"]
    assert "io_flush" in absent
    assert "Frontend.scala:266" in absent["io_flush"]
