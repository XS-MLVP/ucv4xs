"""FrontendTrigger: configuration, PC matching, chains and per-lane actions."""

from __future__ import annotations

import random

import pytest

from dataclasses import replace
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
from suites.frontend.ifu.model.trigger import consecutive_pcs
from suites.frontend.ifu.model.trigger import Update


async def cycle(agent, inputs: Inputs, base_pc: int):
    return list((await agent.cycle(replace(inputs, pcs=consecutive_pcs(base_pc)))).before.actions)


async def characterize(agent, inputs: Inputs, base_pc: int):
    # Explicit port-domain pressure; not evidence of CSR WARL reachability.
    return list((await agent.characterize_cycle(
        replace(inputs, pcs=consecutive_pcs(base_pc)))).before.actions)


IDLE = Update()
ENABLE0 = (1, 0, 0, 0)
ENABLE01 = (1, 1, 0, 0)


def normal(enable=ENABLE0, *, debug=0, can_raise=1) -> Inputs:
    return Inputs(update=IDLE, enable=enable, debug_mode=debug,
                  can_raise_breakpoint=can_raise, pcs=consecutive_pcs(0))


def configure(index: int, trigger: Trigger, enable=ENABLE0, *, debug=0, can_raise=1) -> Inputs:
    return Inputs(update=Update(valid=1, index=index, trigger=trigger), enable=enable,
                  debug_mode=debug, can_raise_breakpoint=can_raise, pcs=consecutive_pcs(0))


# ---------------------------------------------------------------------------
# Directed configuration and matching
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-TR-001")
@pytest.mark.feature("IFU-TR-002")
@pytest.mark.feature("IFU-TR-005")
async def test_equal_match_raises_configured_action(frontend_trigger):
    base = 0x1000
    target = base + 2 * 10
    await cycle(frontend_trigger, configure(0, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        tdata2=target)), base)
    actions = await cycle(frontend_trigger, normal(), base)
    assert actions[10] == ACTION_BREAKPOINT
    assert all(action == ACTION_NONE for index, action in enumerate(actions) if index != 10)
    await cycle(frontend_trigger, configure(0, Trigger(EQ, action=ACTION_DEBUG,
                                                        tdata2=target)), base)
    actions = await cycle(frontend_trigger, normal(), base)
    assert actions[10] == ACTION_DEBUG


@pytest.mark.feature("IFU-TR-002")
async def test_greater_equal_and_less_than_compare_the_whole_address(frontend_trigger):
    base = 0x2000
    threshold = base + 2 * 20
    await cycle(frontend_trigger, configure(0, Trigger(GE, action=ACTION_DEBUG,
                                                        tdata2=threshold)), base)
    actions = await cycle(frontend_trigger, normal(), base)
    assert actions[:20] == [ACTION_NONE] * 20
    assert actions[20:] == [ACTION_DEBUG] * (LANES - 20)
    await cycle(frontend_trigger, configure(0, Trigger(LT, action=ACTION_DEBUG,
                                                        tdata2=threshold)), base)
    actions = await cycle(frontend_trigger, normal(), base)
    assert actions[:20] == [ACTION_DEBUG] * 20
    assert actions[20:] == [ACTION_NONE] * (LANES - 20)
    # High PC bits participate: a trigger above the current window must not match.
    await cycle(frontend_trigger, configure(0, Trigger(EQ, action=ACTION_DEBUG,
                                                        tdata2=base + (1 << 30))), base)
    assert await cycle(frontend_trigger, normal(), base) == [ACTION_NONE] * LANES


@pytest.mark.feature("IFU-TR-002")
async def test_compare_carry_boundary_sweep(frontend_trigger):
    """Sweep the 7-bit low/high split used by the consecutive-PC comparator.

    The optimized comparator computes the high part once and derives the
    possible carry from the low bits.  Starting a window just below a 128-byte
    boundary makes lanes cross that boundary, forcing the +1 high-part and
    carry paths in all three supported relations.
    """

    for begin in range(0, 128, 2):
        base = 0x10000 + begin
        for match_type in (EQ, GE, LT):
            target = base + 2 * 10
            await cycle(frontend_trigger,
                  configure(0, Trigger(match_type, action=ACTION_DEBUG, tdata2=target)), base)
            await cycle(frontend_trigger, normal(), base)


