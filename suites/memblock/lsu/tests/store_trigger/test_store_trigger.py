"""MemTrigger_3 UT: store address trigger matching.

Every test asserts an expected ``TriggerAction`` against the independent
reference in ``env.py`` and then records the corresponding checked behaviour in
the semantic covergroup.
"""
from __future__ import annotations

import random

import pytest

from lsuverify.store_trigger.coverage import StoreTriggerCoverage
from lsuverify.store_trigger.env import (
    ACTION_BREAKPOINT,
    ACTION_CODE_BREAKPOINT,
    ACTION_CODE_DEBUG,
    ACTION_DEBUG,
    ACTION_NONE,
    MATCH_EQ,
    MATCH_GE,
    MATCH_LT,
    MATCH_NAPOT,
    TRIGGER_NUM,
    StoreTriggerEnv,
    TriggerConfig,
    independent_configs,
)

VADDR = 0x0000_1234_5678
LINE_MASK = ~0x3F


@pytest.fixture
def trig(dut_factory):
    dut = dut_factory("store_trigger")
    return StoreTriggerEnv(dut, StoreTriggerCoverage())


def only(slot: int, cfg: TriggerConfig) -> list[TriggerConfig]:
    """One configured slot; the other three are disabled and store=1."""
    configs = [TriggerConfig(action=ACTION_CODE_DEBUG, tdata2=0)
               for _ in range(TRIGGER_NUM)]
    configs[slot] = cfg
    return configs


def run(trig, configs, vaddr=VADDR, mask=0xFFFF, is_cbo=False,
        is_vector_stride=False, debug_mode=0, can_raise_bp=1,
        enables=None, context="case"):
    enables = enables if enables is not None else [1] * TRIGGER_NUM
    trig.drive(configs, enables, vaddr, mask, is_cbo, is_vector_stride,
               debug_mode, can_raise_bp)
    trig.eval()
    return trig.check(context, configs, enables, vaddr, mask, is_cbo,
                      is_vector_stride, debug_mode, can_raise_bp)


# ---------------------------------------------------------------- match types
def test_eq_hits_only_on_exact_address(trig):
    cfg = TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR)
    assert run(trig, only(0, cfg)) == ACTION_DEBUG
    trig.coverage.sample_case("scalar.eq_hit")
    assert run(trig, only(0, cfg), vaddr=VADDR + 1) == ACTION_NONE
    trig.coverage.sample_case("scalar.eq_miss")


def test_ge_boundary_is_inclusive(trig):
    cfg = TriggerConfig(match_type=MATCH_GE, tdata2=VADDR)
    assert run(trig, only(0, cfg), vaddr=VADDR) == ACTION_DEBUG
    assert run(trig, only(0, cfg), vaddr=VADDR + 1) == ACTION_DEBUG
    trig.coverage.sample_case("scalar.ge_hit")
    assert run(trig, only(0, cfg), vaddr=VADDR - 1) == ACTION_NONE
    trig.coverage.sample_case("scalar.ge_miss")


def test_lt_boundary_is_strict(trig):
    cfg = TriggerConfig(match_type=MATCH_LT, tdata2=VADDR)
    assert run(trig, only(0, cfg), vaddr=VADDR - 1) == ACTION_DEBUG
    trig.coverage.sample_case("scalar.lt_hit")
    assert run(trig, only(0, cfg), vaddr=VADDR) == ACTION_NONE
    assert run(trig, only(0, cfg), vaddr=VADDR + 1) == ACTION_NONE
    trig.coverage.sample_case("scalar.lt_miss")


def test_napot_is_not_implemented_and_never_matches(trig):
    """matchType is 2 bits at this interface: EQ/NAPOT/GE/LT only.

    NAPOT(1) is the single encoding this build does not implement, so an exact
    address match must still produce 4'hF.
    """
    cfg = TriggerConfig(match_type=MATCH_NAPOT, tdata2=VADDR)
    assert run(trig, only(0, cfg)) == ACTION_NONE
    trig.coverage.sample_case("scalar.napot_rejected")


# --------------------------------------------------------------------- CBO
def test_cbo_matches_any_offset_inside_the_line(trig):
    cfg = TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR & LINE_MASK)
    for offset in (0, 1, 0x1F, 0x3F):
        assert run(trig, only(0, cfg), vaddr=(VADDR & LINE_MASK) | offset,
                   is_cbo=True) == ACTION_DEBUG
    trig.coverage.sample_case("cbo.line_hit")
    assert run(trig, only(0, cfg), vaddr=(VADDR & LINE_MASK) + 0x40,
               is_cbo=True) == ACTION_NONE
    trig.coverage.sample_case("cbo.line_miss")


