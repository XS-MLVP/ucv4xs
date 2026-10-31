"""FrontendTrigger: configuration, PC matching, chains and per-lane actions."""

from __future__ import annotations

import random

import pytest

from suites.frontend.ifu.legacy_pins import P
from suites.frontend.ifu.model.trigger import ACTION_BREAKPOINT
from suites.frontend.ifu.model.trigger import ACTION_DEBUG
from suites.frontend.ifu.model.trigger import ACTION_NONE
from suites.frontend.ifu.model.trigger import EQ
from suites.frontend.ifu.model.trigger import GE
from suites.frontend.ifu.model.trigger import Inputs
from suites.frontend.ifu.model.trigger import LANES
from suites.frontend.ifu.model.trigger import LT
from suites.frontend.ifu.model.trigger import TRIGGERS
from suites.frontend.ifu.model.trigger import Trigger
from suites.frontend.ifu.model.trigger import TriggerModel
from suites.frontend.ifu.model.trigger import Update


def apply(harness, inputs: Inputs, base_pc: int) -> None:
    update = inputs.update
    trigger = update.trigger or Trigger()
    harness.set(
        io_frontendTrigger_tUpdate_valid=update.valid,
        io_frontendTrigger_tUpdate_bits_addr=update.index,
        io_frontendTrigger_tUpdate_bits_tdata_matchType=trigger.match_type,
        io_frontendTrigger_tUpdate_bits_tdata_select=trigger.select,
        io_frontendTrigger_tUpdate_bits_tdata_action=trigger.action,
        io_frontendTrigger_tUpdate_bits_tdata_chain=trigger.chain,
        io_frontendTrigger_tUpdate_bits_tdata_tdata2=trigger.tdata2,
        io_frontendTrigger_debugMode=inputs.debug_mode,
        io_frontendTrigger_triggerCanRaiseBpExp=inputs.can_raise_breakpoint,
    )
    for index in range(TRIGGERS):
        harness.set(**{P.io(f"frontendTrigger_tEnableVec_{index}"): inputs.enable[index]})
    for lane in range(LANES):
        harness.set(**{P.io(f"pc_{lane}_addr"): (base_pc >> 1) + lane})


def observe(harness) -> list[int]:
    return [harness.read(P.io(f"triggered_{lane}")) for lane in range(LANES)]


def cycle(harness, model: TriggerModel, inputs: Inputs, base_pc: int, *,
          expected_override: list[int] | None = None) -> list[int]:
    apply(harness, inputs, base_pc)
    harness.refresh()
    observed = observe(harness)
    expected = (expected_override if expected_override is not None else
                model.lane_actions(inputs, tuple(base_pc + 2 * lane for lane in range(LANES))))
    assert observed == expected, (
        f"base {base_pc:#x} update={inputs.update}\n"
        f"expected {expected}\nobserved {observed}")
    model.tick(inputs)
    harness.step(1)
    return observed


def start(harness) -> TriggerModel:
    harness.reset()
    return TriggerModel()


IDLE = Update()
ENABLE0 = (1, 0, 0, 0)
ENABLE01 = (1, 1, 0, 0)


def normal(enable=ENABLE0, *, debug=0, can_raise=1) -> Inputs:
    return Inputs(update=IDLE, enable=enable, debug_mode=debug,
                  can_raise_breakpoint=can_raise, pcs=())


def configure(index: int, trigger: Trigger, enable=ENABLE0, *, debug=0, can_raise=1) -> Inputs:
    return Inputs(update=Update(valid=1, index=index, trigger=trigger), enable=enable,
                  debug_mode=debug, can_raise_breakpoint=can_raise, pcs=())


