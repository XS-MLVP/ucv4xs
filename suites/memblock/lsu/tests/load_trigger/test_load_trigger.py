"""MemTrigger (load) UT: load address trigger matching."""
from __future__ import annotations

import random

import pytest

from lsuverify.load_trigger.coverage import CASES, LoadTriggerCoverage
from lsuverify.load_trigger.env import (
    LoadTriggerEnv,
    independent_configs,
    reference_action,
)
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
    TriggerConfig,
)

VADDR = 0x0000_2468_ACE0


@pytest.fixture
def trig(dut_factory):
    dut = dut_factory("load_trigger")
    return LoadTriggerEnv(dut, LoadTriggerCoverage())


def only(slot, cfg):
    configs = [TriggerConfig(action=ACTION_CODE_DEBUG, tdata2=0) for _ in range(TRIGGER_NUM)]
    configs[slot] = cfg
    return configs


def run(trig, configs, vaddr=VADDR, mask=0xFFFF, is_vector_stride=False, is_prf=0,
        debug_mode=0, can_raise_bp=1, enables=None, context="case"):
    enables = enables if enables is not None else [1] * TRIGGER_NUM
    trig.drive(configs, enables, vaddr, mask, is_vector_stride, is_prf,
               debug_mode, can_raise_bp)
    trig.eval()
    return trig.check(context, configs, enables, vaddr, mask, is_vector_stride,
                      is_prf, debug_mode, can_raise_bp)


@pytest.mark.parametrize("match_type,case", [
    (MATCH_EQ, "eq"), (MATCH_GE, "ge"), (MATCH_LT, "lt"),
])
def test_scalar_comparisons_include_their_boundaries(trig, match_type, case):
    cfg = TriggerConfig(match_type=match_type, tdata2=VADDR)
    if match_type == MATCH_EQ:
        assert run(trig, only(0, cfg)) == ACTION_DEBUG
        trig.coverage.sample_case("scalar.eq_hit")
        assert run(trig, only(0, cfg), vaddr=VADDR + 1) == ACTION_NONE
        trig.coverage.sample_case("scalar.eq_miss")
    elif match_type == MATCH_GE:
        assert run(trig, only(0, cfg), vaddr=VADDR) == ACTION_DEBUG
        assert run(trig, only(0, cfg), vaddr=VADDR + 1) == ACTION_DEBUG
        trig.coverage.sample_case("scalar.ge_hit")
        assert run(trig, only(0, cfg), vaddr=VADDR - 1) == ACTION_NONE
        trig.coverage.sample_case("scalar.ge_miss")
    else:
        assert run(trig, only(0, cfg), vaddr=VADDR - 1) == ACTION_DEBUG
        trig.coverage.sample_case("scalar.lt_hit")
        assert run(trig, only(0, cfg), vaddr=VADDR) == ACTION_NONE
        trig.coverage.sample_case("scalar.lt_miss")


def test_napot_is_not_implemented(trig):
    cfg = TriggerConfig(match_type=MATCH_NAPOT, tdata2=VADDR)
    assert run(trig, only(0, cfg)) == ACTION_NONE
    trig.coverage.sample_case("scalar.napot_rejected")


def test_vector_unit_stride_uses_high_bits_and_mask(trig):
    start = 0x6
    cfg = TriggerConfig(match_type=MATCH_EQ, tdata2=(VADDR & ~0xF) | start)
    assert run(trig, only(0, cfg), vaddr=VADDR, mask=1 << start,
               is_vector_stride=True) == ACTION_DEBUG
    trig.coverage.sample_case("vector.mask_hit")
    assert run(trig, only(0, cfg), vaddr=VADDR, mask=0, is_vector_stride=True) == ACTION_NONE
    trig.coverage.sample_case("vector.mask_miss")
    # matchType is ignored in vector mode: LT would fail in scalar mode.
    lt_cfg = TriggerConfig(match_type=MATCH_LT, tdata2=(VADDR & ~0xF) | start)
    assert run(trig, only(0, lt_cfg), vaddr=VADDR, mask=1 << start,
               is_vector_stride=True) == ACTION_DEBUG
    trig.coverage.sample_case("vector.ignores_matchtype")


@pytest.mark.parametrize("gate,case", [
    ("load", "gate.load_bit"), ("select", "gate.select"),
    ("debug_mode", "gate.debug_mode"), ("t_enable", "gate.t_enable"),
])
def test_each_precondition_suppresses_a_matching_address(trig, gate, case):
    base = dict(match_type=MATCH_EQ, tdata2=VADDR)
    assert run(trig, only(0, TriggerConfig(**base))) == ACTION_DEBUG
    if gate == "load":
        assert run(trig, only(0, TriggerConfig(store=0, **base))) == ACTION_NONE
    elif gate == "select":
        assert run(trig, only(0, TriggerConfig(select=1, **base))) == ACTION_NONE
    elif gate == "debug_mode":
        assert run(trig, only(0, TriggerConfig(**base)), debug_mode=1) == ACTION_NONE
    else:
        assert run(trig, only(0, TriggerConfig(**base)),
                   enables=[0, 1, 1, 1]) == ACTION_NONE
    trig.coverage.sample_case(case)


def test_prefetch_suppresses_the_scalar_path_only(trig):
    cfg = only(0, TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR))
    assert run(trig, cfg, is_prf=1) == ACTION_NONE
    trig.coverage.sample_case("prf.suppresses_scalar")
    vec = only(0, TriggerConfig(match_type=MATCH_EQ, tdata2=(VADDR & ~0xF) | 0x3))
    assert run(trig, vec, mask=1 << 3, is_vector_stride=True, is_prf=1) == ACTION_DEBUG
    trig.coverage.sample_case("prf.does_not_suppress_vector")