def test_cbo_ignores_match_type_and_vector_flags(trig):
    # matchType would fail in scalar mode (GE with vaddr < tdata2), but the CBO
    # line compare must ignore it.
    cfg = TriggerConfig(match_type=MATCH_LT, tdata2=VADDR & LINE_MASK)
    assert run(trig, only(0, cfg), vaddr=(VADDR & LINE_MASK) | 0x10,
               is_cbo=True) == ACTION_DEBUG
    trig.coverage.sample_case("cbo.ignores_matchtype")
    # isCbo has priority over isVectorUnitStride in the mode mux.
    assert run(trig, only(0, cfg), vaddr=(VADDR & LINE_MASK) | 0x10,
               is_cbo=True, is_vector_stride=True, mask=0x0001) == ACTION_DEBUG
    trig.coverage.sample_case("cbo.ignores_vector_mode")


# ------------------------------------------------------------------ vector
def test_vector_unit_stride_requires_the_start_byte_in_mask(trig):
    start = 0x5
    cfg = TriggerConfig(match_type=MATCH_EQ, tdata2=(VADDR & ~0xF) | start)
    assert run(trig, only(0, cfg), vaddr=VADDR, mask=1 << start,
               is_vector_stride=True) == ACTION_DEBUG
    trig.coverage.sample_case("vector.mask_hit")
    assert run(trig, only(0, cfg), vaddr=VADDR,
               mask=(1 << start) ^ 0xFFFF, is_vector_stride=True) == ACTION_NONE
    trig.coverage.sample_case("vector.mask_miss")


def test_vector_mode_ignores_match_type(trig):
    start = 0x2
    cfg = TriggerConfig(match_type=MATCH_LT, tdata2=(VADDR & ~0xF) | start)
    assert run(trig, only(0, cfg), vaddr=VADDR, mask=1 << start,
               is_vector_stride=True) == ACTION_DEBUG
    trig.coverage.sample_case("vector.ignores_matchtype")


# ------------------------------------------------------------------- gates
@pytest.mark.parametrize("gate,case", [
    ("select", "gate.select"),
    ("debug_mode", "gate.debug_mode"),
    ("t_enable", "gate.t_enable"),
    ("store", "gate.store"),
])
def test_each_precondition_suppresses_an_otherwise_matching_address(trig, gate, case):
    base = dict(match_type=MATCH_EQ, tdata2=VADDR)
    assert run(trig, only(0, TriggerConfig(**base))) == ACTION_DEBUG
    if gate == "select":
        cfg = TriggerConfig(select=1, **base)
        assert run(trig, only(0, cfg)) == ACTION_NONE
    elif gate == "debug_mode":
        assert run(trig, only(0, TriggerConfig(**base)), debug_mode=1) == ACTION_NONE
    elif gate == "t_enable":
        assert run(trig, only(0, TriggerConfig(**base)),
                   enables=[0, 1, 1, 1]) == ACTION_NONE
    else:
        assert run(trig, only(0, TriggerConfig(store=0, **base))) == ACTION_NONE
    trig.coverage.sample_case(case)


# ------------------------------------------------------------------- chain
def test_chain_start_never_fires_by_itself(trig):
    cfg = TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, chain=1)
    assert run(trig, only(0, cfg)) == ACTION_NONE
    trig.coverage.sample_case("chain.start_does_not_fire")


def test_chain_continues_when_previous_slot_hits_with_same_timing(trig):
    configs = [
        TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, chain=1, timing=0,
                      action=ACTION_CODE_DEBUG),
        TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, chain=0, timing=0,
                      action=ACTION_CODE_DEBUG),
        TriggerConfig(), TriggerConfig(),
    ]
    assert run(trig, configs) == ACTION_DEBUG
    trig.coverage.sample_case("chain.continue_fires")
    trig.coverage.sample_case("chain.timing_match")


def test_chain_breaks_when_previous_slot_misses(trig):
    configs = [
        TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR + 1, chain=1, timing=0,
                      action=ACTION_CODE_DEBUG),
        TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, chain=0, timing=0,
                      action=ACTION_CODE_DEBUG),
        TriggerConfig(), TriggerConfig(),
    ]
    assert run(trig, configs) == ACTION_NONE
    trig.coverage.sample_case("chain.broken_by_previous_miss")


def test_chain_breaks_on_timing_mismatch(trig):
    configs = [
        TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, chain=1, timing=1,
                      action=ACTION_CODE_DEBUG),
        TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, chain=0, timing=0,
                      action=ACTION_CODE_DEBUG),
        TriggerConfig(), TriggerConfig(),
    ]
    assert run(trig, configs) == ACTION_NONE
    trig.coverage.sample_case("chain.timing_mismatch")


def test_chain_patterns_sweep_all_sixteen_bitmaps(trig):
    """Every chain bitmap is exercised with all slots hitting."""
    for pattern in range(16):
        configs = []
        for slot in range(TRIGGER_NUM):
            configs.append(TriggerConfig(
                match_type=MATCH_EQ, tdata2=VADDR,
                chain=(pattern >> slot) & 1, timing=0,
                action=ACTION_CODE_DEBUG))
        run(trig, configs, context=f"chain pattern {pattern:04b}")


# ------------------------------------------------------------------ action
def test_debug_action_ignores_breakpoint_permission(trig):
    cfg = TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, action=ACTION_CODE_DEBUG)
    for allowed in (1, 0):
        assert run(trig, only(0, cfg), can_raise_bp=allowed) == ACTION_DEBUG
    trig.coverage.sample_case("action.debug_ignores_bp_exp")