# ---------------------------------------------------------------------------
# Directed configuration and matching
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-TR-001")
@pytest.mark.feature("IFU-TR-002")
@pytest.mark.feature("IFU-TR-005")
def test_equal_match_raises_configured_action(frontend_trigger):
    model = start(frontend_trigger)
    base = 0x1000
    target = base + 2 * 10
    cycle(frontend_trigger, model, configure(0, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        tdata2=target)), base)
    actions = cycle(frontend_trigger, model, normal(), base)
    assert actions[10] == ACTION_BREAKPOINT
    assert all(action == ACTION_NONE for index, action in enumerate(actions) if index != 10)
    cycle(frontend_trigger, model, configure(0, Trigger(EQ, action=ACTION_DEBUG,
                                                        tdata2=target)), base)
    actions = cycle(frontend_trigger, model, normal(), base)
    assert actions[10] == ACTION_DEBUG


@pytest.mark.feature("IFU-TR-002")
def test_greater_equal_and_less_than_compare_the_whole_address(frontend_trigger):
    model = start(frontend_trigger)
    base = 0x2000
    threshold = base + 2 * 20
    cycle(frontend_trigger, model, configure(0, Trigger(GE, action=ACTION_DEBUG,
                                                        tdata2=threshold)), base)
    actions = cycle(frontend_trigger, model, normal(), base)
    assert actions[:20] == [ACTION_NONE] * 20
    assert actions[20:] == [ACTION_DEBUG] * (LANES - 20)
    cycle(frontend_trigger, model, configure(0, Trigger(LT, action=ACTION_DEBUG,
                                                        tdata2=threshold)), base)
    actions = cycle(frontend_trigger, model, normal(), base)
    assert actions[:20] == [ACTION_DEBUG] * 20
    assert actions[20:] == [ACTION_NONE] * (LANES - 20)
    # High PC bits participate: a trigger above the current window must not match.
    cycle(frontend_trigger, model, configure(0, Trigger(EQ, action=ACTION_DEBUG,
                                                        tdata2=base + (1 << 30))), base)
    assert cycle(frontend_trigger, model, normal(), base) == [ACTION_NONE] * LANES


@pytest.mark.feature("IFU-TR-002")
def test_compare_carry_boundary_sweep(frontend_trigger):
    """Sweep the 7-bit low/high split used by the consecutive-PC comparator.

    The optimized comparator computes the high part once and derives the
    possible carry from the low bits.  Starting a window just below a 128-byte
    boundary makes lanes cross that boundary, forcing the +1 high-part and
    carry paths in all three supported relations.
    """

    model = start(frontend_trigger)
    for begin in range(0, 128, 2):
        base = 0x10000 + begin
        for match_type in (EQ, GE, LT):
            target = base + 2 * 10
            cycle(frontend_trigger, model,
                  configure(0, Trigger(match_type, action=ACTION_DEBUG, tdata2=target)), base)
            cycle(frontend_trigger, model, normal(), base)


@pytest.mark.feature("IFU-TR-002")
@pytest.mark.feature("IFU-TR-003")
def test_each_trigger_replica_has_its_own_compare_and_select(frontend_trigger):
    """The comparator and select gate are replicated per trigger index."""

    model = start(frontend_trigger)
    base = 0x10000 + 126  # crosses the 128-byte low/high split within the window
    target = base + 2 * 10
    for index in range(TRIGGERS):
        enable = tuple(1 if item == index else 0 for item in range(TRIGGERS))
        cycle(frontend_trigger, model,
              configure(index, Trigger(GE, action=ACTION_DEBUG, tdata2=target), enable), base)
        assert cycle(frontend_trigger, model, normal(enable), base)[10] == ACTION_DEBUG
        cycle(frontend_trigger, model,
              configure(index, Trigger(EQ, select=1, action=ACTION_DEBUG, tdata2=target),
                        enable), base)
        assert cycle(frontend_trigger, model, normal(enable), base)[10] == ACTION_NONE
        cycle(frontend_trigger, model,
              configure(index, Trigger(EQ, select=0, action=ACTION_DEBUG, tdata2=target),
                        enable), base)
        assert cycle(frontend_trigger, model, normal(enable), base)[10] == ACTION_DEBUG