def test_chain_and_timing(trig):
    start = only(0, TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, chain=1))
    assert run(trig, start) == ACTION_NONE
    trig.coverage.sample_case("chain.start_does_not_fire")
    cont = [TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, chain=1, timing=0,
                          action=ACTION_CODE_DEBUG),
            TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, chain=0, timing=0,
                          action=ACTION_CODE_DEBUG),
            TriggerConfig(), TriggerConfig()]
    assert run(trig, cont) == ACTION_DEBUG
    trig.coverage.sample_case("chain.continue_fires")
    broken = [cont[0].clone(tdata2=VADDR + 1), cont[1], TriggerConfig(), TriggerConfig()]
    assert run(trig, broken) == ACTION_NONE
    trig.coverage.sample_case("chain.broken_by_previous_miss")
    mismatched = [cont[0].clone(timing=1), cont[1], TriggerConfig(), TriggerConfig()]
    assert run(trig, mismatched) == ACTION_NONE
    trig.coverage.sample_case("chain.timing_mismatch")


def test_action_selection_and_priority(trig):
    debug = only(0, TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR,
                                  action=ACTION_CODE_DEBUG))
    for allowed in (1, 0):
        assert run(trig, debug, can_raise_bp=allowed) == ACTION_DEBUG
    trig.coverage.sample_case("action.debug_ignores_bp_exp")
    bp = only(0, TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR,
                               action=ACTION_CODE_BREAKPOINT))
    assert run(trig, bp, can_raise_bp=1) == ACTION_BREAKPOINT
    trig.coverage.sample_case("action.breakpoint_allowed")
    assert run(trig, bp, can_raise_bp=0) == ACTION_NONE
    trig.coverage.sample_case("action.breakpoint_blocked")
    for code in (2, 3, 4, 15):
        assert run(trig, only(0, TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR,
                                               action=code))) == ACTION_NONE
    trig.coverage.sample_case("action.other_encoding_none")
    both = [TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, action=ACTION_CODE_DEBUG),
            TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR, action=ACTION_CODE_BREAKPOINT),
            TriggerConfig(), TriggerConfig()]
    assert run(trig, both) == ACTION_DEBUG
    both[0], both[1] = both[1], both[0]
    assert run(trig, both) == ACTION_DEBUG
    trig.coverage.sample_case("priority.debug_over_breakpoint")


@pytest.mark.parametrize("slot", range(TRIGGER_NUM))
def test_each_slot_independently_produces_action(trig, slot):
    cfg = only(slot, TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR,
                                   action=ACTION_CODE_DEBUG))
    assert run(trig, cfg) == ACTION_DEBUG
    enables = [1] * TRIGGER_NUM
    enables[slot] = 0
    assert run(trig, cfg, enables=enables) == ACTION_NONE
    trig.coverage.sample_case(f"multi.slot{slot}_only")


def test_cbo_branch_is_absent(trig):
    """The load variant has no CBO mode: a cache-line-aligned comparison with
    matchType EQ only hits the exact address, never the whole line."""
    line = VADDR & ~0x3F
    cfg = only(0, TriggerConfig(match_type=MATCH_EQ, tdata2=line))
    assert run(trig, cfg, vaddr=line) == ACTION_DEBUG
    assert run(trig, cfg, vaddr=line + 8) == ACTION_NONE
    trig.coverage.sample_case("cbo.branch_absent")


def test_trigger_tdata2_full_width_for_every_slot(trig):
    for slot in range(TRIGGER_NUM):
        for bit in range(64):
            cfg = only(slot, TriggerConfig(match_type=MATCH_EQ, tdata2=1 << bit,
                                           action=ACTION_CODE_DEBUG))
            run(trig, cfg, vaddr=0, context=f"tdata2 slot{slot} bit{bit}")
        run(trig, only(slot, TriggerConfig(match_type=MATCH_EQ, tdata2=0)), vaddr=0,
            context=f"tdata2 slot{slot} clear")


def test_vaddr_and_mask_full_width(trig):
    cfg = only(0, TriggerConfig(match_type=MATCH_EQ, tdata2=0))
    for bit in range(50):
        run(trig, cfg, vaddr=1 << bit, context=f"vaddr bit{bit}")
    run(trig, cfg, vaddr=0, context="vaddr clear")
    for bit in range(16):
        run(trig, cfg, vaddr=0, mask=1 << bit, is_vector_stride=True,
            context=f"mask bit{bit}")
    run(trig, cfg, vaddr=0, mask=0, is_vector_stride=True, context="mask clear")


def test_seeded_random_configurations(trig):
    rng = random.Random(20261025)
    for beat in range(400):
        configs = independent_configs(rng)
        enables = [1 if rng.random() < 0.8 else 0 for _ in range(TRIGGER_NUM)]
        run(trig, configs, vaddr=rng.randrange(1 << 50), mask=rng.randrange(1 << 16),
            is_vector_stride=rng.random() < 0.3, is_prf=1 if rng.random() < 0.1 else 0,
            debug_mode=1 if rng.random() < 0.05 else 0,
            can_raise_bp=1 if rng.random() < 0.7 else 0, enables=enables,
            context=f"random {beat}")


def test_case_inventory_is_exact():
    assert len(CASES) == len(set(CASES))
    assert len(CASES) == 30
