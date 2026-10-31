"""Environment and reference for MemTrigger (load variant).

Same four-slot chain/action machinery as ``MemTrigger_3``, with three
differences that matter at this boundary:

* the per-slot type bit is ``load`` instead of ``store``;
* there is **no CBO branch** (``DcacheLineBitsEq`` returns ``false`` for the load
  variant), so ``matchType`` always decides the scalar comparison;
* ``isPrf`` suppresses the scalar path only — the vector unit-stride path does
  not test it at all.

Contract: docs/contracts/load-trigger.md
"""
from __future__ import annotations

import random

from suites.memblock.lsu.store_trigger.env import (
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
    chain_fire,
)

VADDR_BITS = 50
VWORD_BITS = 4


def load_slot_hit(cfg: TriggerConfig, vaddr: int, mask: int, is_vector_stride: bool,
                  is_prf: int, debug_mode: int, enable: int) -> bool:
    if not enable or cfg.select or debug_mode or not cfg.store:
        # ``cfg.store`` holds the slot's type bit; for this DUT it is ``load``.
        return False
    if is_vector_stride:
        if (vaddr >> VWORD_BITS) != (cfg.tdata2 >> VWORD_BITS):
            return False
        return bool(mask & (1 << (cfg.tdata2 & ((1 << VWORD_BITS) - 1))))
    if is_prf:
        return False
    value = cfg.tdata2 & ((1 << VADDR_BITS) - 1)
    if cfg.match_type == MATCH_EQ:
        return vaddr == value
    if cfg.match_type == MATCH_GE:
        return vaddr >= value
    if cfg.match_type == MATCH_LT:
        return vaddr < value
    return False   # NAPOT is not implemented by this build


def reference_action(configs, vaddr: int, mask: int, is_vector_stride: bool,
                     is_prf: int, debug_mode: int, enables, can_raise_bp_exp: int) -> int:
    hits = [load_slot_hit(cfg, vaddr, mask, is_vector_stride, is_prf, debug_mode,
                          enables[i]) for i, cfg in enumerate(configs)]
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


class LoadTriggerEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.cfg_signals = []
        for index in range(TRIGGER_NUM):
            prefix = f"tdataVec_io_fromCsrTrigger_tdataVec_{index}_"
            self.cfg_signals.append({
                "match_type": getattr(dut, prefix + "matchType"),
                "select": getattr(dut, prefix + "select"),
                "timing": getattr(dut, prefix + "timing"),
                "action": getattr(dut, prefix + "action"),
                "chain": getattr(dut, prefix + "chain"),
                "load": getattr(dut, prefix + "load"),
                "tdata2": getattr(dut, prefix + "tdata2"),
            })
        self.enable = [getattr(dut, f"tdataVec_io_fromCsrTrigger_tEnableVec_{i}")
                       for i in range(TRIGGER_NUM)]
        self.debug_mode = dut.tdataVec_io_fromCsrTrigger_debugMode
        self.can_raise_bp = dut.tdataVec_io_fromCsrTrigger_triggerCanRaiseBpExp
        self.vaddr = dut.tdataVec_io_fromLoadStore_vaddr
        self.is_vector_stride = dut.tdataVec_io_fromLoadStore_isVectorUnitStride
        self.mask = dut.tdataVec_io_fromLoadStore_mask
        self.is_prf = dut.tdataVec_io_isPrf
        self.action = dut.tdataVec_io_toLoadStore_triggerAction
        self.vectors = 0

    def drive(self, configs, enables, vaddr, mask, is_vector_stride, is_prf,
              debug_mode, can_raise_bp_exp) -> None:
        for index, cfg in enumerate(configs):
            signals = self.cfg_signals[index]
            signals["match_type"].Set(cfg.match_type)
            signals["select"].Set(cfg.select)
            signals["timing"].Set(cfg.timing)
            signals["action"].Set(cfg.action)
            signals["chain"].Set(cfg.chain)
            signals["load"].Set(cfg.store)   # TriggerConfig.store is the type bit
            signals["tdata2"].Set(cfg.tdata2 & ((1 << 64) - 1))
            self.enable[index].Set(1 if enables[index] else 0)
        self.debug_mode.Set(1 if debug_mode else 0)
        self.can_raise_bp.Set(1 if can_raise_bp_exp else 0)
        self.vaddr.Set(vaddr & ((1 << VADDR_BITS) - 1))
        self.is_vector_stride.Set(1 if is_vector_stride else 0)
        self.mask.Set(mask & 0xFFFF)
        self.is_prf.Set(1 if is_prf else 0)

    def eval(self) -> None:
        self.dut.Step(1)

    def check(self, context, configs, enables, vaddr, mask, is_vector_stride,
              is_prf, debug_mode, can_raise_bp_exp) -> int:
        want = reference_action(configs, vaddr, mask, is_vector_stride, is_prf,
                                debug_mode, enables, can_raise_bp_exp)
        got = int(self.action.value)
        if got != want:
            raise AssertionError(
                f"{context}: triggerAction {got:#x} != {want:#x} "
                f"(vaddr={vaddr:#x} vec={int(is_vector_stride)} prf={int(is_prf)} "
                f"debug={int(debug_mode)} bpExp={int(can_raise_bp_exp)}")
        self.vectors += 1
        return got


def independent_configs(rng: random.Random) -> list[TriggerConfig]:
    return [
        TriggerConfig(match_type=rng.choice([MATCH_EQ, MATCH_GE, MATCH_LT, MATCH_NAPOT]),
                      select=1 if rng.random() < 0.1 else 0,
                      timing=rng.randrange(2),
                      action=rng.choice([ACTION_CODE_DEBUG, ACTION_CODE_BREAKPOINT, 2, 15]),
                      chain=1 if rng.random() < 0.3 else 0,
                      store=1 if rng.random() < 0.85 else 0,   # load bit here
                      tdata2=rng.randrange(1 << VADDR_BITS))
        for _ in range(TRIGGER_NUM)
    ]