@pytest.mark.feature("IFU-TR-003")
def test_enable_select_and_debug_mode_gate_matching(frontend_trigger):
    model = start(frontend_trigger)
    base = 0x3000
    target = base + 2 * 5
    trigger = Trigger(EQ, action=ACTION_DEBUG, tdata2=target)
    cycle(frontend_trigger, model, configure(0, trigger), base)
    assert cycle(frontend_trigger, model, normal(), base)[5] == ACTION_DEBUG
    # The enable vector is registered: one cycle to observe the clear.
    cycle(frontend_trigger, model, normal(enable=(0, 0, 0, 0)), base)
    assert cycle(frontend_trigger, model, normal(enable=(0, 0, 0, 0)), base)[5] == ACTION_NONE
    # Debug mode is a live gate.
    assert cycle(frontend_trigger, model, normal(debug=1), base)[5] == ACTION_NONE
    cycle(frontend_trigger, model, configure(0, Trigger(EQ, select=1, action=ACTION_DEBUG,
                                                        tdata2=target)), base)
    assert cycle(frontend_trigger, model, normal(), base)[5] == ACTION_NONE
    cycle(frontend_trigger, model, configure(0, Trigger(EQ, select=0, action=ACTION_DEBUG,
                                                        tdata2=target)), base)
    assert cycle(frontend_trigger, model, normal(), base)[5] == ACTION_DEBUG


@pytest.mark.feature("IFU-TR-001")
def test_update_targets_only_the_selected_index(frontend_trigger):
    model = start(frontend_trigger)
    base = 0x4000
    pc_a = base + 2 * 3
    pc_b = base + 2 * 9
    pc_c = base + 2 * 17
    cycle(frontend_trigger, model, configure(0, Trigger(EQ, action=ACTION_DEBUG, tdata2=pc_a),
                                             ENABLE01), base)
    cycle(frontend_trigger, model, configure(1, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        tdata2=pc_b), ENABLE01), base)
    actions = cycle(frontend_trigger, model, normal(ENABLE01), base)
    assert actions[3] == ACTION_DEBUG and actions[9] == ACTION_BREAKPOINT
    cycle(frontend_trigger, model, configure(1, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        tdata2=pc_c), ENABLE01), base)
    actions = cycle(frontend_trigger, model, normal(ENABLE01), base)
    assert actions[3] == ACTION_DEBUG
    assert actions[9] == ACTION_NONE
    assert actions[17] == ACTION_BREAKPOINT


@pytest.mark.feature("IFU-TR-005")
def test_breakpoint_requires_permission_and_debug_wins(frontend_trigger):
    model = start(frontend_trigger)
    base = 0x5000
    target = base + 2
    cycle(frontend_trigger, model, configure(0, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        tdata2=target)), base)
    assert cycle(frontend_trigger, model, normal(can_raise=0), base)[1] == ACTION_NONE
    # A second trigger on the same PC requests debug mode; it must win.
    cycle(frontend_trigger, model, configure(1, Trigger(EQ, action=ACTION_DEBUG,
                                                        tdata2=target), ENABLE01), base)
    assert cycle(frontend_trigger, model, normal(ENABLE01), base)[1] == ACTION_DEBUG
    # Unsupported actions do not become breakpoints.
    cycle(frontend_trigger, model, configure(1, Trigger(EQ, action=2, tdata2=target)), base)
    assert cycle(frontend_trigger, model, normal(ENABLE01), base)[1] == ACTION_BREAKPOINT


@pytest.mark.feature("IFU-TR-005")
@pytest.mark.feature("IFU-TR-006")
def test_action_resolution_at_every_lane(frontend_trigger):
    """Each lane's debug/breakpoint/none arms need their own stimulus.

    The generated action mux is physically replicated per lane; a hit only on
    lane 3 says nothing about lane 27's breakpoint path.  Sweep both actions
    across the window so every lane's priority mux is verified.
    """

    model = start(frontend_trigger)
    base = 0x9000
    for lane in range(LANES):
        target = base + 2 * lane
        for action in (ACTION_DEBUG, ACTION_BREAKPOINT):
            cycle(frontend_trigger, model,
                  configure(0, Trigger(EQ, action=action, tdata2=target)), base)
            actions = cycle(frontend_trigger, model, normal(), base)
            assert actions[lane] == action
            assert all(value == ACTION_NONE for index, value in enumerate(actions) if index != lane)


