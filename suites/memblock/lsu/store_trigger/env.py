"""Port-level environment and independent reference for MemTrigger_3.

The reference restates the contract relation (match mode, per-trigger
predicate, chain/timing rule, action priority) in Python. It does not reuse the
RTL ternary tree; the address comparators are written as plain comparisons and
the chain rule is a loop over the four trigger slots.

Contract: docs/contracts/store-trigger.md
"""
from __future__ import annotations

import random

TRIGGER_NUM = 4

ACTION_NONE = 0xF
ACTION_BREAKPOINT = 0x0
ACTION_DEBUG = 0x1

# TrigMatchEnum (Trigger.scala:157-166)
MATCH_EQ = 0
MATCH_NAPOT = 1
MATCH_GE = 2
MATCH_LT = 3

# TriggerAction encodings (Bundle.scala:762-774)
ACTION_CODE_DEBUG = 1
ACTION_CODE_BREAKPOINT = 0
ACTION_CODES_OTHERS = (2, 3, 4, 15)

VADDR_BITS = 50
DCACHE_LINE_BITS = 6   # vaddr[5:0]
VWORD_BITS = 4         # vaddr[3:0]


class TriggerConfig:
    """One trigger slot as seen at the CSR interface."""

    __slots__ = ("match_type", "select", "timing", "action", "chain", "store",
                 "tdata2")

    def __init__(self, match_type=MATCH_EQ, select=0, timing=0, action=ACTION_CODE_DEBUG,
                 chain=0, store=1, tdata2=0):
        self.match_type = match_type
        self.select = select
        self.timing = timing
        self.action = action
        self.chain = chain
        self.store = store
        self.tdata2 = tdata2

    def clone(self, **changes):
        cfg = TriggerConfig(self.match_type, self.select, self.timing, self.action,
                            self.chain, self.store, self.tdata2)
        for name, value in changes.items():
            setattr(cfg, name, value)
        return cfg


def _enabled(cfg: TriggerConfig, debug_mode: int) -> bool:
    return not cfg.select and not debug_mode and bool(cfg.store)


def _scalar_hit(cfg: TriggerConfig, vaddr: int) -> bool:
    value = cfg.tdata2 & ((1 << VADDR_BITS) - 1)
    if cfg.match_type == MATCH_EQ:
        return vaddr == value
    if cfg.match_type == MATCH_GE:
        return vaddr >= value
    if cfg.match_type == MATCH_LT:
        return vaddr < value
    # NAPOT / MASK_* / reserved encodings are not implemented by this build.
    return False


def _cbo_hit_exact(cfg: TriggerConfig, vaddr: int) -> bool:
    # tdata2[63:6] is compared against a 44-bit vaddr[49:6] zero-extended.
    return (vaddr >> DCACHE_LINE_BITS) == (cfg.tdata2 >> DCACHE_LINE_BITS)


def _vector_hit(cfg: TriggerConfig, vaddr: int, mask: int) -> bool:
    if (vaddr >> VWORD_BITS) != (cfg.tdata2 >> VWORD_BITS):
        return False
    return bool(mask & (1 << (cfg.tdata2 & ((1 << VWORD_BITS) - 1))))


def slot_hit(cfg: TriggerConfig, vaddr: int, mask: int, is_cbo: bool,
             is_vector_stride: bool, debug_mode: int, enable: int) -> bool:
    """Per-slot address predicate, including every common precondition."""
    if not enable or not _enabled(cfg, debug_mode):
        return False
    if is_cbo:
        return _cbo_hit_exact(cfg, vaddr)
    if is_vector_stride:
        return _vector_hit(cfg, vaddr, mask)
    return _scalar_hit(cfg, vaddr)


def chain_fire(hit: list[bool], chain: list[int], timing: list[int]) -> list[bool]:
    """TriggerCheckCanFire relation, written as a forward recurrence."""
    can_fire = [False] * TRIGGER_NUM
    can_fire[0] = hit[0] and not chain[0]
    for index in range(1, TRIGGER_NUM):
        prev_chain = chain[index - 1]
        chain_ok = (hit[index - 1] if prev_chain else True)
        timing_ok = (timing[index - 1] == timing[index]) if prev_chain else True
        can_fire[index] = (chain_ok and timing_ok and hit[index] and not chain[index])
    return can_fire


def reference_action(configs: list[TriggerConfig], vaddr: int, mask: int,
                     is_cbo: bool, is_vector_stride: bool, debug_mode: int,
                     enables: list[int], can_raise_bp_exp: int) -> int:
    hits = [slot_hit(cfg, vaddr, mask, is_cbo, is_vector_stride, debug_mode, enables[i])
            for i, cfg in enumerate(configs)]
    fires = chain_fire(hits, [cfg.chain for cfg in configs],
                       [cfg.timing for cfg in configs])
    debug_hit = any(fire and cfg.action == ACTION_CODE_DEBUG
                    for fire, cfg in zip(fires, configs))
    bp_hit = any(fire and cfg.action == ACTION_CODE_BREAKPOINT
                 for fire, cfg in zip(fires, configs))
    if debug_hit:
        return ACTION_DEBUG
    if bp_hit and can_raise_bp_exp:
        return ACTION_BREAKPOINT
    return ACTION_NONE


class StoreTriggerEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        prefix = "tdataVec_io_fromCsrTrigger_tdataVec_"
        self.cfg_signals = []
        for index in range(TRIGGER_NUM):
            self.cfg_signals.append({
                "match_type": getattr(dut, f"{prefix}{index}_matchType"),
                "select": getattr(dut, f"{prefix}{index}_select"),
                "timing": getattr(dut, f"{prefix}{index}_timing"),
                "action": getattr(dut, f"{prefix}{index}_action"),
                "chain": getattr(dut, f"{prefix}{index}_chain"),
                "store": getattr(dut, f"{prefix}{index}_store"),
                "tdata2": getattr(dut, f"{prefix}{index}_tdata2"),
            })
        self.enable = [getattr(dut, f"tdataVec_io_fromCsrTrigger_tEnableVec_{index}")
                       for index in range(TRIGGER_NUM)]
        self.debug_mode = dut.tdataVec_io_fromCsrTrigger_debugMode
        self.can_raise_bp = dut.tdataVec_io_fromCsrTrigger_triggerCanRaiseBpExp
        self.vaddr = dut.tdataVec_io_fromLoadStore_vaddr
        self.is_vector_stride = dut.tdataVec_io_fromLoadStore_isVectorUnitStride
        self.mask = dut.tdataVec_io_fromLoadStore_mask
        self.is_cbo = dut.tdataVec_io_isCbo
        self.action = dut.tdataVec_io_toLoadStore_triggerAction
        self.vectors = 0

    def drive(self, configs: list[TriggerConfig], enables: list[int], vaddr: int,
              mask: int, is_cbo: bool, is_vector_stride: bool, debug_mode: int,
              can_raise_bp_exp: int) -> None:
        for index, cfg in enumerate(configs):
            signals = self.cfg_signals[index]
            signals["match_type"].Set(cfg.match_type)
            signals["select"].Set(cfg.select)
            signals["timing"].Set(cfg.timing)
            signals["action"].Set(cfg.action)
            signals["chain"].Set(cfg.chain)
            signals["store"].Set(cfg.store)
            signals["tdata2"].Set(cfg.tdata2 & ((1 << 64) - 1))
            self.enable[index].Set(1 if enables[index] else 0)
        self.debug_mode.Set(1 if debug_mode else 0)
        self.can_raise_bp.Set(1 if can_raise_bp_exp else 0)
        self.vaddr.Set(vaddr & ((1 << VADDR_BITS) - 1))
        self.is_vector_stride.Set(1 if is_vector_stride else 0)
        self.mask.Set(mask & 0xFFFF)
        self.is_cbo.Set(1 if is_cbo else 0)

    def eval(self) -> None:
        self.dut.Step(1)

    def check(self, context: str, configs: list[TriggerConfig], enables: list[int],
              vaddr: int, mask: int, is_cbo: bool, is_vector_stride: bool,
              debug_mode: int, can_raise_bp_exp: int) -> int:
        want = reference_action(configs, vaddr, mask, is_cbo, is_vector_stride,
                                debug_mode, enables, can_raise_bp_exp)
        got = int(self.action.value)
        if got != want:
            raise AssertionError(
                f"{context}: triggerAction {got:#x} != {want:#x} "
                f"(vaddr={vaddr:#x} cbo={int(is_cbo)} vec={int(is_vector_stride)} "
                f"debug={int(debug_mode)} bpExp={int(can_raise_bp_exp)} "
                f"enables={enables})")
        self.vectors += 1
        if self.coverage is not None:
            hits = [slot_hit(cfg, vaddr, mask, is_cbo, is_vector_stride, debug_mode,
                             enables[i]) for i, cfg in enumerate(configs)]
            self.coverage.observe(
                configs=configs, enables=enables, vaddr=vaddr, mask=mask,
                is_cbo=is_cbo, is_vector_stride=is_vector_stride,
                debug_mode=debug_mode, can_raise_bp_exp=can_raise_bp_exp,
                hits=hits, action=got)
        return got


def independent_configs(rng: random.Random) -> list[TriggerConfig]:
    return [
        TriggerConfig(
            match_type=rng.choice([MATCH_EQ, MATCH_GE, MATCH_LT, MATCH_NAPOT]),
            select=1 if rng.random() < 0.1 else 0,
            timing=rng.randrange(2),
            action=rng.choice([ACTION_CODE_DEBUG, ACTION_CODE_BREAKPOINT,
                               *ACTION_CODES_OTHERS]),
            chain=1 if rng.random() < 0.3 else 0,
            store=1 if rng.random() < 0.85 else 0,
            tdata2=rng.randrange(1 << VADDR_BITS),
        )
        for _ in range(TRIGGER_NUM)
    ]