@pytest.mark.feature("IFU-TR-002")
@pytest.mark.feature("IFU-TR-003")
async def test_each_trigger_replica_has_its_own_compare_and_select(frontend_trigger):
    """The comparator and select gate are replicated per trigger index."""

    base = 0x10000 + 126  # crosses the 128-byte low/high split within the window
    target = base + 2 * 10
    for index in range(TRIGGERS):
        enable = tuple(1 if item == index else 0 for item in range(TRIGGERS))
        await characterize(frontend_trigger,
              configure(index, Trigger(GE, action=ACTION_DEBUG, tdata2=target), enable), base)
        assert (await characterize(frontend_trigger, normal(enable), base))[10] == ACTION_DEBUG
        await characterize(frontend_trigger,
              configure(index, Trigger(EQ, select=1, action=ACTION_DEBUG, tdata2=target),
                        enable), base)
        assert (await characterize(frontend_trigger, normal(enable), base))[10] == ACTION_NONE
        await characterize(frontend_trigger,
              configure(index, Trigger(EQ, select=0, action=ACTION_DEBUG, tdata2=target),
                        enable), base)
        assert (await characterize(frontend_trigger, normal(enable), base))[10] == ACTION_DEBUG


@pytest.mark.feature("IFU-TR-003")
async def test_enable_select_and_debug_mode_gate_matching(frontend_trigger):
    base = 0x3000
    target = base + 2 * 5
    trigger = Trigger(EQ, action=ACTION_DEBUG, tdata2=target)
    await characterize(frontend_trigger, configure(0, trigger), base)
    assert (await characterize(frontend_trigger, normal(), base))[5] == ACTION_DEBUG
    # The enable vector is registered: one cycle to observe the clear.
    await characterize(frontend_trigger, normal(enable=(0, 0, 0, 0)), base)
    assert (await characterize(frontend_trigger, normal(enable=(0, 0, 0, 0)), base))[5] == ACTION_NONE
    # Debug mode is a live gate.
    assert (await characterize(frontend_trigger, normal(debug=1), base))[5] == ACTION_NONE
    await characterize(frontend_trigger, configure(0, Trigger(EQ, select=1, action=ACTION_DEBUG,
                                                        tdata2=target)), base)
    assert (await characterize(frontend_trigger, normal(), base))[5] == ACTION_NONE
    await characterize(frontend_trigger, configure(0, Trigger(EQ, select=0, action=ACTION_DEBUG,
                                                        tdata2=target)), base)
    assert (await characterize(frontend_trigger, normal(), base))[5] == ACTION_DEBUG


@pytest.mark.feature("IFU-TR-001")
async def test_update_targets_only_the_selected_index(frontend_trigger):
    base = 0x4000
    pc_a = base + 2 * 3
    pc_b = base + 2 * 9
    pc_c = base + 2 * 17
    await cycle(frontend_trigger, configure(0, Trigger(EQ, action=ACTION_DEBUG, tdata2=pc_a),
                                             ENABLE01), base)
    await cycle(frontend_trigger, configure(1, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        tdata2=pc_b), ENABLE01), base)
    actions = await cycle(frontend_trigger, normal(ENABLE01), base)
    assert actions[3] == ACTION_DEBUG and actions[9] == ACTION_BREAKPOINT
    await cycle(frontend_trigger, configure(1, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        tdata2=pc_c), ENABLE01), base)
    actions = await cycle(frontend_trigger, normal(ENABLE01), base)
    assert actions[3] == ACTION_DEBUG
    assert actions[9] == ACTION_NONE
    assert actions[17] == ACTION_BREAKPOINT