@pytest.mark.feature("IFU-TR-006")
def test_actions_are_per_lane(frontend_trigger):
    model = start(frontend_trigger)
    base = 0x6000
    cycle(frontend_trigger, model, configure(0, Trigger(EQ, action=ACTION_DEBUG,
                                                        tdata2=base + 2 * 3), ENABLE01), base)
    cycle(frontend_trigger, model, configure(1, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        tdata2=base + 2 * 7), ENABLE01), base)
    actions = cycle(frontend_trigger, model, normal(ENABLE01), base)
    assert actions[3] == ACTION_DEBUG and actions[7] == ACTION_BREAKPOINT
    assert sum(action != ACTION_NONE for action in actions) == 2


@pytest.mark.feature("IFU-TR-004")
def test_pairwise_chain_arms_the_next_trigger(frontend_trigger):
    model = start(frontend_trigger)
    base = 0x7000
    target = base + 2 * 4
    chained = Trigger(EQ, action=ACTION_DEBUG, chain=1, timing=0, tdata2=target)
    terminal = Trigger(EQ, action=ACTION_BREAKPOINT, chain=0, timing=0, tdata2=target)
    cycle(frontend_trigger, model, configure(0, chained, ENABLE01), base)
    cycle(frontend_trigger, model, configure(1, terminal, ENABLE01), base)
    assert cycle(frontend_trigger, model, normal(ENABLE01), base)[4] == ACTION_BREAKPOINT
    # This machine's CSR generation ties timing to "before execution" for
    # every trigger, so the timing comparison is constantly satisfied and the
    # interface does not expose a timing input.
    # A miss on the chained trigger also breaks the link.
    cycle(frontend_trigger, model, configure(0, Trigger(EQ, action=ACTION_DEBUG, chain=1,
                                                        timing=0, tdata2=base + 2 * 20),
                                             ENABLE01), base)
    cycle(frontend_trigger, model, configure(1, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        timing=0, tdata2=target), ENABLE01), base)
    assert cycle(frontend_trigger, model, normal(ENABLE01), base)[4] == ACTION_NONE
    # A chained trigger does not block an independent trigger for the same PC.
    cycle(frontend_trigger, model, configure(0, Trigger(EQ, action=ACTION_DEBUG, chain=1,
                                                        timing=0, tdata2=target),
                                             (1, 0, 1, 0)), base)
    cycle(frontend_trigger, model, configure(2, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        timing=0, tdata2=target),
                                             (1, 0, 1, 0)), base)
    assert cycle(frontend_trigger, model, normal((1, 0, 1, 0)), base)[4] == ACTION_BREAKPOINT


@pytest.mark.feature("IFU-TR-007")
def test_reset_clears_configuration(frontend_trigger):
    model = start(frontend_trigger)
    base = 0x8000
    target = base + 2 * 6
    cycle(frontend_trigger, model, configure(0, Trigger(EQ, action=ACTION_DEBUG,
                                                        tdata2=target)), base)
    assert cycle(frontend_trigger, model, normal(), base)[6] == ACTION_DEBUG
    frontend_trigger.reset()
    model = TriggerModel()
    # The enable register is also cleared; one cycle later the new enable is
    # visible but the trigger configuration is still empty.
    assert cycle(frontend_trigger, model, normal(), base) == [ACTION_NONE] * LANES
    assert cycle(frontend_trigger, model, normal(), base) == [ACTION_NONE] * LANES


