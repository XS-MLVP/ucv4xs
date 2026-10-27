"""Environment and independent reference for Arbiter7_LoadStageIO.

The reference is a two-step model, not a copy of the RTL ternary tree:

1. **Priority selection** — walk the five real sources in order 0,1,2,3,5 and
   pick the first valid one; ``out_ready`` only gates the ready bitmap. This is
   the micro-architectural contract from ``NewLoadUnit.scala:94-102``.
2. **Per-field tables** — the generated RTL folds each payload bit differently
   depending on whether the source drives a constant, a gated value or nothing
   at all. Those per-field rules are declared below as data (mode ``PAYLOAD`` =
   take the selected source's bit, ``(value,)`` = constant) with a bubble
   default, so a mismatch points at exactly one field/source pair.

Contract: docs/contracts/load-arbiter.md
"""
from __future__ import annotations

import random

PAYLOAD = "payload"

# Sources present at the generated boundary. Slots 4 and 6 (prefetchHiConf,
# prefetchLoConf) were removed by constant propagation in this configuration.
SOURCES = (0, 1, 2, 3, 5)
SOURCE_NAMES = {0: "unalignTail", 1: "replayHiPrio", 2: "fastReplay",
                3: "replayLoPrio", 5: "scalarIssue"}

# field -> (width, [(source, mode), ...], bubble_default)
FIELD_RULES = {
    "accessType_instrType": (3, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 4),
    "accessType_pftType": (2, [(0, PAYLOAD), (1, (0,)), (2, PAYLOAD), (3, (0,)), (5, PAYLOAD)], 0),
    "entrance": (8, [(0, (1,)), (1, (2,)), (2, PAYLOAD), (3, (8,)), (5, (64,))], 128),
    "fullva": (64, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "mask": (16, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "mshrId": (4, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD)], 0),
    "ncReplay": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD)], 0),
    "noQuery": (1, [(0, (0,)), (1, PAYLOAD), (2, (1,)), (3, PAYLOAD), (5, PAYLOAD)], 1),
    "paddr": (48, [(0, PAYLOAD), (1, (0,)), (2, PAYLOAD)], 0),
    "replayQueueIdx": (7, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD)], 0),
    "size": (3, [(0, (4,)), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uncacheReplay": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD)], 0),
    "uop_exceptionVec_15": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD)], 0),
    "uop_exceptionVec_19": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD)], 0),
    "uop_exceptionVec_23": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD)], 0),
    "uop_exceptionVec_6": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD)], 0),
    "uop_exceptionVec_7": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD)], 0),
    "uop_fpWen": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_ftqOffset": (5, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_ftqPtr_flag": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_ftqPtr_value": (6, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_fuOpType": (12, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_isRVC": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_loadWaitBit": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_loadWaitStrict": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_lqIdx_flag": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_lqIdx_value": (7, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_pdest": (8, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_perfDebugInfo_runahead_checkpoint_id": (64, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD)], 0),
    "uop_rfWen": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_robIdx_flag": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_robIdx_isFormer": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_robIdx_value": (8, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_sqIdx_first_flag": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_sqIdx_second_flag": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_sqIdx_value": (6, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_storeSetHit": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_v0Wen": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_vecWen": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_waitSqIdx_first_flag": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_waitSqIdx_second_flag": (1, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "uop_waitSqIdx_value": (6, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
    "vaddr": (50, [(0, PAYLOAD), (1, PAYLOAD), (2, PAYLOAD), (3, PAYLOAD), (5, PAYLOAD)], 0),
}

# in_*.ready: slot 0 is highest priority and takes out_ready directly; every
# other slot is blocked by any higher-priority valid source.
def ready_vector(valid: dict[int, int], out_ready: int) -> dict[int, int]:
    ready = {0: out_ready}
    for index in SOURCES[1:]:
        higher = any(valid[source] for source in SOURCES if source < index)
        ready[index] = 0 if higher else out_ready
    return ready


def winner(valid: dict[int, int]) -> int | None:
    for source in SOURCES:
        if valid[source]:
            return source
    return None


def reference_action(valid: dict[int, int], payload: dict[int, dict],
                     out_ready: int) -> dict:
    chosen = winner(valid)
    out = {"valid": 0 if chosen is None else 1, "chosen": chosen,
           "ready": ready_vector(valid, out_ready), "bits": {}}
    for name, (width, arms, default) in FIELD_RULES.items():
        if chosen is None:
            value = default
        else:
            mode = None
            for source, candidate in arms:
                if source == chosen:
                    mode = candidate
                    break
            if mode is PAYLOAD:
                value = payload[chosen].get(name, 0)
            elif mode is None:
                value = default
            else:
                value = mode[0]
        out["bits"][name] = value & ((1 << width) - 1)
    return out


class LoadArbiterEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.in_valid = {source: getattr(dut, f"io_in_{source}_valid") for source in SOURCES}
        self.in_bits = {}
        for source in SOURCES:
            fields = {}
            for name in FIELD_RULES:
                signal = getattr(dut, f"io_in_{source}_bits_{name}", None)
                if signal is not None:
                    fields[name] = signal
            self.in_bits[source] = fields
        self.in_ready = {source: getattr(dut, f"io_in_{source}_ready") for source in SOURCES}
        self.out_valid = dut.io_out_valid
        self.out_ready = dut.io_out_ready
        self.out_bits = {name: getattr(dut, f"io_out_bits_{name}") for name in FIELD_RULES}
        self.vectors = 0

    def drive(self, valid: dict[int, int], payload: dict[int, dict],
              out_ready: int) -> None:
        for source in SOURCES:
            self.in_valid[source].Set(1 if valid.get(source) else 0)
            values = payload.get(source, {})
            for name, signal in self.in_bits[source].items():
                signal.Set(int(values.get(name, 0)) & ((1 << FIELD_RULES[name][0]) - 1))
        self.out_ready.Set(1 if out_ready else 0)

    def eval(self) -> None:
        self.dut.Step(1)

    def check(self, context: str, valid: dict[int, int], payload: dict[int, dict],
              out_ready: int) -> dict:
        want = reference_action(valid, payload, out_ready)
        got_valid = int(self.out_valid.value)
        if got_valid != want["valid"]:
            raise AssertionError(
                f"{context}: out.valid {got_valid} != {want['valid']} "
                f"(valid={valid} out_ready={out_ready})")
        for source in SOURCES:
            got_ready = int(self.in_ready[source].value)
            if got_ready != want["ready"][source]:
                raise AssertionError(
                    f"{context}: in_{source}.ready {got_ready} != "
                    f"{want['ready'][source]} (valid={valid} out_ready={out_ready})")
        for name, signal in self.out_bits.items():
            got = int(signal.value)
            if got != want["bits"][name]:
                raise AssertionError(
                    f"{context}: out.bits.{name} {got:#x} != {want['bits'][name]:#x} "
                    f"(chosen={want['chosen']} valid={valid})")
        self.vectors += 1
        if self.coverage is not None:
            self.coverage.observe(valid=valid, out_ready=out_ready,
                                  chosen=want["chosen"], bits=want["bits"])
        return want


def random_payload(rng: random.Random, source: int) -> dict:
    return {name: rng.randrange(1 << width) for name, (width, _arms, _default)
            in FIELD_RULES.items()}


def blank_payload() -> dict:
    return {name: 0 for name in FIELD_RULES}