@pytest.mark.feature("IFU-TR-005")
async def test_breakpoint_requires_permission_and_debug_wins(frontend_trigger):
    base = 0x5000
    target = base + 2
    await cycle(frontend_trigger, configure(0, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        tdata2=target)), base)
    assert (await cycle(frontend_trigger, normal(can_raise=0), base))[1] == ACTION_NONE
    # A second trigger on the same PC requests debug mode; it must win.
    await cycle(frontend_trigger, configure(1, Trigger(EQ, action=ACTION_DEBUG,
                                                        tdata2=target), ENABLE01), base)
    assert (await cycle(frontend_trigger, normal(ENABLE01), base))[1] == ACTION_DEBUG
    # Unsupported actions do not become breakpoints.
    await characterize(frontend_trigger, configure(1, Trigger(EQ, action=2, tdata2=target)), base)
    assert (await characterize(frontend_trigger, normal(ENABLE01), base))[1] == ACTION_BREAKPOINT


@pytest.mark.feature("IFU-TR-005")
@pytest.mark.feature("IFU-TR-006")
async def test_action_resolution_at_every_lane(frontend_trigger):
    """Each lane's debug/breakpoint/none arms need their own stimulus.

    The generated action mux is physically replicated per lane; a hit only on
    lane 3 says nothing about lane 27's breakpoint path.  Sweep both actions
    across the window so every lane's priority mux is verified.
    """

    base = 0x9000
    for lane in range(LANES):
        target = base + 2 * lane
        for action in (ACTION_DEBUG, ACTION_BREAKPOINT):
            await cycle(frontend_trigger,
                  configure(0, Trigger(EQ, action=action, tdata2=target)), base)
            actions = await cycle(frontend_trigger, normal(), base)
            assert actions[lane] == action
            assert all(value == ACTION_NONE for index, value in enumerate(actions) if index != lane)


@pytest.mark.feature("IFU-TR-006")
async def test_actions_are_per_lane(frontend_trigger):
    base = 0x6000
    await cycle(frontend_trigger, configure(0, Trigger(EQ, action=ACTION_DEBUG,
                                                        tdata2=base + 2 * 3), ENABLE01), base)
    await cycle(frontend_trigger, configure(1, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        tdata2=base + 2 * 7), ENABLE01), base)
    actions = await cycle(frontend_trigger, normal(ENABLE01), base)
    assert actions[3] == ACTION_DEBUG and actions[7] == ACTION_BREAKPOINT
    assert sum(action != ACTION_NONE for action in actions) == 2


@pytest.mark.feature("IFU-TR-004")
async def test_pairwise_chain_arms_the_next_trigger(frontend_trigger):
    base = 0x7000
    target = base + 2 * 4
    chained = Trigger(EQ, action=ACTION_DEBUG, chain=1, timing=0, tdata2=target)
    terminal = Trigger(EQ, action=ACTION_BREAKPOINT, chain=0, timing=0, tdata2=target)
    await cycle(frontend_trigger, configure(0, chained, ENABLE01), base)
    await cycle(frontend_trigger, configure(1, terminal, ENABLE01), base)
    assert (await cycle(frontend_trigger, normal(ENABLE01), base))[4] == ACTION_BREAKPOINT
    # This machine's CSR generation ties timing to "before execution" for
    # every trigger, so the timing comparison is constantly satisfied and the
    # interface does not expose a timing input.
    # A miss on the chained trigger also breaks the link.
    await cycle(frontend_trigger, configure(0, Trigger(EQ, action=ACTION_DEBUG, chain=1,
                                                        timing=0, tdata2=base + 2 * 20),
                                             ENABLE01), base)
    await cycle(frontend_trigger, configure(1, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        timing=0, tdata2=target), ENABLE01), base)
    assert (await cycle(frontend_trigger, normal(ENABLE01), base))[4] == ACTION_NONE
    # A chained trigger does not block an independent trigger for the same PC.
    await cycle(frontend_trigger, configure(0, Trigger(EQ, action=ACTION_DEBUG, chain=1,
                                                        timing=0, tdata2=target),
                                             (1, 0, 1, 0)), base)
    await cycle(frontend_trigger, configure(2, Trigger(EQ, action=ACTION_BREAKPOINT,
                                                        timing=0, tdata2=target),
                                             (1, 0, 1, 0)), base)
    assert (await cycle(frontend_trigger, normal((1, 0, 1, 0)), base))[4] == ACTION_BREAKPOINT