@pytest.mark.feature("IFU-TR-003")
def test_disabled_trigger_ignores_any_tdata2_value(frontend_trigger):
    """A disabled trigger must not act, whatever the 64-bit tdata2 holds.

    This is the enable-gate contract, and it is also the only legal way to
    exercise the high tdata2 bits: with the trigger disabled the result is
    "no action" under both the full-width and the truncated interpretation, so
    the check stays meaningful while the width defect (R-13) is still open.
    """

    model = start(frontend_trigger)
    base = 0x7000
    rng = random.Random(0x7D15)
    for _ in range(8):
        value = rng.getrandbits(64)
        cycle(frontend_trigger, model,
              configure(0, Trigger(EQ, action=ACTION_DEBUG, tdata2=value), (0, 0, 0, 0)), base)
        assert cycle(frontend_trigger, model, normal((0, 0, 0, 0)), base) == [ACTION_NONE] * LANES


# ---------------------------------------------------------------------------
# tdata2 width: the producer (CSR) exposes all 64 bits
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-TR-002")
def test_tdata2_above_the_address_space_cannot_equal_a_fetch_pc(frontend_trigger):
    """tdata2 is a 64-bit RW field; 2**50+pc is not the same address as pc."""

    model = start(frontend_trigger)
    base = 0x5000
    target = base + 2 * 10
    cycle(frontend_trigger, model,
          configure(0, Trigger(EQ, action=ACTION_DEBUG, tdata2=(1 << 50) | target)), base)
    actions = cycle(frontend_trigger, model, normal(), base)
    # 2**50 + target is outside the address space, so no fetch PC equals it.
    assert actions == [ACTION_NONE] * LANES


@pytest.mark.feature("IFU-TR-002")
def test_tdata2_above_the_address_space_is_greater_for_less_than(frontend_trigger):
    """Every implemented PC is less than 2**50, so LT must hit every lane."""

    model = start(frontend_trigger)
    base = 0x6000
    cycle(frontend_trigger, model,
          configure(0, Trigger(LT, action=ACTION_DEBUG, tdata2=(1 << 50))), base)
    actions = cycle(frontend_trigger, model, normal(), base)
    assert actions == [ACTION_DEBUG] * LANES


# ---------------------------------------------------------------------------
# Random comparison
# ---------------------------------------------------------------------------
def random_trigger(rng: random.Random) -> Trigger:
    return Trigger(
        match_type=rng.choice([EQ, GE, LT, 1]),
        select=int(rng.random() < 0.1),
        action=rng.choice([ACTION_BREAKPOINT, ACTION_DEBUG, ACTION_NONE, 2, 3]),
        chain=int(rng.random() < 0.3),
        # Randomise over addresses the machine can generate.  Values outside
        # the implemented address space are a separate, explicitly tested class
        # (see the tdata2_width tests below): they must not be folded into the
        # random domain, which would hide the producer/consumer width question.
        tdata2=rng.getrandbits(50),
    )


@pytest.mark.feature("IFU-TR-001")
@pytest.mark.feature("IFU-TR-002")
@pytest.mark.feature("IFU-TR-003")
@pytest.mark.feature("IFU-TR-004")
@pytest.mark.feature("IFU-TR-005")
@pytest.mark.feature("IFU-TR-006")
def test_random_configuration_sequences_match_the_model(frontend_trigger):
    rng = random.Random(0x7A11)
    model = start(frontend_trigger)
    for step in range(180):
        # Spread PCs over the architectural range so the full comparator and
        # the per-lane match matrix see varied high bits; keep the window
        # below 2^50 and aligned so the consecutive-PC optimization is valid.
        base = rng.randrange(0, (1 << 50) - 2 * LANES, 2)
        update = Update()
        if rng.random() < 0.4:
            update = Update(valid=1, index=rng.randrange(TRIGGERS), trigger=random_trigger(rng))
        inputs = Inputs(update=update,
                        enable=tuple(int(rng.random() < 0.6) for _ in range(TRIGGERS)),
                        debug_mode=int(rng.random() < 0.1),
                        can_raise_breakpoint=int(rng.random() < 0.7),
                        pcs=())
        cycle(frontend_trigger, model, inputs, base)