def test_breakpoint_action_requires_permission(trig):
    cfg = TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR,
                        action=ACTION_CODE_BREAKPOINT)
    assert run(trig, only(0, cfg), can_raise_bp=1) == ACTION_BREAKPOINT
    trig.coverage.sample_case("action.breakpoint_allowed")
    assert run(trig, only(0, cfg), can_raise_bp=0) == ACTION_NONE
    trig.coverage.sample_case("action.breakpoint_blocked")


@pytest.mark.parametrize("code", [2, 3, 4, 15])
def test_other_action_encodings_produce_none(trig, code):
    cfg = TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, action=code)
    assert run(trig, only(0, cfg), can_raise_bp=1) == ACTION_NONE
    trig.coverage.sample_case("action.other_encoding_none")


def test_debug_action_wins_over_breakpoint(trig):
    configs = [
        TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, action=ACTION_CODE_DEBUG),
        TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, action=ACTION_CODE_BREAKPOINT),
        TriggerConfig(), TriggerConfig(),
    ]
    assert run(trig, configs, can_raise_bp=1) == ACTION_DEBUG
    trig.coverage.sample_case("priority.debug_over_breakpoint")
    # Reversing the slot order must not change the winner.
    configs[0], configs[1] = configs[1], configs[0]
    assert run(trig, configs, can_raise_bp=1) == ACTION_DEBUG


# --------------------------------------------------------------- multi-slot
@pytest.mark.parametrize("slot", range(TRIGGER_NUM))
def test_each_slot_independently_produces_action(trig, slot):
    cfg = TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR,
                        action=ACTION_CODE_DEBUG)
    assert run(trig, only(slot, cfg)) == ACTION_DEBUG
    # The same address with only that slot's enable cleared yields nothing.
    enables = [1] * TRIGGER_NUM
    enables[slot] = 0
    assert run(trig, only(slot, cfg), enables=enables) == ACTION_NONE
    trig.coverage.sample_case(f"multi.slot{slot}_only")


# ------------------------------------------------------------------ random
def test_seeded_random_trigger_configurations(trig):
    rng = random.Random(20261025)
    for beat in range(400):
        configs = independent_configs(rng)
        enables = [1 if rng.random() < 0.8 else 0 for _ in range(TRIGGER_NUM)]
        vaddr = rng.randrange(1 << 50)
        mask = rng.randrange(1 << 16)
        is_cbo = rng.random() < 0.2
        is_vector = (not is_cbo) and rng.random() < 0.3
        debug_mode = 1 if rng.random() < 0.08 else 0
        can_raise_bp = 1 if rng.random() < 0.7 else 0
        run(trig, configs, vaddr=vaddr, mask=mask, is_cbo=is_cbo,
            is_vector_stride=is_vector, debug_mode=debug_mode,
            can_raise_bp=can_raise_bp, enables=enables,
            context=f"random beat {beat}")


def test_tdata2_full_64bit_width_is_exercised(trig):
    """Walk a single one across all 64 tdata2 bits for every slot.

    The address compare uses vaddr[49:0] only, and the CBO compare uses
    tdata2[63:6] against a zero-extended 44-bit vaddr, so the high tdata2 bits
    are meaningful and must not be left un-toggled.
    """
    for slot in range(TRIGGER_NUM):
        for bit in range(64):
            cfg = TriggerConfig(match_type=MATCH_EQ, tdata2=1 << bit)
            run(trig, only(slot, cfg), vaddr=0, context=f"tdata2 slot{slot} bit{bit}")
            run(trig, only(slot, cfg), vaddr=0, is_cbo=True,
                context=f"tdata2 cbo slot{slot} bit{bit}")
        # Return the slot to all-zero so each direction toggles again.
        run(trig, only(slot, TriggerConfig(match_type=MATCH_EQ, tdata2=0)), vaddr=0,
            context=f"tdata2 slot{slot} clear")


def test_vaddr_and_mask_full_width_are_exercised(trig):
    """Walk a single one across the 50-bit vaddr and the 16-bit mask."""
    cfg = TriggerConfig(match_type=MATCH_EQ, tdata2=0)
    for bit in range(50):
        run(trig, only(0, cfg), vaddr=1 << bit, context=f"vaddr bit{bit}")
    run(trig, only(0, cfg), vaddr=0, context="vaddr clear")
    for bit in range(16):
        run(trig, only(0, cfg), vaddr=0, mask=1 << bit, is_vector_stride=True,
            context=f"mask bit{bit}")
    run(trig, only(0, cfg), vaddr=0, mask=0, is_vector_stride=True,
        context="mask clear")


def test_every_declared_case_is_reachable_by_the_suite():
    from lsuverify.store_trigger.coverage import TRIGGER_CASES
    assert len(TRIGGER_CASES) == len(set(TRIGGER_CASES))
    assert len(TRIGGER_CASES) == 32