@pytest.mark.feature("IFU-TR-007")
async def test_reset_clears_configuration(frontend_trigger):
    base = 0x8000
    target = base + 2 * 6
    await cycle(frontend_trigger, configure(0, Trigger(EQ, action=ACTION_DEBUG,
                                                        tdata2=target)), base)
    assert (await cycle(frontend_trigger, normal(), base))[6] == ACTION_DEBUG
    await frontend_trigger.reset()
    # The enable register is also cleared; one cycle later the new enable is
    # visible but the trigger configuration is still empty.
    assert await cycle(frontend_trigger, normal(), base) == [ACTION_NONE] * LANES
    assert await cycle(frontend_trigger, normal(), base) == [ACTION_NONE] * LANES


@pytest.mark.feature("IFU-TR-003")
async def test_disabled_trigger_ignores_any_tdata2_value(frontend_trigger):
    """A disabled trigger must not act, whatever the 64-bit tdata2 holds.

    This is the enable-gate contract. With the trigger disabled we can also
    exercise arbitrary high tdata2 bits: the result is
    "no action" under both the full-width and the truncated interpretation, so
    the check stays meaningful while the width defect (R-13) is still open.
    """

    base = 0x7000
    rng = random.Random(0x7D15)
    for _ in range(8):
        value = rng.getrandbits(64)
        await cycle(frontend_trigger,
              configure(0, Trigger(EQ, action=ACTION_DEBUG, tdata2=value), (0, 0, 0, 0)), base)
        assert await cycle(frontend_trigger, normal((0, 0, 0, 0)), base) == [ACTION_NONE] * LANES


# ---------------------------------------------------------------------------
# tdata2 width: the producer (CSR) exposes all 64 bits
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-TR-002")
async def test_tdata2_above_the_address_space_cannot_equal_a_fetch_pc(frontend_trigger):
    """tdata2 is a 64-bit RW field; 2**50+pc is not the same address as pc."""

    base = 0x5000
    target = base + 2 * 10
    await cycle(frontend_trigger,
          configure(0, Trigger(EQ, action=ACTION_DEBUG, tdata2=(1 << 50) | target)), base)
    actions = await cycle(frontend_trigger, normal(), base)
    # 2**50 + target is outside the address space, so no fetch PC equals it.
    assert actions == [ACTION_NONE] * LANES


@pytest.mark.feature("IFU-TR-002")
async def test_tdata2_above_the_address_space_is_greater_for_less_than(frontend_trigger):
    """Every implemented PC is less than 2**50, so LT must hit every lane."""

    base = 0x6000
    await cycle(frontend_trigger,
          configure(0, Trigger(LT, action=ACTION_DEBUG, tdata2=(1 << 50))), base)
    actions = await cycle(frontend_trigger, normal(), base)
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
async def test_random_configuration_sequences_match_the_model(frontend_trigger):
    rng = random.Random(0x7A11)
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
                        pcs=consecutive_pcs(0))
        await characterize(frontend_trigger, inputs, base)


@pytest.mark.feature('IFU-TR-001')
@pytest.mark.feature('IFU-TR-003')
async def test_config_and_enable_are_checked_before_and_after_the_same_edge(frontend_trigger):
    pcs = consecutive_pcs(0x4000)
    first = Inputs(Update(1, 0, Trigger(action=ACTION_DEBUG, tdata2=pcs[4])), ENABLE0, pcs=pcs)
    observed = await frontend_trigger.cycle(first)
    assert observed.before.actions == (ACTION_NONE,) * LANES
    assert observed.after.actions[4] == ACTION_DEBUG
    second = replace(first, update=Update(1, 0, Trigger(action=ACTION_DEBUG, tdata2=pcs[7])))
    changed = await frontend_trigger.cycle(second)
    assert changed.before.actions[4] == ACTION_DEBUG and changed.before.actions[7] == ACTION_NONE
    assert changed.after.actions[4] == ACTION_NONE and changed.after.actions[7] == ACTION_DEBUG


@pytest.mark.feature('IFU-TR-007')
async def test_reset_configuration_is_zero_including_the_action_field(frontend_trigger):
    # No tUpdate at all. Reset EQ/PC0/action0 is observable once enabled.
    inputs = Inputs(enable=ENABLE0, pcs=consecutive_pcs(0))
    enabled = await frontend_trigger.cycle(inputs)
    assert enabled.before.actions == (ACTION_NONE,) * LANES
    assert enabled.after.actions == (ACTION_BREAKPOINT,) + (ACTION_NONE,) * (LANES - 1)
    await frontend_trigger.reset()
    again = await frontend_trigger.cycle(inputs)
    assert again.before.actions == enabled.before.actions and again.after.actions == enabled.after.actions


@pytest.mark.feature('IFU-TR-003')
@pytest.mark.feature('IFU-TR-005')
async def test_debug_and_breakpoint_permission_are_live_not_delayed(frontend_trigger):
    pcs = consecutive_pcs(0x6000)
    inputs = Inputs(Update(1, 0, Trigger(action=ACTION_BREAKPOINT, tdata2=pcs[3])), ENABLE0, pcs=pcs)
    await frontend_trigger.cycle(inputs)
    quiet = await frontend_trigger.cycle(replace(inputs, update=Update(), can_raise_breakpoint=0))
    assert quiet.before.actions == quiet.after.actions == (ACTION_NONE,) * LANES
    await frontend_trigger.cycle(replace(inputs, update=Update(1, 0, Trigger(action=ACTION_DEBUG, tdata2=pcs[3]))))
    quiet = await frontend_trigger.cycle(replace(inputs, update=Update(), debug_mode=1))
    assert quiet.before.actions == quiet.after.actions == (ACTION_NONE,) * LANES
    active = await frontend_trigger.cycle(replace(inputs, update=Update()))
    assert active.before.actions[3] == active.after.actions[3] == ACTION_DEBUG


@pytest.mark.feature('IFU-TR-002')
@pytest.mark.feature('IFU-TR-006')
async def test_lane_pcs_need_not_form_a_dense_consecutive_sequence(frontend_trigger):
    # Mixed-width instruction coordinates plus repeated unused lane PCs, all
    # within a single64-byte fetch span crossing the128-byte comparison split.
    pcs = tuple(0x1FF0 + 2 * min(lane + lane // 3, 31) for lane in range(LANES))
    for relation in (EQ, GE, LT):
        configured = Inputs(Update(1, 0, Trigger(relation, action=ACTION_DEBUG, tdata2=0x2000)),
                            ENABLE0, pcs=pcs)
        await frontend_trigger.cycle(configured)
        observed = await frontend_trigger.cycle(replace(configured, update=Update()))
        expected = tuple(ACTION_DEBUG if {EQ: pc == 0x2000, GE: pc >= 0x2000, LT: pc < 0x2000}[relation]
                         else ACTION_NONE for pc in pcs)
        assert observed.before.actions == observed.after.actions == expected


@pytest.mark.feature('IFU-TR-004')
async def test_last_slot_chain_bit_is_csr_reachable_but_has_no_successor(frontend_trigger):
    # Debug.scala/TriggerUtil checks adjacent1 bits. It does not force chain[3]
    # to0, so the producer domain must not reject this legal uncompleted link.
    inputs = Inputs(Update(1, 3, Trigger(action=ACTION_DEBUG, chain=1, tdata2=0x4008)),
                    (0, 0, 0, 1), pcs=consecutive_pcs(0x4000))
    updated = await frontend_trigger.cycle(inputs)
    held = await frontend_trigger.cycle(replace(inputs, update=Update()))
    assert updated.after.actions == held.before.actions == held.after.actions == (ACTION_NONE,) * LANES
